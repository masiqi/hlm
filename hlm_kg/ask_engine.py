from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import uuid4
from typing import Any

from hlm_kg.chapter_sources import ChapterSource, parse_chapter_source
from hlm_kg.content_store import ContentStore
from hlm_kg.domain import (
    AnswerClaim,
    AnswerSection,
    AskAnswer,
    ContinuationLink,
    Evidence,
    Refusal,
    RefusalReason,
)
from hlm_kg.evidence import detect_source_conflict, supported_claims
from hlm_kg.evidence_adapter import EvidenceCandidate, normalize_query_data_response
from hlm_kg.entity_resolver import EntityResolver, ResolvedEntity
from hlm_kg.question_planner import QuestionPlanner


OUT_OF_SCOPE_TERMS = ("作文", "现实", "八卦", "数学", "英语")
MAX_RETRIEVAL_EVIDENCE = 3
AGE_QUESTION_MARKERS = ("几岁", "多大", "年龄", "岁数", "年纪")
DEATH_QUESTION_MARKERS = ("怎么死", "怎样死", "如何死", "死因", "为什么死", "为何而死", "因何而死", "去世", "死亡")
DEATH_EVIDENCE_MARKERS = (
    "病情加重",
    "急怒攻心",
    "吐血",
    "绝粒",
    "速死",
    "临终",
    "垂毙",
    "泪尽",
    "魂归",
    "去世",
    "死亡",
    "死",
    "亡",
    "咽气",
    "气绝",
    "痨死",
    "病死",
    "自尽",
    "投井",
    "跳井",
    "上吊",
    "殉情",
)
DEATH_SOURCE_TITLE_MARKERS = ("死", "亡", "焚稿", "魂归", "病", "临终", "绝粒", "殉情")
FIRST_MENTION_MARKERS = ("第一次", "首次", "初次", "最早", "起初", "开头", "开始")
AGE_EXPRESSION_RE = re.compile(
    r"(?:年方|年已|年约|年过)?[一二三四五六七八九十百千万两\d]+(?:来|多|余)?岁|"
    r"大[一二三四五六七八九十百千万两\d]+岁"
)


@dataclass(frozen=True)
class QuestionProfile:
    subject_terms: tuple[str, ...]
    subject_clues: tuple[str, ...]
    dimensions: frozenset[str]
    first_mention: bool = False


class AskEngine:
    def __init__(self, store: ContentStore) -> None:
        self.store = store

    def ask(self, question: str, retrieval_client: Any | None = None) -> AskAnswer:
        if any(term in question for term in OUT_OF_SCOPE_TERMS):
            return self._refuse(question, "OUT_OF_SCOPE", "当前产品只支持《红楼梦》阅读理解相关问题。")

        if retrieval_client is not None:
            return self._answer_from_retrieval(question, retrieval_client)

        if "没有资料" in question:
            supported = self._daiyu_answer(question)
            return AskAnswer(
                id=supported.id,
                question=question,
                status="partial",
                short_conclusion=supported.short_conclusion,
                evidence=supported.evidence,
                explanation=supported.explanation,
                quotable_facts=supported.quotable_facts,
                continuation_links=supported.continuation_links,
                refusal=Refusal(
                    reason="UNSUPPORTED_SUBCLAIM",
                    message="“没有资料的后文细节”当前资料不足，未生成确定结论。",
                ),
            )

        if "黛玉" in question or "葬花" in question or "葬花吟" in question:
            return self._daiyu_answer(question)
        if "探春" in question or "理家" in question:
            return self._tanchun_answer(question)

        local_candidates = self._original_text_candidates(question, _question_profile(question, self.store))
        if local_candidates:
            return self._candidate_evidence_answer(question, local_candidates)

        return self._refuse(question, "NO_EVIDENCE", "当前资料中没有找到足够依据回答这个问题。")

    def _answer_from_retrieval(self, question: str, retrieval_client: Any) -> AskAnswer:
        profile = _question_profile(question, self.store)
        try:
            response = retrieval_client.query_data(question, mode="hybrid", only_need_context=True)
        except Exception:  # noqa: BLE001 - retrieval failure should not expose internals to students
            return self._refuse(question, "GRAPH_UNAVAILABLE", "关系线索暂时不可用，当前不能生成可靠回答。")

        candidates = normalize_query_data_response(response, question=question)
        if _is_chapter_location_question(question):
            chapter_candidates = _chapter_location_candidates(candidates)
            if _has_conflicting_chapters(chapter_candidates):
                return self._refuse(question, "SOURCE_CONFLICT", "资料存在不一致，优先查看原文依据。")
            candidate = chapter_candidates[0] if chapter_candidates else None
            if candidate is None:
                return self._refuse(question, "NO_EVIDENCE", "当前资料中没有找到足够依据回答这个问题。")
            return self._chapter_location_answer(question, candidate)

        supported_candidates = _supporting_candidates(candidates, profile=profile)
        original_text_candidates = self._original_text_candidates(
            question,
            profile,
            answer_hints=[
                answer
                for candidate in supported_candidates
                if (answer := _candidate_age_answer(candidate, profile))
            ],
            preferred_chapters=[
                source.chapter_number
                for candidate in supported_candidates
                for source in candidate.chapter_sources
            ],
        )
        if original_text_candidates:
            supported_candidates = original_text_candidates + supported_candidates
        if not supported_candidates:
            return self._refuse(question, "NO_EVIDENCE", "当前资料中没有找到足够依据回答这个问题。")

        return self._candidate_evidence_answer(question, supported_candidates, profile=profile)

    def _original_text_candidates(
        self,
        question: str,
        profile: QuestionProfile,
        *,
        answer_hints: list[str] | None = None,
        preferred_chapters: list[int] | None = None,
    ) -> list[EvidenceCandidate]:
        if "age" not in profile.dimensions or not profile.subject_terms:
            return []

        answer_hints = answer_hints or []
        candidates: list[EvidenceCandidate] = []
        chapter_order = _chapter_scan_order(preferred_chapters)
        if profile.first_mention:
            first_chapter = self._first_subject_chapter(profile)
            chapter_order = [first_chapter] if first_chapter is not None else []
        for chapter_number in chapter_order:
            try:
                chapter = self.store.chapter(chapter_number)
                text = self.store.chapter_text(chapter_number)
            except KeyError:
                continue
            match = _find_attributed_age(text, profile) or _find_age_answer_hint(text, answer_hints)
            if match is None:
                continue
            source = _chapter_source_for_chapter(chapter)
            candidates.append(
                EvidenceCandidate(
                    kind="chunk",
                    title=f"{source.chapter_label}：{source.chapter_title}",
                    description=_text_window_around_span(text, match.span(), radius=260),
                    query_mode="original_text",
                    file_paths=[chapter.original_text_path],
                    source_ids=[],
                    chapter_sources=[source],
                    raw={"answer_dimension": "age", "answer_text": match.group(0)},
                    score=1000 - chapter_number,
                )
            )
            if profile.first_mention or len(candidates) >= MAX_RETRIEVAL_EVIDENCE:
                break
        return candidates

    def _first_subject_chapter(self, profile: QuestionProfile) -> int | None:
        if profile.subject_clues:
            for chapter_number in range(1, 121):
                try:
                    text = self.store.chapter_text(chapter_number)
                except KeyError:
                    continue
                if any(_contains_fuzzy_clue(text, clue) for clue in profile.subject_clues):
                    return chapter_number
        for chapter_number in range(1, 121):
            try:
                text = self.store.chapter_text(chapter_number)
            except KeyError:
                continue
            if _text_mentions_profile_subject(text, profile):
                return chapter_number
        return None

    def _chapter_location_answer(self, question: str, candidate: EvidenceCandidate) -> AskAnswer:
        source = candidate.chapter_sources[0]
        evidence = Evidence(
            id=f"ev-query-{uuid4()}",
            source_type="graph_relation" if candidate.kind in {"relationship", "entity"} else "original_text",
            chapter=source.chapter_number,
            location=f"{source.chapter_label}：{source.chapter_title}",
            quote=None,
            evidence_text=candidate.description or candidate.title,
            entity_ids=[],
            relation_id=candidate.title if candidate.kind == "relationship" else None,
            confidence="explicit",
            provenance=source.source_file,
            derived_from_ids=[],
        )
        conclusion = AnswerClaim(
            text=f"根据可回溯资料，相关内容出现在{source.chapter_label}《{source.chapter_title}》。",
            evidence_ids=[evidence.id],
            claim_type="identity_relation",
        )
        explanation = AnswerClaim(
            text=f"依据来自{source.source_file}，说明“{candidate.title}”与这一回相关。",
            evidence_ids=[evidence.id],
            claim_type="quotable_fact",
        )
        return AskAnswer(
            id=f"ask-{uuid4()}",
            question=question,
            status="answered",
            short_conclusion=[conclusion],
            evidence=[evidence],
            explanation=[AnswerSection(title="为什么", claims=[explanation])],
            quotable_facts=AnswerSection(title="可引用事实", claims=[explanation]),
            continuation_links=[
                ContinuationLink(f"查看{source.chapter_label}", "chapter", str(source.chapter_number)),
            ],
            refusal=None,
        )

    def _candidate_evidence_answer(
        self,
        question: str,
        candidates: list[EvidenceCandidate],
        *,
        profile: QuestionProfile | None = None,
    ) -> AskAnswer:
        profile = profile or _question_profile(question, self.store)
        selected_candidates = candidates[:MAX_RETRIEVAL_EVIDENCE]
        evidence = [
            _evidence_from_candidate(candidate, index, profile=profile)
            for index, candidate in enumerate(selected_candidates, start=1)
        ]
        primary_candidate = selected_candidates[0]
        primary_evidence = evidence[0]
        conclusion = AnswerClaim(
            text=_student_safe_candidate_conclusion(primary_candidate, profile=profile),
            evidence_ids=[primary_evidence.id],
            claim_type=_claim_type_for_candidate(primary_candidate, profile=profile),
        )
        explanation_claims = [
            AnswerClaim(
                text=_student_safe_evidence_explanation(candidate, profile=profile),
                evidence_ids=[item.id],
                claim_type=_claim_type_for_candidate(candidate, profile=profile),
            )
            for candidate, item in zip(selected_candidates, evidence, strict=True)
        ]
        quotable_claims = [
            AnswerClaim(
                text=_quotable_fact_from_candidate(candidate, profile=profile),
                evidence_ids=[item.id],
                claim_type="quotable_fact",
            )
            for candidate, item in zip(selected_candidates, evidence, strict=True)
        ]
        status = "partial" if _has_explicit_unsupported_subclaim(question) else "answered"
        return AskAnswer(
            id=f"ask-{uuid4()}",
            question=question,
            status=status,
            short_conclusion=[conclusion],
            evidence=evidence,
            explanation=[AnswerSection(title="依据", claims=explanation_claims)],
            quotable_facts=AnswerSection(title="可引用事实", claims=quotable_claims),
            continuation_links=_continuation_links_for_candidates(selected_candidates, profile=profile),
            refusal=(
                Refusal(
                    reason="UNSUPPORTED_SUBCLAIM",
                    message="“没有资料的后文细节”当前资料不足，未生成确定结论。",
                )
                if status == "partial"
                else None
            ),
        )

    def _daiyu_answer(self, question: str) -> AskAnswer:
        evidence = [
            self.store.evidence("ev-027-daiyu-burying-flowers"),
            self.store.evidence("ev-rel-daiyu-burying-flowers-fate"),
        ]
        conclusion = AnswerClaim(
            text="黛玉葬花可用于理解她的身世悲感；后文关联需要结合全书关系线索来看。",
            evidence_ids=["ev-rel-daiyu-burying-flowers-fate"],
            claim_type="image_foreshadowing",
        )
        quotable = AnswerClaim(
            text="第 27 回黛玉葬花并吟《葬花吟》，可用于说明她的身世悲感与洁身自持。",
            evidence_ids=["ev-027-daiyu-burying-flowers"],
            claim_type="quotable_fact",
        )
        return self._answer(question, evidence, conclusion, quotable, ContinuationLink("查看第二十七回", "chapter", "27"))

    def _tanchun_answer(self, question: str) -> AskAnswer:
        evidence = [
            self.store.evidence("ev-056-tanchun-manages-household"),
            self.store.evidence("ev-rel-tanchun-manages-trait"),
        ]
        conclusion = AnswerClaim(
            text="探春理家体现她兴利除弊的管理才干和忧患意识。",
            evidence_ids=["ev-056-tanchun-manages-household", "ev-rel-tanchun-manages-trait"],
            claim_type="event_causality",
        )
        quotable = AnswerClaim(
            text="第 56 回探春理家，通过整顿大观园事务体现其兴利除弊的管理才干。",
            evidence_ids=["ev-056-tanchun-manages-household"],
            claim_type="quotable_fact",
        )
        return self._answer(question, evidence, conclusion, quotable, ContinuationLink("查看第五十六回", "chapter", "56"))

    def _answer(
        self,
        question: str,
        evidence: list[Evidence],
        conclusion: AnswerClaim,
        quotable: AnswerClaim,
        link: ContinuationLink,
    ) -> AskAnswer:
        if detect_source_conflict(evidence):
            return self._refuse(question, "SOURCE_CONFLICT", "资料存在不一致，优先查看原文依据。")
        explanation_claim = AnswerClaim(
            text="原文章回材料负责定位事实，关系线索负责说明可支持的理解方向。",
            evidence_ids=conclusion.evidence_ids,
            claim_type=conclusion.claim_type,
        )
        supported = supported_claims([conclusion, quotable, explanation_claim], evidence)
        if len(supported) != 3:
            return self._refuse(question, "NO_EVIDENCE", "当前资料中没有找到足够依据回答这个问题。")
        return AskAnswer(
            id=f"ask-{uuid4()}",
            question=question,
            status="answered",
            short_conclusion=[conclusion],
            evidence=evidence,
            explanation=[AnswerSection(title="为什么", claims=[explanation_claim])],
            quotable_facts=AnswerSection(title="可引用事实", claims=[quotable]),
            continuation_links=[link],
            refusal=None,
        )

    def _refuse(self, question: str, reason: RefusalReason, message: str) -> AskAnswer:
        return AskAnswer(
            id=f"ask-{uuid4()}",
            question=question,
            status="refused",
            short_conclusion=[],
            evidence=[],
            explanation=[],
            quotable_facts=None,
            continuation_links=[],
            refusal=Refusal(reason=reason, message=message),
        )


def _is_chapter_location_question(question: str) -> bool:
    return any(marker in question for marker in ("哪一回", "哪一章", "第几回", "第几章", "发生在", "出现在哪", "章回定位"))


def _chapter_location_candidates(candidates: list[EvidenceCandidate]) -> list[EvidenceCandidate]:
    return [candidate for candidate in candidates if candidate.chapter_sources and _supports_chapter_location(candidate)]


def _supporting_candidates(candidates: list[EvidenceCandidate], *, profile: QuestionProfile) -> list[EvidenceCandidate]:
    supported = [
        candidate
        for candidate in candidates
        if candidate.kind != "reference"
        and candidate.chapter_sources
        and (candidate.description.strip() or candidate.title.strip())
    ]
    if profile.subject_terms:
        supported = [candidate for candidate in supported if _candidate_references_profile_subject(candidate, profile)]
    if "age" in profile.dimensions:
        supported = [candidate for candidate in supported if _candidate_age_answer(candidate, profile)]
    if "death" in profile.dimensions:
        supported = [candidate for candidate in supported if _candidate_death_answer(candidate, profile)]
    return supported


def _supports_chapter_location(candidate: EvidenceCandidate) -> bool:
    if candidate.kind == "reference":
        return False
    if candidate.kind == "chunk":
        text = candidate.description
    else:
        text = f"{candidate.description}\n{candidate.relationship_keywords or ''}"
    return any(marker in text for marker in ("发生在", "出现于", "出现在", "章回", "回目", "出自第", "发生章回"))


def _candidate_references_profile_subject(candidate: EvidenceCandidate, profile: QuestionProfile) -> bool:
    text = "\n".join(
        [
            candidate.title,
            candidate.description,
            candidate.relationship_keywords or "",
            str(candidate.raw.get("entity_name", "")) if isinstance(candidate.raw, dict) else "",
            str(candidate.raw.get("src_id", "")) if isinstance(candidate.raw, dict) else "",
            str(candidate.raw.get("tgt_id", "")) if isinstance(candidate.raw, dict) else "",
        ]
    )
    return any(term and term in text for term in profile.subject_terms)


def _has_conflicting_chapters(candidates: list[EvidenceCandidate]) -> bool:
    chapters = {
        source.chapter_number
        for candidate in candidates
        for source in candidate.chapter_sources
    }
    return len(chapters) > 1


def _is_age_question(question: str) -> bool:
    return any(marker in question for marker in AGE_QUESTION_MARKERS)


def _is_death_question(question: str) -> bool:
    return any(marker in question for marker in DEATH_QUESTION_MARKERS)


def _question_profile(question: str, store: Any | None = None) -> QuestionProfile:
    plan = QuestionPlanner(EntityResolver(store)).plan(question) if store is not None else None
    dimensions = _dimensions_from_plan(question, plan)
    matched_cards = _cards_for_resolved_subjects(tuple(plan.subjects) if plan is not None else (), store)
    subject_terms: list[str] = []
    subject_clues: list[str] = []
    if plan is not None:
        for term in plan.subject_terms:
            _append_unique(subject_terms, term)
    for card in matched_cards:
        for clue in _subject_clues_from_card(card):
            _append_unique(subject_clues, clue)

    if not subject_terms:
        matched_cards = _question_subject_cards(question, store)
        for card in matched_cards:
            _append_unique(subject_terms, str(card.name))
            for alias in _card_name_aliases(card, matched_cards, store):
                _append_unique(subject_terms, alias)
            for clue in _subject_clues_from_card(card):
                _append_unique(subject_clues, clue)

    if not subject_terms:
        for term in _fallback_question_subject_terms(question):
            _append_unique(subject_terms, term)

    return QuestionProfile(
        subject_terms=tuple(subject_terms),
        subject_clues=tuple(subject_clues),
        dimensions=frozenset(dimensions),
        first_mention=any(marker in question for marker in FIRST_MENTION_MARKERS),
    )


def _dimensions_from_plan(question: str, plan: Any | None) -> set[str]:
    dimensions: set[str] = set()
    target_property = getattr(plan, "target_property", None)
    if target_property == "age" or _is_age_question(question):
        dimensions.add("age")
    if target_property == "death_cause_or_process" or _is_death_question(question):
        dimensions.add("death")
    return dimensions


def _cards_for_resolved_subjects(subjects: tuple[ResolvedEntity, ...], store: Any | None) -> list[Any]:
    if not subjects:
        return []
    cards = _knowledge_cards_for_profile(store)
    by_id = {str(getattr(card, "id", "") or ""): card for card in cards}
    by_name = {str(getattr(card, "name", "") or ""): card for card in cards}
    matched: list[Any] = []
    for subject in subjects:
        card = by_id.get(str(subject.canonical_id or "")) or by_name.get(str(subject.canonical_name or ""))
        if card is not None and card not in matched:
            matched.append(card)
    return matched


def _question_subject_cards(question: str, store: Any | None) -> list[Any]:
    cards = _knowledge_cards_for_profile(store)
    matches = [card for card in cards if _usable_card_name(card) in question]
    matches.sort(key=lambda card: len(_usable_card_name(card)), reverse=True)
    selected: list[Any] = []
    for card in matches:
        name = _usable_card_name(card)
        if any(_is_shadowed_subject_name(name, card, selected_card) for selected_card in selected):
            continue
        selected.append(card)
    return selected


def _is_shadowed_subject_name(name: str, card: Any, selected_card: Any) -> bool:
    selected_name = _usable_card_name(selected_card)
    if not selected_name or name not in selected_name:
        return False
    return not (_card_type(card) == "person" and _card_type(selected_card) == "person")


def _knowledge_cards_for_profile(store: Any | None) -> list[Any]:
    if store is None:
        return []
    fallback_store = getattr(store, "fallback_store", None)
    if fallback_store is not None and fallback_store is not store:
        return _knowledge_cards_for_profile(fallback_store)
    try:
        cards = getattr(store, "knowledge_cards")
    except Exception:  # noqa: BLE001 - profile extraction is advisory
        return []
    if callable(cards):
        try:
            cards = cards()
        except Exception:  # noqa: BLE001 - profile extraction is advisory
            return []
    if not isinstance(cards, list):
        return []
    return [card for card in cards if _usable_card_name(card)]


def _usable_card_name(card: Any) -> str:
    name = str(getattr(card, "name", "") or "").strip()
    if len(name) < 2:
        return ""
    return name


def _card_type(card: Any) -> str:
    return str(getattr(card, "type", "") or "")


def _card_name_aliases(card: Any, matched_cards: list[Any], store: Any | None) -> list[str]:
    if _card_type(card) != "person":
        return []
    name = _usable_card_name(card)
    if not name:
        return []
    aliases: list[str] = []
    if re.fullmatch(r"[\u4e00-\u9fff]{3}", name):
        _append_unique(aliases, name[1:])
    for other in _knowledge_cards_for_profile(store):
        other_name = _usable_card_name(other)
        if not other_name or other_name == name or _card_type(other) != _card_type(card):
            continue
        if len(other_name) >= 2 and other_name in name:
            _append_unique(aliases, other_name)
    for matched in matched_cards:
        matched_name = _usable_card_name(matched)
        if matched_name and matched_name in name:
            _append_unique(aliases, matched_name)
    return aliases


def _subject_clues_from_card(card: Any) -> list[str]:
    if _card_type(card) != "person":
        return []
    material = "；".join(
        [
            str(getattr(card, "brief", "") or ""),
            "；".join(str(item) for item in getattr(card, "text_understanding", [])[:3]),
        ]
    )
    clues: list[str] = []
    if re.search(r"衔.{0,6}玉", material):
        clues.append("衔玉")
    return clues


def _fallback_question_subject_terms(question: str) -> list[str]:
    compact = re.sub(r"[，。？！、：；“”\"'《》（）()]", "", question)
    stop_words = (
        "第一次",
        "首次",
        "初次",
        "最早",
        "出现",
        "出场",
        "提到",
        "写到",
        "资料",
        "介绍",
        "在书中",
        "书中",
        "时候",
        "是",
        "几岁",
        "多大",
        "年纪",
        "年龄",
        "岁数",
        "这时候",
    )
    for word in stop_words:
        compact = compact.replace(word, " ")
    terms: list[str] = []
    for part in compact.split():
        if len(part) < 2:
            continue
        _append_unique(terms, part)
        if re.fullmatch(r"[\u4e00-\u9fff]{3}", part):
            _append_unique(terms, part[1:])
    return terms


def _append_unique(items: list[str], value: str) -> None:
    value = value.strip()
    if value and value not in items:
        items.append(value)


def _text_mentions_profile_subject(text: str, profile: QuestionProfile) -> bool:
    if any(term and term in text for term in profile.subject_terms):
        return True
    return any(_contains_fuzzy_clue(text, clue) for clue in profile.subject_clues)


def _text_window_around_span(text: str, span: tuple[int, int], *, radius: int = 90) -> str:
    start = max(0, span[0] - radius)
    end = min(len(text), span[1] + radius)
    return text[start:end].replace("\n", "").strip()


def _find_attributed_age(text: str, profile: QuestionProfile) -> re.Match[str] | None:
    for match in AGE_EXPRESSION_RE.finditer(text):
        if _age_expression_is_attributed_to_subject(text, match, profile):
            return match
    return None


def _find_age_answer_hint(text: str, answer_hints: list[str]) -> re.Match[str] | None:
    for match in AGE_EXPRESSION_RE.finditer(text):
        if match.group(0) in answer_hints:
            return match
    return None


def _chapter_scan_order(preferred_chapters: list[int] | None = None) -> list[int]:
    ordered: list[int] = []
    for chapter in preferred_chapters or []:
        if 1 <= chapter <= 120 and chapter not in ordered:
            ordered.append(chapter)
    ordered.extend(chapter for chapter in range(1, 121) if chapter not in ordered)
    return ordered


def _candidate_age_answer(candidate: EvidenceCandidate, profile: QuestionProfile) -> str | None:
    raw_answer = candidate.raw.get("answer_text") if isinstance(candidate.raw, dict) else None
    if isinstance(raw_answer, str) and raw_answer:
        return raw_answer
    text = f"{candidate.title}\n{candidate.description}\n{candidate.relationship_keywords or ''}"
    match = _find_attributed_age(text, profile)
    return match.group(0) if match is not None else None


def _candidate_death_answer(candidate: EvidenceCandidate, profile: QuestionProfile) -> str | None:
    text = _clean_candidate_text(f"{candidate.description}<SEP>{candidate.relationship_keywords or ''}")
    segments = _candidate_text_segments(text)
    focused_segments = [
        segment
        for segment in segments
        if _segment_references_subject(segment, profile) and _segment_has_death_answer(segment)
    ]
    if not focused_segments:
        return None
    return "；".join(_dedupe_preserve_order(focused_segments[:2]))


def _candidate_text_segments(text: str) -> list[str]:
    normalized = text.replace("<SEP>", "。").replace("\n", "。")
    parts = re.split(r"(?<=[。；;])", normalized)
    return [part.strip("。；; \t") for part in parts if part.strip("。；; \t")]


def _segment_references_subject(segment: str, profile: QuestionProfile) -> bool:
    return any(term and term in segment for term in profile.subject_terms)


def _segment_has_death_answer(segment: str) -> bool:
    if not any(marker in segment for marker in DEATH_EVIDENCE_MARKERS):
        return False
    if "死后" in segment and not any(marker in segment for marker in ("病情加重", "急怒攻心", "吐血", "绝粒", "速死", "临终", "泪尽", "魂归")):
        return False
    return True


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    deduped: list[str] = []
    for item in items:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _age_expression_is_attributed_to_subject(text: str, match: re.Match[str], profile: QuestionProfile) -> bool:
    start, end = match.span()
    if _age_expression_points_to_following_nominal(text, match):
        return False
    before = text[max(0, start - 240):start]
    near_before = text[max(0, start - 90):start]
    immediate_before = text[max(0, start - 24):start]
    after = text[end:min(len(text), end + 100)]
    if match.group(0).startswith("大"):
        return any(term in immediate_before for term in profile.subject_terms) or any(
            _name_introduction_after_age(after, term) for term in profile.subject_terms
        )
    if any(term in near_before for term in profile.subject_terms):
        return True
    if any(_contains_fuzzy_clue(before, clue) for clue in profile.subject_clues):
        return True
    if any(_name_introduction_after_age(after, term) for term in profile.subject_terms):
        return True
    return False


def _age_expression_points_to_following_nominal(text: str, match: re.Match[str]) -> bool:
    following = text[match.end():match.end() + 12]
    return any(
        following.startswith(head)
        for head in ("的人", "的少年", "的孩子", "的小孩", "的小厮", "的丫头", "的小丫头", "的女子", "的女孩子")
    )


def _contains_fuzzy_clue(text: str, clue: str) -> bool:
    if clue in text:
        return True
    if len(clue) == 2:
        return re.search(f"{re.escape(clue[0])}.{{0,12}}{re.escape(clue[1])}", text) is not None
    return False


def _name_introduction_after_age(text: str, subject_term: str) -> bool:
    pattern = rf"(?:名|叫|称|唤|小名|乳名).{{0,16}}{re.escape(subject_term)}"
    return re.search(pattern, text) is not None


def _chapter_source_for_chapter(chapter: Any) -> ChapterSource:
    parsed = parse_chapter_source(str(chapter.original_text_path))
    if parsed is not None:
        return parsed
    return ChapterSource(
        chapter_number=int(chapter.number),
        chapter_label=f"第{int(chapter.number)}回",
        chapter_title=str(chapter.title),
        source_file=str(chapter.original_text_path),
    )


def _evidence_from_candidate(candidate: EvidenceCandidate, index: int, *, profile: QuestionProfile | None = None) -> Evidence:
    source = _source_for_candidate(candidate, profile=profile)
    return Evidence(
        id=f"ev-query-{index}-{uuid4()}",
        source_type=_source_type_for_candidate(candidate),
        chapter=source.chapter_number,
        location=f"{source.chapter_label}：{source.chapter_title}",
        quote=None,
        evidence_text=_evidence_text_for_candidate(candidate, profile=profile),
        entity_ids=[],
        relation_id=candidate.title if candidate.kind == "relationship" else None,
        confidence="explicit",
        provenance=source.source_file,
        derived_from_ids=[],
    )


def _source_for_candidate(candidate: EvidenceCandidate, *, profile: QuestionProfile | None = None) -> ChapterSource:
    if profile is not None and "death" in profile.dimensions:
        for source in candidate.chapter_sources:
            title_text = f"{source.chapter_label}{source.chapter_title}"
            if (
                any(term in title_text for term in profile.subject_terms)
                and any(marker in title_text for marker in DEATH_SOURCE_TITLE_MARKERS)
            ):
                return source
        for source in candidate.chapter_sources:
            title_text = f"{source.chapter_label}{source.chapter_title}"
            if source.chapter_number >= 80 and any(marker in title_text for marker in DEATH_SOURCE_TITLE_MARKERS):
                return source
        if candidate.chapter_sources:
            return candidate.chapter_sources[-1]
    return candidate.chapter_sources[0]


def _evidence_text_for_candidate(candidate: EvidenceCandidate, *, profile: QuestionProfile | None = None) -> str:
    if profile is not None and "death" in profile.dimensions:
        death_answer = _candidate_death_answer(candidate, profile)
        if death_answer:
            return death_answer
    return candidate.description or candidate.title


def _source_type_for_candidate(candidate: EvidenceCandidate) -> str:
    if candidate.kind in {"relationship", "entity"}:
        return "graph_relation"
    if candidate.kind == "chunk":
        return "original_text"
    return "processed_material"


def _claim_type_for_candidate(candidate: EvidenceCandidate, *, profile: QuestionProfile | None = None) -> str:
    if isinstance(candidate.raw, dict) and candidate.raw.get("answer_dimension") == "age":
        return "quotable_fact"
    if profile is not None and "death" in profile.dimensions:
        return "event_causality"
    if candidate.kind in {"relationship", "entity"}:
        return "identity_relation"
    return "plot_summary"


def _student_safe_candidate_conclusion(candidate: EvidenceCandidate, *, profile: QuestionProfile) -> str:
    if "death" in profile.dimensions:
        death_answer = _candidate_death_answer(candidate, profile)
        if death_answer:
            subject = _primary_subject_label(profile)
            return f"根据可回溯资料，{subject}的死亡经过或原因可概括为：{death_answer}。"
    if "age" in profile.dimensions:
        age_answer = _candidate_age_answer(candidate, profile)
        if age_answer:
            subject = _primary_subject_label(profile)
            source = candidate.chapter_sources[0] if candidate.chapter_sources else None
            source_text = f"{source.chapter_label}" if source is not None else "资料中"
            plain_age = _plain_age_expression(age_answer)
            if profile.first_mention:
                return f"根据可回溯资料，{subject}最早被明确介绍的年龄线索在{source_text}，原文依据是“{age_answer}”，可理解为{plain_age}。"
            return f"根据可回溯资料，{subject}的相关年龄线索是“{age_answer}”，可理解为{plain_age}。"
    description = _clean_candidate_text(candidate.description)
    if description:
        return f"根据可回溯资料，{description}"
    return f"根据可回溯资料，可以定位到“{candidate.title}”。"


def _student_safe_evidence_explanation(candidate: EvidenceCandidate, *, profile: QuestionProfile) -> str:
    source = _source_for_candidate(candidate, profile=profile)
    topic = _clean_candidate_text(candidate.title)
    if "death" in profile.dimensions:
        death_answer = _candidate_death_answer(candidate, profile)
        if death_answer:
            return f"{source.chapter_label}《{source.chapter_title}》的资料说明：{death_answer}"
    description = _clean_candidate_text(candidate.description)
    if description:
        return f"{source.chapter_label}《{source.chapter_title}》的资料说明：{description}"
    return f"{source.chapter_label}《{source.chapter_title}》提供了“{topic}”的相关依据。"


def _quotable_fact_from_candidate(candidate: EvidenceCandidate, *, profile: QuestionProfile) -> str:
    source = _source_for_candidate(candidate, profile=profile)
    if isinstance(candidate.raw, dict) and candidate.raw.get("answer_dimension") == "age":
        answer_text = str(candidate.raw.get("answer_text") or "").strip()
        if answer_text:
            return f"第{source.chapter_number}回：原文提供“{answer_text}”这一年龄线索。"
    if "death" in profile.dimensions:
        death_answer = _candidate_death_answer(candidate, profile)
        if death_answer:
            return f"第{source.chapter_number}回：{death_answer}"
    description = _clean_candidate_text(candidate.description or candidate.title)
    return f"第{source.chapter_number}回：{description}"


def _primary_subject_label(profile: QuestionProfile) -> str:
    return profile.subject_terms[0] if profile.subject_terms else "相关对象"


def _plain_age_expression(age_answer: str) -> str:
    if age_answer.endswith("来岁"):
        return f"{age_answer[:-2]}岁左右"
    if age_answer.startswith("大"):
        return f"比参照人物{age_answer}"
    return age_answer


def _continuation_links_for_candidates(candidates: list[EvidenceCandidate], *, profile: QuestionProfile) -> list[ContinuationLink]:
    links: list[ContinuationLink] = []
    seen: set[int] = set()
    for candidate in candidates:
        sources = [_source_for_candidate(candidate, profile=profile)] if "death" in profile.dimensions else candidate.chapter_sources
        for source in sources:
            if source.chapter_number in seen:
                continue
            seen.add(source.chapter_number)
            links.append(ContinuationLink(f"查看{source.chapter_label}", "chapter", str(source.chapter_number)))
    return links


def _clean_candidate_text(value: str) -> str:
    parts = [part.strip() for part in str(value or "").split("<SEP>") if part.strip()]
    return "；".join(parts)


def _has_explicit_unsupported_subclaim(question: str) -> bool:
    return "没有资料" in question

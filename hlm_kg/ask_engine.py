from __future__ import annotations

import re
from dataclasses import dataclass, replace
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
from hlm_kg.evidence_adapter import EvidenceCandidate, normalize_query_data_response
from hlm_kg.evidence_judge import EvidenceContract, EvidenceJudge, EvidenceJudgment
from hlm_kg.entity_resolver import EntityResolver, ResolvedEntity
from hlm_kg.question_planner import QUESTION_FILLER_CHARS, QuestionPlanner, SemanticQuestionAnalyzer


OUT_OF_SCOPE_TERMS = ("作文", "现实", "八卦", "数学", "英语")
MAX_RETRIEVAL_EVIDENCE = 3
MAX_LOCAL_EVIDENCE_CANDIDATES = 8
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
DEATH_SOURCE_TITLE_MARKERS = ("死", "亡", "寿终", "焚稿", "魂归", "病", "临终", "绝粒", "殉情")
TERMINAL_CHRONOLOGY_ORIGINAL_MARKERS = (
    "回光返照",
    "喉间",
    "享年",
    "牙关",
    "合眼",
    "睁着",
    "去了",
    "寿终",
    "临终",
    "去世",
    "死亡",
    "咽气",
    "气绝",
)
AGE_EXPRESSION_RE = re.compile(
    r"(?:年方|年已|年约|年过)?[一二三四五六七八九十百千万两\d]+(?:来|多|余)?岁|"
    r"大[一二三四五六七八九十百千万两\d]+岁"
)
HEALTH_CONDITION_RE = re.compile(
    r"(?:有|抱|患|生|得|染|带来|带了)?"
    r"(?P<condition>[^，。；：、“”\"']{0,12}(?:之症|症|之疾|疾|热毒|痨病|痨症))"
)


@dataclass(frozen=True)
class QuestionProfile:
    subject_terms: tuple[str, ...]
    subject_clues: tuple[str, ...]
    dimensions: frozenset[str]
    question_focus: str = ""
    required_evidence: tuple[str, ...] = ()
    evidence_terms: tuple[str, ...] = ()
    retrieval_queries: tuple[str, ...] = ()
    answer_shape: str = "explanatory"
    first_mention: bool = False


class AskEngine:
    def __init__(
        self,
        store: ContentStore,
        semantic_analyzer: SemanticQuestionAnalyzer | None = None,
        evidence_judge: EvidenceJudge | None = None,
    ) -> None:
        self.store = store
        self.question_planner = QuestionPlanner(EntityResolver(store), semantic_analyzer=semantic_analyzer)
        self.evidence_judge = evidence_judge

    def ask(self, question: str, retrieval_client: Any | None = None) -> AskAnswer:
        if any(term in question for term in OUT_OF_SCOPE_TERMS):
            return self._refuse(question, "OUT_OF_SCOPE", "当前产品只支持《红楼梦》阅读理解相关问题。")

        if retrieval_client is not None:
            return self._answer_from_retrieval(question, retrieval_client)

        profile = self._question_profile(question)
        if self.evidence_judge is not None:
            local_candidates = self._original_text_candidates(question, profile)
            local_candidates = self._judged_supporting_candidates(question, local_candidates, profile)
            if local_candidates:
                return self._candidate_evidence_answer(question, local_candidates, profile=profile)

        return self._refuse(question, "NO_EVIDENCE", "当前资料中没有找到足够依据回答这个问题。")

    def _answer_from_retrieval(self, question: str, retrieval_client: Any) -> AskAnswer:
        profile = self._question_profile(question)
        if self.evidence_judge is not None and _should_try_local_before_retrieval(profile):
            local_candidates = self._original_text_candidates(question, profile)
            local_candidates = self._judged_supporting_candidates(question, local_candidates, profile)
            if local_candidates:
                return self._candidate_evidence_answer(question, local_candidates, profile=profile)

        try:
            responses = [retrieval_client.query_data(question, mode="hybrid", only_need_context=True)]
        except Exception:  # noqa: BLE001 - retrieval failure should not expose internals to students
            return self._refuse(question, "GRAPH_UNAVAILABLE", "关系线索暂时不可用，当前不能生成可靠回答。")

        candidates = [
            candidate
            for response in responses
            for candidate in normalize_query_data_response(response, question=question)
        ]
        if "chapter_location" in profile.dimensions:
            chapter_candidates = _chapter_location_candidates(candidates)
            if _has_conflicting_chapters(chapter_candidates):
                return self._refuse(question, "SOURCE_CONFLICT", "资料存在不一致，优先查看原文依据。")
            candidate = chapter_candidates[0] if chapter_candidates else None
            if candidate is None:
                return self._refuse(question, "NO_EVIDENCE", "当前资料中没有找到足够依据回答这个问题。")
            return self._chapter_location_answer(question, candidate)

        supported_candidates = _rank_candidates_for_profile(_supporting_candidates(candidates, profile=profile), profile)
        if self.evidence_judge is not None:
            judged_retrieval_candidates = self._judged_supporting_candidates(question, supported_candidates, profile)
            if judged_retrieval_candidates:
                if _requires_original_verification(profile, judged_retrieval_candidates):
                    preferred_chapters = [
                        source.chapter_number
                        for candidate in judged_retrieval_candidates
                        for source in candidate.chapter_sources
                    ]
                    original_text_candidates = self._original_text_candidates(
                        question,
                        profile,
                        preferred_chapters=preferred_chapters,
                    )
                    supported_candidates = self._judged_supporting_candidates(question, original_text_candidates, profile)
                else:
                    supported_candidates = judged_retrieval_candidates
            else:
                preferred_chapters = [
                    source.chapter_number
                    for candidate in supported_candidates
                    for source in candidate.chapter_sources
                ]
                original_text_candidates = self._original_text_candidates(
                    question,
                    profile,
                    preferred_chapters=preferred_chapters,
                )
                supported_candidates = self._judged_supporting_candidates(question, original_text_candidates, profile)
        if not supported_candidates:
            return self._refuse(question, "NO_EVIDENCE", "当前资料中没有找到足够依据回答这个问题。")

        return self._candidate_evidence_answer(question, supported_candidates, profile=profile)

    def _question_profile(self, question: str) -> QuestionProfile:
        return _question_profile(question, self.store, planner=self.question_planner)

    def _judged_supporting_candidates(
        self,
        question: str,
        candidates: list[EvidenceCandidate],
        profile: QuestionProfile,
    ) -> list[EvidenceCandidate]:
        if self.evidence_judge is None:
            return candidates
        contract = EvidenceContract(
            question=question,
            subject_terms=profile.subject_terms,
            question_focus=profile.question_focus,
            required_evidence=profile.required_evidence,
            answer_shape=profile.answer_shape,
        )
        supported: list[EvidenceCandidate] = []
        for candidate in _rank_candidates_for_profile(candidates, profile)[:8]:
            try:
                judgment = self.evidence_judge.judge(candidate, contract)
            except Exception:  # noqa: BLE001 - judging is advisory; unsupported is safer than hallucination
                continue
            if judgment.supported and (judgment.answer_text or judgment.evidence_text):
                supported.append(_candidate_with_judgment(candidate, judgment))
                if "terminal_chronology" not in profile.dimensions:
                    break
        if "terminal_chronology" in profile.dimensions:
            return sorted(supported, key=_candidate_terminal_source_order, reverse=True)[:1]
        return supported

    def _original_text_candidates(
        self,
        question: str,
        profile: QuestionProfile,
        *,
        answer_hints: list[str] | None = None,
        preferred_chapters: list[int] | None = None,
    ) -> list[EvidenceCandidate]:
        if "terminal_chronology" in profile.dimensions:
            return self._terminal_original_text_candidates(profile, preferred_chapters=preferred_chapters)
        if not profile.subject_terms or not profile.evidence_terms:
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
            matches = _find_focus_evidence_spans(text, profile)
            if not matches and profile.first_mention:
                age_match = _find_attributed_age(text, profile)
                if age_match is not None:
                    matches = [age_match]
            if not matches and (hint_match := _find_age_answer_hint(text, answer_hints)) is not None:
                matches = [hint_match]
            if not matches:
                continue
            source = _chapter_source_for_chapter(chapter)
            for match in matches:
                span = match.span()
                description = _text_window_around_span(text, span, radius=260)
                if any(candidate.description == description for candidate in candidates):
                    continue
                candidates.append(
                    EvidenceCandidate(
                        kind="chunk",
                        title=f"{source.chapter_label}：{source.chapter_title}",
                        description=description,
                        query_mode="original_text",
                        file_paths=[chapter.original_text_path],
                        source_ids=[],
                        chapter_sources=[source],
                        raw={},
                        score=(1000 - chapter_number) + _focus_window_score(description, profile),
                    )
                )
            if profile.first_mention or len(candidates) >= MAX_LOCAL_EVIDENCE_CANDIDATES:
                break
        return sorted(candidates, key=lambda candidate: candidate.score, reverse=True)[:MAX_LOCAL_EVIDENCE_CANDIDATES]

    def _terminal_original_text_candidates(
        self,
        profile: QuestionProfile,
        *,
        preferred_chapters: list[int] | None = None,
    ) -> list[EvidenceCandidate]:
        if not profile.subject_terms:
            return []

        candidates: list[EvidenceCandidate] = []
        for chapter_number in _terminal_chapter_scan_order(self.store, preferred_chapters):
            try:
                chapter = self.store.chapter(chapter_number)
                text = self.store.chapter_text(chapter_number)
            except KeyError:
                continue
            source = _chapter_source_for_chapter(chapter)
            title_text = f"{source.chapter_label}{source.chapter_title}"
            title_has_terminal_marker = any(marker in title_text for marker in DEATH_SOURCE_TITLE_MARKERS)
            matches = _find_terminal_subject_spans(text, profile, title_has_terminal_marker=title_has_terminal_marker)
            for match in matches:
                description = _text_window_around_span(text, match.span(), radius=360)
                if any(candidate.description == description for candidate in candidates):
                    continue
                candidates.append(
                    EvidenceCandidate(
                        kind="chunk",
                        title=f"{source.chapter_label}：{source.chapter_title}",
                        description=description,
                        query_mode="original_text",
                        file_paths=[chapter.original_text_path],
                        source_ids=[],
                        chapter_sources=[source],
                        raw={},
                        score=_terminal_original_window_score(description, source, profile),
                    )
                )
        return sorted(candidates, key=lambda candidate: candidate.score, reverse=True)[:MAX_LOCAL_EVIDENCE_CANDIDATES]

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
    if "health" in profile.dimensions:
        supported = [candidate for candidate in supported if _candidate_health_answer(candidate, profile)]
    return supported


def _requires_original_verification(profile: QuestionProfile, candidates: list[EvidenceCandidate]) -> bool:
    if "terminal_chronology" not in profile.dimensions:
        return False
    return any(candidate.kind in {"relationship", "entity"} for candidate in candidates)


def _should_try_local_before_retrieval(profile: QuestionProfile) -> bool:
    return profile.first_mention or bool(profile.dimensions & {"age", "health", "terminal_chronology"})


def _rank_candidates_for_profile(candidates: list[EvidenceCandidate], profile: QuestionProfile) -> list[EvidenceCandidate]:
    return sorted(candidates, key=lambda candidate: _candidate_contract_score(candidate, profile), reverse=True)


def _candidate_contract_score(candidate: EvidenceCandidate, profile: QuestionProfile) -> tuple[int, int, int]:
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
    terms = _contract_evidence_terms(profile)
    coverage = sum(1 for term in terms if term and term in text)
    weighted_coverage = sum(len(term) for term in terms if term and term in text)
    subject_coverage = sum(1 for term in profile.subject_terms if term and term in text)
    terminal_order = _candidate_terminal_source_order(candidate) if "terminal_chronology" in profile.dimensions else 0
    return (coverage * 100 + weighted_coverage * 10 + subject_coverage * 20, terminal_order, candidate.score)


def _candidate_terminal_source_order(candidate: EvidenceCandidate) -> int:
    if not candidate.chapter_sources:
        return 0
    return max(source.chapter_number for source in candidate.chapter_sources)


def _contract_evidence_terms(profile: QuestionProfile) -> tuple[str, ...]:
    text = "\n".join(
        [
            profile.question_focus,
            "\n".join(profile.required_evidence),
            "\n".join(profile.evidence_terms),
        ]
    )
    for term in profile.subject_terms:
        if term:
            text = text.replace(term, " ")
    terms: list[str] = []
    for match in re.finditer(r"[\u4e00-\u9fff]+|[A-Za-z0-9_]+", text):
        run = match.group(0)
        if re.fullmatch(r"[A-Za-z0-9_]+", run):
            if len(run) >= 2:
                _append_unique(terms, run)
            continue
        compact = "".join(char for char in run if char not in QUESTION_FILLER_CHARS)
        if len(compact) >= 2:
            _append_unique(terms, compact)
        for width in (4, 3, 2):
            if len(run) < width:
                continue
            for index in range(0, len(run) - width + 1):
                gram = "".join(char for char in run[index:index + width] if char not in QUESTION_FILLER_CHARS)
                if len(gram) >= 2:
                    _append_unique(terms, gram)
    return tuple(terms[:32])


def _candidate_with_judgment(candidate: EvidenceCandidate, judgment: EvidenceJudgment) -> EvidenceCandidate:
    raw = dict(candidate.raw) if isinstance(candidate.raw, dict) else {}
    raw["judged_answer_text"] = judgment.answer_text
    raw["judged_evidence_text"] = judgment.evidence_text
    raw["judged_claim_type"] = judgment.claim_type
    return replace(candidate, raw=raw)


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


def _question_profile(question: str, store: Any | None = None, *, planner: QuestionPlanner | None = None) -> QuestionProfile:
    plan = planner.plan(question) if planner is not None else QuestionPlanner(EntityResolver(store)).plan(question) if store is not None else None
    dimensions = _dimensions_from_plan(plan)
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

    return QuestionProfile(
        subject_terms=tuple(subject_terms),
        subject_clues=tuple(subject_clues),
        dimensions=frozenset(dimensions),
        question_focus=str(getattr(plan, "question_focus", "") or "") if plan is not None else "",
        required_evidence=tuple(getattr(plan, "required_evidence", ()) or ()) if plan is not None else (),
        evidence_terms=tuple(getattr(plan, "evidence_terms", ()) or ()) if plan is not None else (),
        retrieval_queries=tuple(getattr(plan, "retrieval_queries", ()) or ()) if plan is not None else (),
        answer_shape=str(getattr(plan, "answer_shape", "") or "explanatory") if plan is not None else "explanatory",
        first_mention=bool(plan is not None and "first_mention" in getattr(plan, "constraints", ())),
    )


def _dimensions_from_plan(plan: Any | None) -> set[str]:
    if plan is None:
        return set()
    dimensions: set[str] = set()
    focus_text = str(getattr(plan, "question_focus", "") or "")
    required_text = "\n".join(str(item) for item in getattr(plan, "required_evidence", ()) or ())
    constraints_text = "\n".join(str(item) for item in getattr(plan, "constraints", ()) or ())
    contract_text = "\n".join(
        [
            focus_text,
            required_text,
            constraints_text,
        ]
    )
    constraints = {str(item) for item in getattr(plan, "constraints", ()) or ()}
    if constraints & {"final_in_sequence", "time_bound_before_death"} or (
        any(marker in contract_text for marker in ("时序终点", "最后被记录", "最后完成", "最后实施"))
        and any(marker in contract_text for marker in ("去世前", "临终", "生前"))
    ):
        dimensions.add("terminal_chronology")
    if any(term in contract_text for term in ("章回", "第几回", "哪一回", "发生或出现")):
        dimensions.add("chapter_location")
    if any(term in contract_text for term in ("死亡", "死因", "去世", "临终", "魂归", "绝粒", "急怒攻心")):
        dimensions.add("death")
    if any(term in focus_text for term in ("年龄", "年纪", "几岁", "多大", "岁")):
        dimensions.add("age")
    if any(term in focus_text for term in ("病症", "疾病", "身体状况", "长期服药", "病情", "患病")):
        dimensions.add("health")
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


def _find_focus_evidence_spans(text: str, profile: QuestionProfile) -> list[re.Match[str]]:
    matches: list[re.Match[str]] = []
    for term in _local_evidence_terms(profile):
        if not term:
            continue
        for match in re.finditer(re.escape(term), text):
            window = _text_window_around_span(text, match.span(), radius=260)
            if _text_mentions_profile_subject(window, profile):
                matches.append(match)
    return matches


def _find_terminal_subject_spans(
    text: str,
    profile: QuestionProfile,
    *,
    title_has_terminal_marker: bool,
) -> list[re.Match[str]]:
    matches: list[re.Match[str]] = []
    for term in profile.subject_terms:
        if not term:
            continue
        for match in re.finditer(re.escape(term), text):
            window = _text_window_around_span(text, match.span(), radius=360)
            if title_has_terminal_marker or _window_has_terminal_marker(window):
                matches.append(match)
    return matches


def _window_has_terminal_marker(window: str) -> bool:
    return any(marker in window for marker in TERMINAL_CHRONOLOGY_ORIGINAL_MARKERS)


def _focus_window_score(window: str, profile: QuestionProfile) -> int:
    score = 0
    score += 30 * sum(1 for term in _local_evidence_terms(profile) if term and term in window)
    score += 20 * sum(1 for term in profile.subject_terms if term and term in window)
    return score


def _terminal_original_window_score(window: str, source: ChapterSource, profile: QuestionProfile) -> int:
    subject_score = 20 * sum(1 for term in profile.subject_terms if term and term in window)
    marker_score = 40 * sum(1 for marker in TERMINAL_CHRONOLOGY_ORIGINAL_MARKERS if marker in window)
    title_text = f"{source.chapter_label}{source.chapter_title}"
    title_score = 200 if any(marker in title_text for marker in DEATH_SOURCE_TITLE_MARKERS) else 0
    return source.chapter_number * 100 + title_score + marker_score + subject_score


def _local_evidence_terms(profile: QuestionProfile) -> tuple[str, ...]:
    subject_terms = {term for term in profile.subject_terms if term}
    return tuple(term for term in profile.evidence_terms if term and term not in subject_terms)


def _terminal_chapter_scan_order(store: Any, preferred_chapters: list[int] | None = None) -> list[int]:
    ordered: list[int] = []

    def append_chapter(chapter_number: int) -> None:
        if 1 <= chapter_number <= 120 and chapter_number not in ordered:
            ordered.append(chapter_number)

    for chapter_number in range(120, 0, -1):
        try:
            chapter = store.chapter(chapter_number)
        except KeyError:
            continue
        title_text = f"第{int(chapter.number)}回{chapter.title}"
        if any(marker in title_text for marker in DEATH_SOURCE_TITLE_MARKERS):
            append_chapter(chapter_number)
    for chapter_number in preferred_chapters or []:
        append_chapter(int(chapter_number))
    for chapter_number in range(120, 0, -1):
        append_chapter(chapter_number)
    return ordered


def _find_attributed_health_condition(text: str, profile: QuestionProfile) -> tuple[tuple[int, int], str] | None:
    for match in HEALTH_CONDITION_RE.finditer(text):
        condition = _clean_health_condition(match.group("condition"))
        if not condition:
            continue
        if _health_condition_is_attributed_to_subject(text, match, profile):
            return match.span(), condition
    return None


def _health_condition_is_attributed_to_subject(text: str, match: re.Match[str], profile: QuestionProfile) -> bool:
    start, end = match.span()
    before = text[max(0, start - 240):start]
    after = text[end:min(len(text), end + 160)]
    return any(term in before or term in after for term in profile.subject_terms)


def _clean_health_condition(value: str | None) -> str:
    condition = str(value or "").strip()
    condition = _condition_after_health_predicate(condition)
    condition = condition.lstrip("有抱患生得染")
    if not condition:
        return ""
    if condition in {"病", "病情", "病根"}:
        return ""
    if "之病" in condition and not any(marker in condition for marker in ("之症", "之疾")):
        return ""
    return condition


def _condition_after_health_predicate(condition: str) -> str:
    for marker in ("带来", "带了", "有", "患", "抱", "生", "得", "染"):
        marker_index = condition.rfind(marker)
        if marker_index < 0:
            continue
        candidate = condition[marker_index + len(marker):].strip()
        candidate = candidate.lstrip("的一股些个种")
        if _looks_like_health_condition(candidate):
            return candidate
    return condition


def _looks_like_health_condition(condition: str) -> bool:
    return (
        re.fullmatch(r"[^，。；：、“”\"']{1,12}(?:之症|症|之疾|疾|热毒|痨病|痨症)", condition)
        is not None
    )


def _chapter_scan_order(preferred_chapters: list[int] | None = None) -> list[int]:
    ordered: list[int] = []
    for chapter in preferred_chapters or []:
        if 1 <= chapter <= 120 and chapter not in ordered:
            ordered.append(chapter)
    ordered.extend(chapter for chapter in range(1, 121) if chapter not in ordered)
    return ordered


def _candidate_age_answer(candidate: EvidenceCandidate, profile: QuestionProfile) -> str | None:
    raw_answer = candidate.raw.get("answer_text") if isinstance(candidate.raw, dict) else None
    if isinstance(raw_answer, str) and raw_answer and candidate.raw.get("answer_dimension") == "age":
        return raw_answer
    if isinstance(candidate.raw, dict) and candidate.raw.get("answer_dimension") is not None:
        return None
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


def _candidate_health_answer(candidate: EvidenceCandidate, profile: QuestionProfile) -> str | None:
    raw_answer = candidate.raw.get("answer_text") if isinstance(candidate.raw, dict) else None
    if isinstance(raw_answer, str) and raw_answer and candidate.raw.get("answer_dimension") == "health_condition":
        return raw_answer
    text = _clean_candidate_text(f"{candidate.description}<SEP>{candidate.relationship_keywords or ''}")
    segments = _candidate_text_segments(text)
    focused_segments = [
        segment
        for segment in segments
        if _segment_references_subject(segment, profile) and _segment_health_condition(segment)
    ]
    if not focused_segments:
        return None
    return "；".join(_dedupe_preserve_order(focused_segments[:2]))


def _candidate_health_condition(candidate: EvidenceCandidate, profile: QuestionProfile) -> str | None:
    health_answer = _candidate_health_answer(candidate, profile)
    if not health_answer:
        return None
    if isinstance(candidate.raw, dict) and candidate.raw.get("answer_dimension") == "health_condition":
        return health_answer
    condition = _segment_health_condition(health_answer)
    return condition or health_answer


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


def _segment_health_condition(segment: str) -> str | None:
    for match in HEALTH_CONDITION_RE.finditer(segment):
        condition = _clean_health_condition(match.group("condition"))
        if condition:
            return condition
    return None


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
    if profile is not None and "terminal_chronology" in profile.dimensions:
        terminal_sources = [
            source
            for source in candidate.chapter_sources
            if any(marker in f"{source.chapter_label}{source.chapter_title}" for marker in DEATH_SOURCE_TITLE_MARKERS)
        ]
        if terminal_sources:
            return max(terminal_sources, key=lambda source: source.chapter_number)
        if candidate.chapter_sources:
            return max(candidate.chapter_sources, key=lambda source: source.chapter_number)
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
    judged_evidence_text = _judged_raw_text(candidate, "judged_evidence_text")
    if judged_evidence_text:
        return judged_evidence_text
    if profile is not None and "death" in profile.dimensions:
        death_answer = _candidate_death_answer(candidate, profile)
        if death_answer:
            return death_answer
    if profile is not None and "health" in profile.dimensions:
        if isinstance(candidate.raw, dict) and candidate.raw.get("answer_dimension") == "health_condition":
            return candidate.description or candidate.title
        health_answer = _candidate_health_answer(candidate, profile)
        if health_answer:
            return health_answer
    return candidate.description or candidate.title


def _source_type_for_candidate(candidate: EvidenceCandidate) -> str:
    if candidate.kind in {"relationship", "entity"}:
        return "graph_relation"
    if candidate.kind == "chunk":
        return "original_text"
    return "processed_material"


def _claim_type_for_candidate(candidate: EvidenceCandidate, *, profile: QuestionProfile | None = None) -> str:
    judged_claim_type = _judged_raw_text(candidate, "judged_claim_type")
    if judged_claim_type:
        return judged_claim_type
    if isinstance(candidate.raw, dict) and candidate.raw.get("answer_dimension") in {"age", "health_condition"}:
        return "quotable_fact"
    if profile is not None and "health" in profile.dimensions:
        return "quotable_fact"
    if profile is not None and "death" in profile.dimensions:
        return "event_causality"
    if candidate.kind in {"relationship", "entity"}:
        return "identity_relation"
    return "plot_summary"


def _student_safe_candidate_conclusion(candidate: EvidenceCandidate, *, profile: QuestionProfile) -> str:
    judged_answer_text = _judged_raw_text(candidate, "judged_answer_text")
    if judged_answer_text:
        return f"根据可回溯资料，{judged_answer_text}"
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
    if "health" in profile.dimensions:
        health_condition = _candidate_health_condition(candidate, profile)
        if health_condition:
            subject = _primary_subject_label(profile)
            return f"根据可回溯资料，{subject}的病症线索是“{health_condition}”。这是文本中的说法，不宜直接改写成现代医学诊断。"
    description = _clean_candidate_text(candidate.description)
    if description:
        return f"根据可回溯资料，{description}"
    return f"根据可回溯资料，可以定位到“{candidate.title}”。"


def _student_safe_evidence_explanation(candidate: EvidenceCandidate, *, profile: QuestionProfile) -> str:
    source = _source_for_candidate(candidate, profile=profile)
    topic = _clean_candidate_text(candidate.title)
    judged_evidence_text = _judged_raw_text(candidate, "judged_evidence_text")
    if judged_evidence_text:
        return f"{source.chapter_label}《{source.chapter_title}》的资料说明：{judged_evidence_text}"
    if "death" in profile.dimensions:
        death_answer = _candidate_death_answer(candidate, profile)
        if death_answer:
            return f"{source.chapter_label}《{source.chapter_title}》的资料说明：{death_answer}"
    if "health" in profile.dimensions:
        health_condition = _candidate_health_condition(candidate, profile)
        if health_condition:
            subject = _primary_subject_label(profile)
            return f"{source.chapter_label}《{source.chapter_title}》的资料提供了{subject}“{health_condition}”这一病症线索。"
    description = _clean_candidate_text(candidate.description)
    if description:
        return f"{source.chapter_label}《{source.chapter_title}》的资料说明：{description}"
    return f"{source.chapter_label}《{source.chapter_title}》提供了“{topic}”的相关依据。"


def _quotable_fact_from_candidate(candidate: EvidenceCandidate, *, profile: QuestionProfile) -> str:
    source = _source_for_candidate(candidate, profile=profile)
    judged_evidence_text = _judged_raw_text(candidate, "judged_evidence_text")
    if judged_evidence_text:
        return f"第{source.chapter_number}回：{judged_evidence_text}"
    if isinstance(candidate.raw, dict) and candidate.raw.get("answer_dimension") == "age":
        answer_text = str(candidate.raw.get("answer_text") or "").strip()
        if answer_text:
            return f"第{source.chapter_number}回：原文提供“{answer_text}”这一年龄线索。"
    if "health" in profile.dimensions:
        health_condition = _candidate_health_condition(candidate, profile)
        if health_condition:
            return f"第{source.chapter_number}回：资料提供“{health_condition}”这一病症线索。"
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


def _judged_raw_text(candidate: EvidenceCandidate, key: str) -> str:
    if not isinstance(candidate.raw, dict):
        return ""
    return str(candidate.raw.get(key) or "").strip()


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

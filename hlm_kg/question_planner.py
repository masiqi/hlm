from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from hlm_kg.entity_resolver import EntityResolver, ResolvedEntity


ANSWER_SHAPES = {"short_direct", "explanatory"}
QUESTION_FILLER_CHARS = frozenset("的了呢吗么什哪几多少大是有在和与及或请问一下个这那其何怎如为")


@dataclass(frozen=True)
class QuestionPlan:
    raw_question: str
    subjects: tuple[ResolvedEntity, ...]
    intent: str
    question_focus: str
    constraints: tuple[str, ...]
    answer_shape: str
    required_evidence: tuple[str, ...]
    evidence_terms: tuple[str, ...]
    retrieval_queries: tuple[str, ...]

    @property
    def subject_terms(self) -> tuple[str, ...]:
        terms: list[str] = []
        for subject in self.subjects:
            for term in (subject.canonical_name, *subject.aliases):
                if term and term not in terms:
                    terms.append(term)
        return tuple(terms)


@dataclass(frozen=True)
class QuestionSemantics:
    question_focus: str | None = None
    evidence_terms: tuple[str, ...] = ()
    required_evidence: tuple[str, ...] = ()
    retrieval_queries: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    intent: str | None = None
    answer_shape: str | None = None
    subject_type_hint: str | None = None


class SemanticQuestionAnalyzer(Protocol):
    def analyze(self, question: str, *, subjects: tuple[ResolvedEntity, ...]) -> QuestionSemantics:
        """Return structured question semantics without generating factual answers."""


class QuestionPlanner:
    def __init__(self, resolver: EntityResolver, semantic_analyzer: SemanticQuestionAnalyzer | None = None) -> None:
        self.resolver = resolver
        self.semantic_analyzer = semantic_analyzer

    def plan(self, question: str) -> QuestionPlan:
        raw_question = str(question or "").strip()
        mentions = self.resolver.mentions_in_text(raw_question)
        preliminary_subjects = _resolve_mentions(self.resolver, mentions, raw_question, preferred_type=None)
        semantics = _analyze_question(self.semantic_analyzer, raw_question, preliminary_subjects)
        subject_type_hint = _normalize_subject_type_hint(semantics.subject_type_hint)
        subjects = _resolve_mentions(self.resolver, mentions, raw_question, preferred_type=subject_type_hint)
        constraints = _normalize_constraints(semantics.constraints)
        question_focus = _normalize_optional_text(semantics.question_focus)
        evidence_terms = _question_evidence_terms(raw_question, subjects)
        intent = _normalize_intent(semantics.intent)
        answer_shape = _normalize_answer_shape(semantics.answer_shape)
        return QuestionPlan(
            raw_question=raw_question,
            subjects=subjects,
            intent=intent,
            question_focus=question_focus,
            constraints=constraints,
            answer_shape=answer_shape,
            required_evidence=_required_evidence(subjects, semantics.required_evidence, question_focus),
            evidence_terms=evidence_terms,
            retrieval_queries=(),
        )


def _resolve_mentions(
    resolver: EntityResolver,
    mentions: tuple[str, ...],
    question: str,
    *,
    preferred_type: str | None,
) -> tuple[ResolvedEntity, ...]:
    return tuple(
        resolved
        for mention in mentions
        if (
            resolved := resolver.resolve_mention(
                mention,
                context_text=question,
                preferred_type=preferred_type,
            )
        ).confidence
        != "unresolved"
    )


def _analyze_question(
    semantic_analyzer: SemanticQuestionAnalyzer | None,
    question: str,
    subjects: tuple[ResolvedEntity, ...],
) -> QuestionSemantics:
    if semantic_analyzer is None:
        return QuestionSemantics()
    try:
        return semantic_analyzer.analyze(question, subjects=subjects)
    except Exception:  # noqa: BLE001 - question understanding is advisory; evidence generation must degrade safely
        return QuestionSemantics()


def _normalize_constraints(values: tuple[str, ...]) -> tuple[str, ...]:
    return _normalize_string_tuple(values)


def _normalize_subject_type_hint(value: str | None) -> str | None:
    clean = str(value or "").strip()
    return clean if clean in {"person", "place", "object", "event", "literary_text", "concept"} else None


def _normalize_intent(value: str | None) -> str:
    clean = str(value or "").strip()
    if clean:
        return clean
    return "ask_fact"


def _normalize_answer_shape(value: str | None) -> str:
    clean = str(value or "").strip()
    if clean in ANSWER_SHAPES:
        return clean
    return "explanatory"


def _required_evidence(
    subjects: tuple[ResolvedEntity, ...],
    semantic_requirements: tuple[str, ...],
    question_focus: str,
) -> tuple[str, ...]:
    requirements: list[str] = []
    for subject in subjects:
        label = subject.canonical_name or subject.mention
        requirements.append(f"evidence must refer to {label} or its aliases")
    if question_focus:
        requirements.append(f"evidence must directly answer this focus: {question_focus}")
    for requirement in _normalize_string_tuple(semantic_requirements):
        if requirement not in requirements:
            requirements.append(requirement)
    return tuple(requirements)


def _normalize_optional_text(value: str | None) -> str:
    return str(value or "").strip()


def _normalize_string_tuple(values: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        clean = str(value or "").strip()
        if clean and clean not in normalized:
            normalized.append(clean)
    return tuple(normalized)


def _question_evidence_terms(question: str, subjects: tuple[ResolvedEntity, ...]) -> tuple[str, ...]:
    text = str(question or "")
    for subject in subjects:
        for term in (subject.canonical_name, subject.mention, *subject.aliases):
            clean = str(term or "").strip()
            if clean:
                text = text.replace(clean, " ")

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
        if len(compact) == 1:
            _append_unique(terms, compact)
        elif compact:
            _append_unique(terms, compact[-1])
    return tuple(terms[:16])


def _append_unique(items: list[str], value: str) -> None:
    clean = str(value or "").strip()
    if clean and clean not in items:
        items.append(clean)

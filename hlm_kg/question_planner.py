from __future__ import annotations

from dataclasses import dataclass

from hlm_kg.entity_resolver import EntityResolver, ResolvedEntity


AGE_QUESTION_TERMS = ("几岁", "多大", "年龄", "岁数", "年纪")
DEATH_QUESTION_TERMS = ("怎么死", "怎样死", "如何死", "死因", "为什么死", "为何而死", "因何而死", "去世", "死亡")
FIRST_MENTION_TERMS = ("第一次", "首次", "初次", "最早", "起初", "开头", "开始")
IDENTITY_TERMS = ("是什么", "是谁", "同一个", "同一")


@dataclass(frozen=True)
class QuestionPlan:
    raw_question: str
    subjects: tuple[ResolvedEntity, ...]
    intent: str
    target_property: str | None
    constraints: tuple[str, ...]
    answer_shape: str
    required_evidence: tuple[str, ...]

    @property
    def subject_terms(self) -> tuple[str, ...]:
        terms: list[str] = []
        for subject in self.subjects:
            for term in (subject.canonical_name, *subject.aliases):
                if term and term not in terms:
                    terms.append(term)
        return tuple(terms)


class QuestionPlanner:
    def __init__(self, resolver: EntityResolver) -> None:
        self.resolver = resolver

    def plan(self, question: str) -> QuestionPlan:
        raw_question = str(question or "").strip()
        subjects = tuple(
            resolved
            for mention in self.resolver.mentions_in_text(raw_question)
            if (resolved := self.resolver.resolve_mention(mention, context_text=raw_question)).confidence != "unresolved"
        )
        target_property = _target_property(raw_question)
        constraints = _constraints(raw_question)
        intent = _intent_for_property(target_property)
        answer_shape = "short_direct" if target_property in {"age", "death_cause_or_process"} else "explanatory"
        return QuestionPlan(
            raw_question=raw_question,
            subjects=subjects,
            intent=intent,
            target_property=target_property,
            constraints=constraints,
            answer_shape=answer_shape,
            required_evidence=_required_evidence(subjects, target_property),
        )


def _target_property(question: str) -> str | None:
    if any(term in question for term in AGE_QUESTION_TERMS):
        return "age"
    if any(term in question for term in DEATH_QUESTION_TERMS):
        return "death_cause_or_process"
    if any(term in question for term in IDENTITY_TERMS):
        return "identity_or_definition"
    return None


def _constraints(question: str) -> tuple[str, ...]:
    constraints: list[str] = []
    if any(term in question for term in FIRST_MENTION_TERMS):
        constraints.append("first_mention")
    return tuple(constraints)


def _intent_for_property(target_property: str | None) -> str:
    if target_property == "identity_or_definition":
        return "ask_identity"
    return "ask_fact"


def _required_evidence(subjects: tuple[ResolvedEntity, ...], target_property: str | None) -> tuple[str, ...]:
    requirements: list[str] = []
    for subject in subjects:
        label = subject.canonical_name or subject.mention
        requirements.append(f"evidence must refer to {label} or its aliases")
    if target_property == "death_cause_or_process":
        requirements.append("evidence must support death cause, death process, or death conclusion")
    elif target_property == "age":
        requirements.append("evidence must support an attributed age claim")
    elif target_property == "identity_or_definition":
        requirements.append("evidence must support identity, type, or definition")
    return tuple(requirements)

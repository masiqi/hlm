from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


EvidenceSourceType = Literal["original_text", "processed_material", "knowledge_card", "graph_relation"]
EvidenceConfidence = Literal["explicit", "derived", "weak"]
GraphRelationProvenance = Literal["lightrag", "curated"]
KnowledgeCardType = Literal["person", "event", "judgement", "image", "object", "place", "expression"]
TopicCategory = Literal["人物关系", "关键事件", "判词命运", "意象伏笔", "可引用事实"]
AnswerStatus = Literal["answered", "partial", "refused"]
ClaimType = Literal[
    "identity_relation",
    "plot_summary",
    "judgement_destiny",
    "image_foreshadowing",
    "event_causality",
    "quotable_fact",
]
RefusalReason = Literal[
    "NO_EVIDENCE",
    "AMBIGUOUS_ENTITY",
    "GRAPH_UNAVAILABLE",
    "SOURCE_CONFLICT",
    "OUT_OF_SCOPE",
    "UNSUPPORTED_SUBCLAIM",
]


@dataclass(frozen=True)
class Chapter:
    id: str
    number: int
    title: str
    original_text_path: str
    review_card_id: str | None = None
    primary_entity_ids: list[str] = field(default_factory=list)
    primary_event_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProcessedMaterialSource:
    prompt_name: str
    prompt_version: str
    generated_at: str | None = None


@dataclass(frozen=True)
class Evidence:
    id: str
    source_type: EvidenceSourceType
    chapter: int | None
    location: str | None
    quote: str | None
    evidence_text: str
    entity_ids: list[str]
    relation_id: str | None
    confidence: EvidenceConfidence
    provenance: str
    derived_from_ids: list[str] = field(default_factory=list)

    @property
    def can_support_claim(self) -> bool:
        return self.confidence == "explicit"


@dataclass(frozen=True)
class ChapterReviewCard:
    id: str
    chapter: int
    source: ProcessedMaterialSource
    plain_summary: str
    plot_chain: list[str]
    key_events: list[str]
    key_characters: list[str]
    current_chapter_foreshadowing_signals: list[str]
    later_association_relation_ids: list[str]
    quotable_fact_ids: list[str]
    retrieval_tags: list[str]
    understanding_focus: list[str]


@dataclass(frozen=True)
class ChapterAnnotation:
    id: str
    chapter: int
    start_offset: int
    end_offset: int
    surface_text: str
    annotation_type: str
    entity_id: str | None
    relation_id: str | None
    evidence_id: str | None
    display_priority: int


@dataclass(frozen=True)
class TraceItem:
    id: str
    entity_id: str
    chapter: int
    relation_id: str | None
    evidence_id: str | None
    title: str
    description: str
    trace_type: str
    sort_order: int
    importance: int


@dataclass(frozen=True)
class GraphRelation:
    id: str
    subject_id: str
    predicate: str
    object_id: str
    chapters: list[int]
    evidence_ids: list[str]
    provenance: GraphRelationProvenance
    description: str


@dataclass(frozen=True)
class KnowledgeCard:
    id: str
    name: str
    type: KnowledgeCardType
    brief: str
    text_understanding: list[str]
    understanding_angles: list[str]
    graph_relation_ids: list[str]
    evidence_ids: list[str]
    related_card_ids: list[str]

    def __post_init__(self) -> None:
        allowed = {"person", "event", "judgement", "image", "object", "place", "expression"}
        if self.type not in allowed:
            raise ValueError(f"invalid card type: {self.type}")


@dataclass(frozen=True)
class Topic:
    id: str
    title: str
    category: TopicCategory
    description: str
    card_ids: list[str]
    relation_ids: list[str]
    typical_question_patterns: list[str]
    quotable_fact_ids: list[str]
    evidence_ids: list[str]

    def __post_init__(self) -> None:
        allowed = {"人物关系", "关键事件", "判词命运", "意象伏笔", "可引用事实"}
        if self.category not in allowed:
            raise ValueError(f"invalid topic category: {self.category}")


@dataclass(frozen=True)
class AnswerClaim:
    text: str
    evidence_ids: list[str]
    claim_type: ClaimType


@dataclass(frozen=True)
class AnswerSection:
    title: str
    claims: list[AnswerClaim]


@dataclass(frozen=True)
class Refusal:
    reason: RefusalReason
    message: str


@dataclass(frozen=True)
class ContinuationLink:
    label: str
    target_type: Literal["chapter", "card", "topic", "relation"]
    target_id: str


@dataclass(frozen=True)
class AskAnswer:
    id: str
    question: str
    status: AnswerStatus
    short_conclusion: list[AnswerClaim]
    evidence: list[Evidence]
    explanation: list[AnswerSection]
    quotable_facts: AnswerSection | None
    continuation_links: list[ContinuationLink]
    refusal: Refusal | None


@dataclass(frozen=True)
class PromptDefinition:
    name: str
    version: str
    purpose: str
    input_schema: str
    output_schema: str
    evidence_rules: list[str]
    refusal_rules: list[str]
    content_requirements: list[str] = field(default_factory=list)


def validate_answer(answer: AskAnswer) -> None:
    if answer.status == "refused":
        if answer.refusal is None:
            raise ValueError("refused answers require refusal")
        if answer.short_conclusion or answer.explanation or answer.quotable_facts is not None:
            raise ValueError("refused answers must not contain claims")
        return
    if answer.status == "partial":
        if answer.refusal is None or answer.refusal.reason != "UNSUPPORTED_SUBCLAIM":
            raise ValueError("partial answers require UNSUPPORTED_SUBCLAIM refusal")

    claims = list(answer.short_conclusion)
    for section in answer.explanation:
        claims.extend(section.claims)
    if answer.quotable_facts is not None:
        claims.extend(answer.quotable_facts.claims)
    for claim in claims:
        if not claim.evidence_ids:
            raise ValueError(f"claim requires evidence_ids: {claim.text}")
    if answer.status == "partial" and not claims:
        raise ValueError("partial answers require at least one supported claim")

    supportable_ids = _supportable_evidence_ids(answer.evidence)
    for claim in claims:
        missing = [evidence_id for evidence_id in claim.evidence_ids if evidence_id not in supportable_ids]
        if missing:
            raise ValueError(f"claim references unsupported evidence_ids: {missing}")


def _supportable_evidence_ids(evidence_items: list[Evidence]) -> set[str]:
    explicit_ids = {evidence.id for evidence in evidence_items if evidence.can_support_claim}
    supportable_ids = set(explicit_ids)
    for evidence in evidence_items:
        if evidence.confidence != "derived":
            continue
        if any(source_id in explicit_ids for source_id in evidence.derived_from_ids):
            supportable_ids.add(evidence.id)
    return supportable_ids

from __future__ import annotations

from enum import Enum

from hlm_kg.domain import AnswerClaim, Evidence, EvidenceSourceType


class EvidenceDecision(str, Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"


SOURCE_PRIORITIES: dict[EvidenceSourceType, int] = {
    "original_text": 0,
    "graph_relation": 1,
    "processed_material": 2,
    "knowledge_card": 2,
}


def source_priority(source_type: EvidenceSourceType) -> int:
    return SOURCE_PRIORITIES[source_type]


def decide_claim_support(claim: AnswerClaim, evidence_by_id: dict[str, Evidence]) -> EvidenceDecision:
    if not claim.evidence_ids:
        return EvidenceDecision.UNSUPPORTED
    selected = [_resolve_supportable(evidence_id, evidence_by_id) for evidence_id in claim.evidence_ids]
    if any(item is None for item in selected):
        return EvidenceDecision.UNSUPPORTED
    evidence_items = [item for item in selected if item is not None]
    if any(not item.evidence_text.strip() for item in evidence_items):
        return EvidenceDecision.UNSUPPORTED

    if claim.claim_type == "identity_relation":
        has_original_text = any(item.source_type == "original_text" and item.chapter is not None for item in evidence_items)
        return _supported(has_original_text or _has_chaptered_graph_relation(evidence_items))
    if claim.claim_type == "plot_summary":
        return _supported(
            any(item.chapter is not None and item.source_type in {"original_text", "processed_material"} for item in evidence_items)
        )
    if claim.claim_type == "judgement_destiny":
        has_original_text = any(item.source_type == "original_text" and item.chapter is not None for item in evidence_items)
        return _supported(has_original_text and _has_chaptered_graph_relation(evidence_items))
    if claim.claim_type == "image_foreshadowing":
        return _supported(_has_graph_relation(evidence_items) or _distinct_chapters(evidence_items) >= 2)
    if claim.claim_type == "event_causality":
        locatable_count = sum(1 for item in evidence_items if item.chapter is not None)
        return _supported(locatable_count >= 2)
    if claim.claim_type == "quotable_fact":
        return _supported(any(item.confidence == "explicit" for item in evidence_items))
    return EvidenceDecision.UNSUPPORTED


def _resolve_supportable(evidence_id: str, evidence_by_id: dict[str, Evidence]) -> Evidence | None:
    evidence = evidence_by_id.get(evidence_id)
    if evidence is None or evidence.confidence == "weak":
        return None
    if evidence.confidence == "explicit":
        return evidence
    if evidence.confidence == "derived":
        has_explicit_source = any(
            (source := evidence_by_id.get(source_id)) is not None
            and source.confidence == "explicit"
            and source.source_type in {"original_text", "processed_material", "graph_relation"}
            for source_id in evidence.derived_from_ids
        )
        if has_explicit_source:
            return evidence
    return None


def _has_graph_relation(evidence_items: list[Evidence]) -> bool:
    return any(item.source_type == "graph_relation" and item.relation_id and item.chapter is not None for item in evidence_items)


def _has_chaptered_graph_relation(evidence_items: list[Evidence]) -> bool:
    return any(item.source_type == "graph_relation" and item.relation_id and item.chapter is not None for item in evidence_items)


def _distinct_chapters(evidence_items: list[Evidence]) -> int:
    return len({item.chapter for item in evidence_items if item.chapter is not None})


def _supported(value: bool) -> EvidenceDecision:
    return EvidenceDecision.SUPPORTED if value else EvidenceDecision.UNSUPPORTED


def detect_source_conflict(evidence_items: list[Evidence]) -> bool:
    explicit_by_relation: dict[str, set[str]] = {}
    for item in evidence_items:
        if item.confidence != "explicit" or item.relation_id is None:
            continue
        explicit_by_relation.setdefault(item.relation_id, set()).add(item.evidence_text)
    return any(len(texts) > 1 for texts in explicit_by_relation.values())


def supported_claims(claims: list[AnswerClaim], evidence: list[Evidence]) -> list[AnswerClaim]:
    evidence_by_id = {item.id: item for item in evidence}
    return [
        claim
        for claim in claims
        if decide_claim_support(claim, evidence_by_id) is EvidenceDecision.SUPPORTED
    ]

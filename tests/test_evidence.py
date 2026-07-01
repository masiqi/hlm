from hlm_kg.domain import AnswerClaim, Evidence
from hlm_kg.evidence import EvidenceDecision, decide_claim_support, detect_source_conflict, source_priority


def evidence(
    evidence_id: str,
    source_type: str = "original_text",
    chapter: int | None = 27,
    confidence: str = "explicit",
    relation_id: str | None = None,
    derived_from_ids: list[str] | None = None,
    text: str = "第 27 回黛玉葬花并吟《葬花吟》。",
) -> Evidence:
    return Evidence(
        id=evidence_id,
        source_type=source_type,
        chapter=chapter,
        location=f"第 {chapter} 回" if chapter else "全书关系线索",
        quote=None,
        evidence_text=text,
        entity_ids=["card-lindaiyu"],
        relation_id=relation_id,
        confidence=confidence,
        provenance="curated",
        derived_from_ids=derived_from_ids or [],
    )


def test_source_priority_puts_original_text_first():
    assert source_priority("original_text") < source_priority("graph_relation")
    assert source_priority("graph_relation") < source_priority("processed_material")


def test_identity_relation_can_use_one_explicit_source():
    claim = AnswerClaim(
        text="潇湘妃子指林黛玉。",
        evidence_ids=["ev-1"],
        claim_type="identity_relation",
    )

    decision = decide_claim_support(
        claim,
        {"ev-1": evidence("ev-1", source_type="graph_relation", relation_id="rel-alias-lindaiyu")},
    )

    assert decision == EvidenceDecision.SUPPORTED


def test_identity_relation_rejects_processed_material_without_original_or_chaptered_relation():
    claim = AnswerClaim(
        text="潇湘妃子指林黛玉。",
        evidence_ids=["ev-1"],
        claim_type="identity_relation",
    )

    decision = decide_claim_support(claim, {"ev-1": evidence("ev-1", source_type="processed_material")})

    assert decision == EvidenceDecision.UNSUPPORTED


def test_plot_summary_requires_locatable_chapter_material():
    claim = AnswerClaim(
        text="第 27 回写宝钗扑蝶和黛玉葬花。",
        evidence_ids=["ev-1"],
        claim_type="plot_summary",
    )

    decision = decide_claim_support(claim, {"ev-1": evidence("ev-1", source_type="processed_material")})

    assert decision == EvidenceDecision.SUPPORTED


def test_judgement_destiny_rejects_relation_without_original_text():
    claim = AnswerClaim(
        text="葬花可作为理解黛玉命运悲感的关系线索。",
        evidence_ids=["ev-relation"],
        claim_type="judgement_destiny",
    )

    decision = decide_claim_support(
        claim,
        {"ev-relation": evidence("ev-relation", source_type="graph_relation", chapter=None, relation_id="rel-daiyu-fate")},
    )

    assert decision == EvidenceDecision.UNSUPPORTED


def test_judgement_destiny_requires_original_text_and_mapping_relation():
    claim = AnswerClaim(
        text="判词命运解释必须同时有原文和人物映射关系。",
        evidence_ids=["ev-text", "ev-relation"],
        claim_type="judgement_destiny",
    )

    decision = decide_claim_support(
        claim,
        {
            "ev-text": evidence("ev-text", source_type="original_text", chapter=5),
            "ev-relation": evidence("ev-relation", source_type="graph_relation", relation_id="rel-judgement-person"),
        },
    )

    assert decision == EvidenceDecision.SUPPORTED


def test_judgement_destiny_rejects_chapterless_mapping_relation():
    claim = AnswerClaim(
        text="判词命运解释必须有可定位的人物映射关系。",
        evidence_ids=["ev-text", "ev-relation"],
        claim_type="judgement_destiny",
    )

    decision = decide_claim_support(
        claim,
        {
            "ev-text": evidence("ev-text", source_type="original_text", chapter=5),
            "ev-relation": evidence(
                "ev-relation",
                source_type="graph_relation",
                chapter=None,
                relation_id="rel-judgement-person",
            ),
        },
    )

    assert decision == EvidenceDecision.UNSUPPORTED


def test_image_foreshadowing_rejects_single_original_text_evidence():
    claim = AnswerClaim(
        text="葬花和后文黛玉命运有关。",
        evidence_ids=["ev-27"],
        claim_type="image_foreshadowing",
    )

    decision = decide_claim_support(claim, {"ev-27": evidence("ev-27", source_type="original_text")})

    assert decision == EvidenceDecision.UNSUPPORTED


def test_image_foreshadowing_accepts_graph_relation():
    claim = AnswerClaim(
        text="葬花和后文黛玉命运有关。",
        evidence_ids=["ev-relation"],
        claim_type="image_foreshadowing",
    )

    decision = decide_claim_support(
        claim,
        {"ev-relation": evidence("ev-relation", source_type="graph_relation", relation_id="rel-daiyu-fate")},
    )

    assert decision == EvidenceDecision.SUPPORTED


def test_image_foreshadowing_rejects_chapterless_graph_relation():
    claim = AnswerClaim(
        text="葬花和后文黛玉命运有关。",
        evidence_ids=["ev-relation"],
        claim_type="image_foreshadowing",
    )

    decision = decide_claim_support(
        claim,
        {
            "ev-relation": evidence(
                "ev-relation",
                source_type="graph_relation",
                chapter=None,
                relation_id="rel-daiyu-fate",
            )
        },
    )

    assert decision == EvidenceDecision.UNSUPPORTED


def test_image_foreshadowing_accepts_two_distinct_chapter_sources():
    claim = AnswerClaim(
        text="葬花和后文黛玉命运有关。",
        evidence_ids=["ev-27", "ev-98"],
        claim_type="image_foreshadowing",
    )

    decision = decide_claim_support(
        claim,
        {
            "ev-27": evidence("ev-27", source_type="original_text", chapter=27),
            "ev-98": evidence("ev-98", source_type="original_text", chapter=98),
        },
    )

    assert decision == EvidenceDecision.SUPPORTED


def test_event_causality_requires_two_locatable_sources():
    claim = AnswerClaim(
        text="探春整顿事务体现其兴利除弊。",
        evidence_ids=["ev-card"],
        claim_type="event_causality",
    )

    decision = decide_claim_support(claim, {"ev-card": evidence("ev-card", source_type="processed_material")})

    assert decision == EvidenceDecision.UNSUPPORTED


def test_event_causality_rejects_single_graph_relation():
    claim = AnswerClaim(
        text="探春整顿事务体现其兴利除弊。",
        evidence_ids=["ev-relation"],
        claim_type="event_causality",
    )

    decision = decide_claim_support(
        claim,
        {"ev-relation": evidence("ev-relation", source_type="graph_relation", relation_id="rel-tanchun-manages")},
    )

    assert decision == EvidenceDecision.UNSUPPORTED


def test_event_causality_accepts_two_locatable_sources():
    claim = AnswerClaim(
        text="探春整顿事务体现其兴利除弊。",
        evidence_ids=["ev-card", "ev-relation"],
        claim_type="event_causality",
    )

    decision = decide_claim_support(
        claim,
        {
            "ev-card": evidence("ev-card", source_type="processed_material", chapter=56),
            "ev-relation": evidence("ev-relation", source_type="graph_relation", chapter=56, relation_id="rel-tanchun-manages"),
        },
    )

    assert decision == EvidenceDecision.SUPPORTED


def test_quotable_fact_requires_one_explicit_source():
    claim = AnswerClaim(
        text="第 27 回黛玉葬花并吟《葬花吟》。",
        evidence_ids=["ev-27"],
        claim_type="quotable_fact",
    )

    decision = decide_claim_support(claim, {"ev-27": evidence("ev-27", source_type="original_text")})

    assert decision == EvidenceDecision.SUPPORTED


def test_derived_evidence_requires_referenced_explicit_evidence():
    claim = AnswerClaim(
        text="葬花和后文黛玉命运有关。",
        evidence_ids=["ev-derived"],
        claim_type="image_foreshadowing",
    )
    explicit = evidence("ev-27", source_type="original_text", chapter=27)
    derived = evidence(
        "ev-derived",
        source_type="graph_relation",
        chapter=27,
        confidence="derived",
        relation_id="rel-daiyu-fate",
        derived_from_ids=["ev-27"],
    )

    assert decide_claim_support(claim, {"ev-derived": derived}) == EvidenceDecision.UNSUPPORTED
    assert decide_claim_support(claim, {"ev-27": explicit, "ev-derived": derived}) == EvidenceDecision.SUPPORTED


def test_derived_evidence_rejects_knowledge_card_only_dependency():
    claim = AnswerClaim(
        text="葬花和后文黛玉命运有关。",
        evidence_ids=["ev-derived"],
        claim_type="image_foreshadowing",
    )
    explicit_card = evidence("ev-card", source_type="knowledge_card", chapter=27)
    derived = evidence(
        "ev-derived",
        source_type="graph_relation",
        chapter=27,
        confidence="derived",
        relation_id="rel-daiyu-fate",
        derived_from_ids=["ev-card"],
    )

    assert decide_claim_support(claim, {"ev-card": explicit_card, "ev-derived": derived}) == EvidenceDecision.UNSUPPORTED


def test_detect_source_conflict_flags_different_explicit_text_for_same_relation():
    first = evidence("ev-a", relation_id="rel-daiyu-fate", text="葬花指向命运悲感。")
    second = evidence("ev-b", relation_id="rel-daiyu-fate", text="葬花完全没有后文关联。")

    assert detect_source_conflict([first, second]) is True

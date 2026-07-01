import pytest

from hlm_kg.domain import (
    AnswerClaim,
    AnswerSection,
    AskAnswer,
    ChapterReviewCard,
    Evidence,
    KnowledgeCard,
    ProcessedMaterialSource,
    PromptDefinition,
    Refusal,
    Topic,
    validate_answer,
)


def _explicit_evidence(evidence_id: str = "ev-explicit") -> Evidence:
    return Evidence(
        id=evidence_id,
        source_type="original_text",
        chapter=27,
        location="第二十七回",
        quote=None,
        evidence_text="第 27 回黛玉葬花并吟《葬花吟》。",
        entity_ids=["person-lindaiyu"],
        relation_id=None,
        confidence="explicit",
        provenance="book/chapters",
        derived_from_ids=[],
    )


def test_answered_answer_requires_evidence_ids_on_claims():
    answer = AskAnswer(
        id="ask-1",
        question="探春理家体现什么？",
        status="answered",
        short_conclusion=[
            AnswerClaim(
                text="探春理家体现其兴利除弊的管理才干。",
                evidence_ids=[],
                claim_type="event_causality",
            )
        ],
        evidence=[],
        explanation=[],
        quotable_facts=None,
        continuation_links=[],
        refusal=None,
    )

    with pytest.raises(ValueError, match="evidence_ids"):
        validate_answer(answer)


def test_refused_answer_requires_refusal_reason():
    answer = AskAnswer(
        id="ask-2",
        question="请写一篇作文",
        status="refused",
        short_conclusion=[],
        evidence=[],
        explanation=[],
        quotable_facts=None,
        continuation_links=[],
        refusal=None,
    )

    with pytest.raises(ValueError, match="refusal"):
        validate_answer(answer)


def test_weak_evidence_cannot_support_determinate_claim():
    weak = Evidence(
        id="ev-weak",
        source_type="processed_material",
        chapter=27,
        location="章节复习卡",
        quote=None,
        evidence_text="疑似与后文有关。",
        entity_ids=["obj-daiyu"],
        relation_id=None,
        confidence="weak",
        provenance="seed",
        derived_from_ids=[],
    )

    assert weak.can_support_claim is False


def test_explicit_evidence_can_support_claim():
    evidence = Evidence(
        id="ev-27-daiyu",
        source_type="original_text",
        chapter=27,
        location="第二十七回",
        quote="花谢花飞花满天，红消香断有谁怜？",
        evidence_text="第 27 回黛玉葬花并吟《葬花吟》。",
        entity_ids=["person-lindaiyu"],
        relation_id=None,
        confidence="explicit",
        provenance="book/chapters",
        derived_from_ids=[],
    )

    assert evidence.can_support_claim is True


def test_derived_evidence_requires_explicit_dependency_in_answer():
    derived = Evidence(
        id="ev-derived",
        source_type="graph_relation",
        chapter=None,
        location="全书关系线索",
        quote=None,
        evidence_text="葬花与后文黛玉命运构成关系线索。",
        entity_ids=["person-lindaiyu"],
        relation_id="rel-daiyu-burying-flowers-fate",
        confidence="derived",
        provenance="curated",
        derived_from_ids=["ev-explicit"],
    )
    answer = AskAnswer(
        id="ask-3",
        question="黛玉葬花有什么后文关联？",
        status="answered",
        short_conclusion=[
            AnswerClaim(
                text="葬花可作为理解黛玉命运悲感的关系线索。",
                evidence_ids=["ev-derived"],
                claim_type="image_foreshadowing",
            )
        ],
        evidence=[derived],
        explanation=[],
        quotable_facts=None,
        continuation_links=[],
        refusal=None,
    )

    with pytest.raises(ValueError, match="unsupported evidence_ids"):
        validate_answer(answer)


def test_chapter_review_card_records_prompt_source():
    card = ChapterReviewCard(
        id="review-027",
        chapter=27,
        source=ProcessedMaterialSource(
            prompt_name="hongloumeng_chapter_review_card",
            prompt_version="2026-07-01",
            generated_at=None,
        ),
        plain_summary="本回主要写黛玉葬花。",
        plot_chain=["黛玉葬花"],
        key_events=["event-daiyu-burying-flowers"],
        key_characters=["card-lindaiyu"],
        current_chapter_foreshadowing_signals=[],
        later_association_relation_ids=["rel-daiyu-burying-flowers-fate"],
        quotable_fact_ids=["ev-027-daiyu-burying-flowers"],
        retrieval_tags=["第27回"],
        understanding_focus=["意象"],
    )

    assert card.source.prompt_name == "hongloumeng_chapter_review_card"


def test_ask_answer_quotable_facts_are_an_answer_section():
    explicit = _explicit_evidence()
    answer = AskAnswer(
        id="ask-4",
        question="黛玉葬花体现了什么？",
        status="answered",
        short_conclusion=[
            AnswerClaim(
                text="黛玉葬花体现其身世悲感。",
                evidence_ids=["ev-explicit"],
                claim_type="image_foreshadowing",
            )
        ],
        evidence=[explicit],
        explanation=[],
        quotable_facts=AnswerSection(
            title="可引用事实",
            claims=[
                AnswerClaim(
                    text="第 27 回黛玉葬花并吟《葬花吟》。",
                    evidence_ids=["ev-explicit"],
                    claim_type="quotable_fact",
                )
            ],
        ),
        continuation_links=[],
        refusal=None,
    )

    validate_answer(answer)


def test_partial_answer_requires_unsupported_subclaim_refusal():
    explicit = _explicit_evidence()
    answer = AskAnswer(
        id="ask-5",
        question="黛玉葬花体现什么？再说明没有资料的后文细节。",
        status="partial",
        short_conclusion=[
            AnswerClaim(
                text="第 27 回黛玉葬花并吟《葬花吟》。",
                evidence_ids=["ev-explicit"],
                claim_type="quotable_fact",
            )
        ],
        evidence=[explicit],
        explanation=[],
        quotable_facts=None,
        continuation_links=[],
        refusal=None,
    )

    with pytest.raises(ValueError, match="partial"):
        validate_answer(answer)


def test_valid_partial_answer_names_unsupported_subclaim():
    explicit = _explicit_evidence()
    answer = AskAnswer(
        id="ask-6",
        question="黛玉葬花体现什么？再说明没有资料的后文细节。",
        status="partial",
        short_conclusion=[
            AnswerClaim(
                text="第 27 回黛玉葬花并吟《葬花吟》。",
                evidence_ids=["ev-explicit"],
                claim_type="quotable_fact",
            )
        ],
        evidence=[explicit],
        explanation=[],
        quotable_facts=None,
        continuation_links=[],
        refusal=Refusal(
            reason="UNSUPPORTED_SUBCLAIM",
            message="问题中有一部分当前资料不足，未生成确定结论。",
        ),
    )

    validate_answer(answer)


def test_prompt_definition_records_structured_rules():
    prompt = PromptDefinition(
        name="answer_with_evidence",
        version="2026-07-01",
        purpose="基于证据组织问答结果",
        input_schema="AskInput",
        output_schema="AskAnswer",
        evidence_rules=["回答前必须先检索或读取证据"],
        refusal_rules=["证据不足时拒答"],
    )

    assert prompt.output_schema == "AskAnswer"


def test_knowledge_card_type_and_topic_category_are_closed_vocabularies():
    with pytest.raises(ValueError, match="card type"):
        KnowledgeCard(
            id="card-invalid",
            name="无效卡片",
            type="freeform",
            brief="无效",
            text_understanding=[],
            understanding_angles=[],
            graph_relation_ids=[],
            evidence_ids=[],
            related_card_ids=[],
        )

    with pytest.raises(ValueError, match="topic category"):
        Topic(
            id="topic-invalid",
            title="无效专题",
            category="自由发挥",
            description="无效",
            card_ids=[],
            relation_ids=[],
            typical_question_patterns=[],
            quotable_fact_ids=[],
            evidence_ids=[],
        )

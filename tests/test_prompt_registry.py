from pathlib import Path

from hlm_kg.prompt_registry import PromptRegistry


def test_prompt_registry_loads_required_prompt_definitions():
    registry = PromptRegistry.from_path(Path("data/prompts/definitions.json"))

    chapter_card = registry.get("hongloumeng_chapter_review_card")
    evidence_answer = registry.get("answer_with_evidence")

    assert chapter_card.version == "2026-07-01"
    assert chapter_card.input_schema == "ChapterReviewCardInput"
    assert chapter_card.output_schema == "ChapterReviewCard"
    assert evidence_answer.input_schema == "AskInput"
    assert evidence_answer.output_schema == "AskAnswer"


def test_prompt_registry_exposes_evidence_and_refusal_rules():
    registry = PromptRegistry.from_path(Path("data/prompts/definitions.json"))

    chapter_card = registry.get("hongloumeng_chapter_review_card")
    evidence_answer = registry.get("answer_with_evidence")

    combined_rules = "\n".join(chapter_card.evidence_rules + evidence_answer.evidence_rules + evidence_answer.refusal_rules)
    assert "不得编造" in combined_rules
    assert "后文关联" in combined_rules
    assert "全书关系线索" in combined_rules
    assert "资料不足" in combined_rules


def test_chapter_review_card_prompt_exposes_fast_reading_content_contract():
    registry = PromptRegistry.from_path(Path("data/prompts/definitions.json"))

    chapter_card = registry.get("hongloumeng_chapter_review_card")

    content_contract = "\n".join(chapter_card.content_requirements)
    assert "8小时读懂全书" in chapter_card.purpose
    assert "本回一句话概括" in content_contract
    assert "本回梗概" in content_contract
    assert "情节链梳理" in content_contract
    assert "人物关系图谱" in content_contract
    assert "核心知识卡片" in content_contract


def test_chapter_review_card_prompt_requires_system_relation_backed_later_associations():
    registry = PromptRegistry.from_path(Path("data/prompts/definitions.json"))

    chapter_card = registry.get("hongloumeng_chapter_review_card")

    retrieval_contract = "\n".join(chapter_card.evidence_rules + chapter_card.content_requirements)
    assert "后文关联必须来自系统提供的全书关系线索" in retrieval_contract
    assert "不能只依靠模型常识" in retrieval_contract
    assert "later_association_relation_ids" in retrieval_contract
    assert "characters、relationships、places、objects、literary_texts、modern_explanations、later_associations、annotations" in retrieval_contract


def test_prompt_registry_can_find_definitions_by_rule_text():
    registry = PromptRegistry.from_path(Path("data/prompts/definitions.json"))

    matches = registry.find_by_rule("资料不足")

    assert {prompt.name for prompt in matches} == {"hongloumeng_chapter_review_card", "answer_with_evidence"}


def test_readme_documents_prompt_definition_location():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "data/prompts/definitions.json" in readme
    assert "证据规则" in readme
    assert "拒答规则" in readme

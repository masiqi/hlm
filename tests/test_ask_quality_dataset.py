from pathlib import Path

import pytest

from hlm_kg.ask_quality_dataset import (
    AskQualityDatasetError,
    ask_quality_categories,
    load_ask_quality_dataset,
    render_ask_quality_report,
    validate_ask_quality_dataset,
)


DATASET_PATH = Path("data/eval/ask_quality_dataset.json")


def test_ask_quality_dataset_covers_required_categories():
    samples = load_ask_quality_dataset(DATASET_PATH)

    assert 35 <= len(samples) <= 50
    assert ask_quality_categories(samples) == {
        "精确事实定位",
        "人物关系与身份别称",
        "章回情节与内容概括",
        "事件因果与伏笔照应",
        "诗词判词与人物命运",
        "主题意象与空间物件",
        "比较鉴赏与论述支撑",
        "证据不足与拒答",
    }


def test_ask_quality_dataset_emphasizes_common_character_relationships():
    samples = load_ask_quality_dataset(DATASET_PATH)

    relationship_samples = [sample for sample in samples if sample["category"] == "人物关系与身份别称"]
    relationship_questions = "\n".join(sample["question"] for sample in relationship_samples)

    assert len(relationship_samples) >= 10
    for expected_name in ("贾宝玉", "林黛玉", "薛宝钗", "王熙凤", "袭人", "鸳鸯"):
        assert expected_name in relationship_questions


def test_ask_quality_dataset_is_not_a_standard_answer_bank():
    samples = load_ask_quality_dataset(DATASET_PATH)

    for sample in samples:
        assert "standard_answer" not in sample
        assert "answer" not in sample
        assert "score" not in sample
        assert "expected_status" in sample
        assert "expected_subjects" in sample
        assert "preferred_evidence_types" in sample
        assert "required_evidence_terms" in sample
        assert "must_not_focus_on" in sample


def test_validate_ask_quality_dataset_reports_counts():
    samples = load_ask_quality_dataset(DATASET_PATH)

    report = validate_ask_quality_dataset(samples)

    assert report.total == len(samples)
    assert report.status_counts["answered"] >= 30
    assert report.status_counts["refused"] >= 2
    assert report.category_counts["人物关系与身份别称"] >= 10
    assert report.issues == []


def test_render_ask_quality_report_is_agent_readable():
    samples = load_ask_quality_dataset(DATASET_PATH)
    report = validate_ask_quality_dataset(samples)

    rendered = render_ask_quality_report(report)

    assert "问一问质量数据集验证报告" in rendered
    assert "总样例数" in rendered
    assert "人物关系与身份别称" in rendered
    assert "answered" in rendered
    assert "未发现问题" in rendered


def test_validate_ask_quality_dataset_rejects_answer_like_fields():
    samples = [
        {
            "id": "ask-invalid-answer",
            "category": "精确事实定位",
            "question": "林黛玉生的什么病？",
            "expected_status": "answered",
            "expected_subjects": ["林黛玉"],
            "expected_chapters": [3],
            "preferred_evidence_types": ["original_text"],
            "required_evidence_terms": ["不足之症"],
            "must_not_focus_on": ["宝黛关系"],
            "quality_notes": "用于校验拒绝标准答案字段。",
            "answer": "不足之症",
        }
    ]

    with pytest.raises(AskQualityDatasetError, match="answer"):
        validate_ask_quality_dataset(samples)


def test_validate_ask_quality_dataset_rejects_invalid_expected_status():
    samples = [
        {
            "id": "ask-invalid-status",
            "category": "精确事实定位",
            "question": "林黛玉生的什么病？",
            "expected_status": "maybe",
            "expected_subjects": ["林黛玉"],
            "expected_chapters": [3],
            "preferred_evidence_types": ["original_text"],
            "required_evidence_terms": ["不足之症"],
            "must_not_focus_on": [],
            "quality_notes": "用于校验状态枚举。",
        }
    ]

    with pytest.raises(AskQualityDatasetError, match="expected_status"):
        validate_ask_quality_dataset(samples)


def test_validate_ask_quality_dataset_rejects_invalid_evidence_type():
    samples = [
        {
            "id": "ask-invalid-evidence-type",
            "category": "人物关系与身份别称",
            "question": "贾宝玉和林黛玉是什么关系？",
            "expected_status": "answered",
            "expected_subjects": ["贾宝玉", "林黛玉"],
            "expected_chapters": [3],
            "preferred_evidence_types": ["made_up_type"],
            "required_evidence_terms": ["姑表"],
            "must_not_focus_on": [],
            "quality_notes": "用于校验证据类型。",
        }
    ]

    with pytest.raises(AskQualityDatasetError, match="preferred_evidence_types"):
        validate_ask_quality_dataset(samples)


def test_makefile_exposes_ask_quality_dataset_target():
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert "validate-ask-quality-dataset:" in makefile
    assert "python -m hlm_kg.ask_quality_dataset" in makefile

from pathlib import Path

import pytest

from hlm_kg.validation_samples import (
    ValidationSampleError,
    render_validation_report,
    load_validation_samples,
    sample_categories,
    validate_validation_samples,
)


def test_validation_samples_cover_required_categories():
    samples = load_validation_samples(Path("data/app/validation_samples.json"))

    assert 20 <= len(samples) <= 40
    assert sample_categories(samples) == {
        "人物关系与身份别称",
        "章回情节与内容概括",
        "比较鉴赏与论述",
        "诗词判词与人物命运",
        "主题意象与象征",
        "事件因果与伏笔照应",
        "制度礼俗与文化常识",
    }


def test_validation_samples_do_not_require_standard_answers():
    samples = load_validation_samples(Path("data/app/validation_samples.json"))

    for sample in samples:
        assert "standard_answer" not in sample
        assert "answer" not in sample
        assert "score" not in sample
        assert "expected_evidence_types" in sample
        assert "expected_objects" in sample


def test_validate_validation_samples_reports_category_counts():
    samples = load_validation_samples(Path("data/app/validation_samples.json"))

    report = validate_validation_samples(samples)

    assert report.total == len(samples)
    assert report.category_counts["人物关系与身份别称"] == 3
    assert report.category_counts["制度礼俗与文化常识"] == 3
    assert report.issues == []


def test_render_validation_report_is_agent_readable():
    samples = load_validation_samples(Path("data/app/validation_samples.json"))
    report = validate_validation_samples(samples)

    rendered = render_validation_report(report)

    assert "校准样例验证报告" in rendered
    assert "总样例数" in rendered
    assert "人物关系与身份别称: 3" in rendered
    assert "未发现问题" in rendered


def test_validate_validation_samples_rejects_answer_like_fields():
    samples = [
        {
            "id": "sample-invalid-answer",
            "category": "人物关系与身份别称",
            "question": "潇湘妃子指的是谁？",
            "expected_objects": ["林黛玉"],
            "expected_evidence_types": ["graph_relation"],
            "should_refuse": False,
            "answer": "林黛玉",
        }
    ]

    with pytest.raises(ValidationSampleError, match="answer"):
        validate_validation_samples(samples)


def test_validate_validation_samples_rejects_invalid_evidence_type():
    samples = [
        {
            "id": "sample-invalid-evidence-type",
            "category": "人物关系与身份别称",
            "question": "潇湘妃子指的是谁？",
            "expected_objects": ["林黛玉"],
            "expected_evidence_types": ["made_up_type"],
            "should_refuse": False,
        }
    ]

    with pytest.raises(ValidationSampleError, match="expected_evidence_types"):
        validate_validation_samples(samples)


def test_validate_validation_samples_rejects_non_boolean_should_refuse():
    samples = [
        {
            "id": "sample-invalid-should-refuse",
            "category": "人物关系与身份别称",
            "question": "潇湘妃子指的是谁？",
            "expected_objects": ["林黛玉"],
            "expected_evidence_types": ["graph_relation"],
            "should_refuse": "false",
        }
    ]

    with pytest.raises(ValidationSampleError, match="should_refuse"):
        validate_validation_samples(samples)


def test_makefile_exposes_validation_samples_target():
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert "validate-samples:" in makefile
    assert "python -m hlm_kg.validation_samples" in makefile

from pathlib import Path

from hlm_kg.validation_samples import load_validation_samples, sample_categories


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

from pathlib import Path

from hlm_kg.questions import analyze_questions, load_questions


def test_load_questions_parses_jsonl():
    records = load_questions(Path("questions/zujuan_questions_2026-06-30.jsonl"))

    assert len(records) > 0
    assert {"id", "text", "source", "type", "url"}.issubset(records[0])


def test_analyze_questions_returns_type_summary_without_answers():
    records = load_questions(Path("questions/zujuan_questions_2026-06-30.jsonl"))
    summary = analyze_questions(records)

    assert summary["record_count"] == len(records)
    assert "fields" in summary
    assert "type_counts" in summary
    assert "capability_counts" in summary
    assert "答案" not in "\n".join(summary["example_queries"])

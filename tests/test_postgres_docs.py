from pathlib import Path


def test_postgres_trace_graph_docs_cover_safe_operations():
    text = Path("docs/postgres_trace_graph.md").read_text(encoding="utf-8")

    assert "DATABASE_URL" in text
    assert "make postgres-migrate" in text
    assert "make postgres-import-seed" in text
    assert "HLM_CONTENT_STORE=postgres" in text
    assert "不要提交 `.env`" in text

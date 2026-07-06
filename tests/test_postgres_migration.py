from pathlib import Path

from hlm_kg.postgres_config import load_database_url, load_dotenv, parse_bool
from scripts import migrate_postgres


def test_migration_sql_creates_trace_graph_tables_and_indexes():
    sql = Path("db/migrations/001_postgres_trace_graph.sql").read_text(encoding="utf-8")

    for table in [
        "chapters",
        "chapter_cards",
        "entities",
        "entity_aliases",
        "relations",
        "evidence",
        "chapter_annotations",
        "trace_items",
        "entity_trace_cache",
        "entity_graph_cache",
        "embeddings",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql

    assert "JSONB" in sql
    assert "CREATE EXTENSION IF NOT EXISTS vector" not in sql
    assert "CREATE INDEX IF NOT EXISTS idx_trace_items_entity" in sql
    assert "CREATE INDEX IF NOT EXISTS idx_entity_trace_cache_lookup" in sql
    assert "CREATE INDEX IF NOT EXISTS idx_entity_graph_cache_name" in sql
    assert "extended_neighbors JSONB NOT NULL DEFAULT '[]'::jsonb" in sql
    assert "CREATE INDEX IF NOT EXISTS idx_chapter_annotations_chapter" in sql
    assert "CREATE INDEX IF NOT EXISTS idx_entities_name" in sql


def test_load_database_url_reads_database_url_without_printing_secret(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@example.local:5432/hlm")

    assert load_database_url() == "postgresql://user:secret@example.local:5432/hlm"


def test_load_database_url_returns_none_when_missing(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert load_database_url() is None


def test_parse_bool_accepts_common_truthy_values():
    assert parse_bool("1") is True
    assert parse_bool("true") is True
    assert parse_bool("yes") is True
    assert parse_bool("on") is True
    assert parse_bool("0") is False
    assert parse_bool(None) is False


def test_migrate_postgres_loads_sql_file():
    sql = migrate_postgres.load_migration_sql(Path("db/migrations/001_postgres_trace_graph.sql"))

    assert "CREATE TABLE IF NOT EXISTS chapters" in sql


def test_load_dotenv_handles_special_characters_without_shell_expansion(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "DATABASE_URL=postgresql://user:p*ss@localhost:5432/hlm\n"
        "QUOTED_VALUE=\"contains spaces and * chars\"\n",
        encoding="utf-8",
    )

    values = load_dotenv(env_path)

    assert values["DATABASE_URL"] == "postgresql://user:p*ss@localhost:5432/hlm"
    assert values["QUOTED_VALUE"] == "contains spaces and * chars"

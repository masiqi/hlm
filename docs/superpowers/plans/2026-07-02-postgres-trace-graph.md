# PostgreSQL Trace Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build PostgreSQL-backed data storage for chapters, chapter cards, knowledge cards, relations, evidence, original-text annotations, and trace items so a student can click a person/event/object and see all related clues with chapter jumps.

**Architecture:** Keep the existing JSON `ContentStore` as the safe fallback. Add a PostgreSQL schema, migration runner, seed importer, and `PostgresContentStore` with the same read surface plus annotations and trace items. Extend the web API and static frontend to consume annotations/traces while preserving current behavior when PostgreSQL is not enabled.

**Tech Stack:** Python 3, `psycopg`, PostgreSQL, optional `pgvector`, JSONB, existing `http.server` web app, pytest.

## Global Constraints

- Development issue: GitHub #31, branch `feat/postgres-trace-graph`.
- Never print or commit `.env`, `DATABASE_URL`, database passwords, API keys, or generated secrets.
- Use `DATABASE_URL` from `.env` for live database operations.
- Existing JSON-backed tests and behavior must remain valid.
- PostgreSQL mode must be opt-in via `HLM_CONTENT_STORE=postgres` or explicit `use_postgres_store=True` in tests.
- Student-facing responses and UI text must not expose internal terms: `LightRAG`, `RAG`, `知识图谱`, `向量检索`, `置信度`, `模型分数`, `标准答案`, `题库`, `下一题`, `提交答案`, `批改`.
- Every displayed trace or annotation must be backed by a chapter, evidence row, relation row, entity row, or a clear empty-state message.
- Frontend must remain usable on mobile; no nested cards; no decorative gradients or orbs.
- Tests must not require a live PostgreSQL server unless explicitly marked or invoked by a manual smoke command.

---

### Task 1: PostgreSQL Schema And Migration Runner

**Files:**
- Create: `db/migrations/001_postgres_trace_graph.sql`
- Create: `hlm_kg/postgres_config.py`
- Create: `scripts/migrate_postgres.py`
- Create: `tests/test_postgres_migration.py`
- Modify: `Makefile`

**Interfaces:**
- Produces: `hlm_kg.postgres_config.load_database_url(env: Mapping[str, str] | None = None) -> str | None`
- Produces: `hlm_kg.postgres_config.parse_bool(value: str | None) -> bool`
- Produces: `scripts.migrate_postgres.load_migration_sql(path: Path) -> str`
- Produces: `scripts.migrate_postgres.main(argv: list[str] | None = None) -> int`
- Later tasks rely on migration tables: `chapters`, `chapter_cards`, `entities`, `entity_aliases`, `relations`, `evidence`, `chapter_annotations`, `trace_items`, `embeddings`.

- [ ] **Step 1: Write failing migration structure tests**

Create `tests/test_postgres_migration.py`:

```python
from pathlib import Path

from hlm_kg.postgres_config import load_database_url, parse_bool
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
        "embeddings",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql

    assert "JSONB" in sql
    assert "CREATE EXTENSION IF NOT EXISTS vector" in sql
    assert "CREATE INDEX IF NOT EXISTS idx_trace_items_entity" in sql
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
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
pytest tests/test_postgres_migration.py -q
```

Expected: FAIL because `hlm_kg.postgres_config`, `scripts/migrate_postgres`, and migration SQL do not exist.

- [ ] **Step 3: Add migration SQL**

Create `db/migrations/001_postgres_trace_graph.sql`:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chapters (
    id TEXT PRIMARY KEY,
    number INTEGER NOT NULL UNIQUE CHECK (number BETWEEN 1 AND 120),
    title TEXT NOT NULL,
    source_file TEXT NOT NULL,
    original_text TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chapter_cards (
    id TEXT PRIMARY KEY,
    chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    plot_chain JSONB NOT NULL DEFAULT '[]'::jsonb,
    key_events JSONB NOT NULL DEFAULT '[]'::jsonb,
    key_characters JSONB NOT NULL DEFAULT '[]'::jsonb,
    foreshadowing JSONB NOT NULL DEFAULT '[]'::jsonb,
    later_association_relation_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    quotable_fact_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    retrieval_tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    understanding_focus JSONB NOT NULL DEFAULT '[]'::jsonb,
    raw_card JSONB NOT NULL DEFAULT '{}'::jsonb,
    prompt_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    generated_at TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    brief TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS entity_aliases (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    alias_type TEXT NOT NULL DEFAULT 'name',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (entity_id, alias)
);

CREATE TABLE IF NOT EXISTS relations (
    id TEXT PRIMARY KEY,
    subject_entity_id TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object_entity_id TEXT NOT NULL,
    chapters JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    provenance TEXT NOT NULL DEFAULT 'curated',
    confidence TEXT NOT NULL DEFAULT 'explicit',
    description TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    chapter_id TEXT REFERENCES chapters(id) ON DELETE SET NULL,
    source_type TEXT NOT NULL,
    location TEXT,
    quote TEXT,
    evidence_text TEXT NOT NULL,
    entity_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    relation_id TEXT,
    confidence TEXT NOT NULL,
    provenance TEXT NOT NULL,
    derived_from_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chapter_annotations (
    id TEXT PRIMARY KEY,
    chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    start_offset INTEGER NOT NULL CHECK (start_offset >= 0),
    end_offset INTEGER NOT NULL CHECK (end_offset > start_offset),
    surface_text TEXT NOT NULL,
    annotation_type TEXT NOT NULL,
    entity_id TEXT REFERENCES entities(id) ON DELETE SET NULL,
    relation_id TEXT REFERENCES relations(id) ON DELETE SET NULL,
    evidence_id TEXT REFERENCES evidence(id) ON DELETE SET NULL,
    display_priority INTEGER NOT NULL DEFAULT 100,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS trace_items (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    relation_id TEXT REFERENCES relations(id) ON DELETE SET NULL,
    evidence_id TEXT REFERENCES evidence(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    trace_type TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    importance INTEGER NOT NULL DEFAULT 50,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS embeddings (
    id TEXT PRIMARY KEY,
    owner_type TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    model TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chapter_cards_chapter ON chapter_cards(chapter_id);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
CREATE INDEX IF NOT EXISTS idx_entity_aliases_alias ON entity_aliases(alias);
CREATE INDEX IF NOT EXISTS idx_relations_subject ON relations(subject_entity_id);
CREATE INDEX IF NOT EXISTS idx_relations_object ON relations(object_entity_id);
CREATE INDEX IF NOT EXISTS idx_evidence_chapter ON evidence(chapter_id);
CREATE INDEX IF NOT EXISTS idx_chapter_annotations_chapter ON chapter_annotations(chapter_id, start_offset);
CREATE INDEX IF NOT EXISTS idx_chapter_annotations_entity ON chapter_annotations(entity_id);
CREATE INDEX IF NOT EXISTS idx_trace_items_entity ON trace_items(entity_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_trace_items_chapter ON trace_items(chapter_id);
```

- [ ] **Step 4: Add config helper**

Create `hlm_kg/postgres_config.py`:

```python
from __future__ import annotations

import os
from collections.abc import Mapping


def load_database_url(env: Mapping[str, str] | None = None) -> str | None:
    source = os.environ if env is None else env
    value = source.get("DATABASE_URL")
    if value is None or not value.strip():
        return None
    return value.strip()


def parse_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}
```

- [ ] **Step 5: Add migration runner**

Create `scripts/migrate_postgres.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

import psycopg

from hlm_kg.postgres_config import load_database_url


DEFAULT_MIGRATION = Path("db/migrations/001_postgres_trace_graph.sql")


def load_migration_sql(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def run_migration(database_url: str, migration_path: Path = DEFAULT_MIGRATION) -> None:
    sql = load_migration_sql(migration_path)
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    migration_path = Path(args[0]) if args else DEFAULT_MIGRATION
    database_url = load_database_url()
    if database_url is None:
        print("error: DATABASE_URL is not set", file=sys.stderr)
        return 2
    run_migration(database_url, migration_path)
    print("PostgreSQL migration applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Add Makefile target**

Modify `Makefile`:

```make
.PHONY: help env split-chapters analyze-questions dry-run validate-samples import-chapter-cards build-kg lightrag-up lightrag-down test web postgres-migrate
```

Add help line:

```make
	@echo "  make postgres-migrate  Apply PostgreSQL schema migration using DATABASE_URL"
```

Add target:

```make
postgres-migrate:
	python scripts/migrate_postgres.py
```

- [ ] **Step 7: Run focused tests**

Run:

```bash
pytest tests/test_postgres_migration.py -q
```

Expected: PASS.

- [ ] **Step 8: Run full tests**

Run:

```bash
pytest -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add db/migrations/001_postgres_trace_graph.sql hlm_kg/postgres_config.py scripts/migrate_postgres.py tests/test_postgres_migration.py Makefile
git commit -m "feat: add postgres trace graph schema"
```

---

### Task 2: PostgreSQL Seed Importer

**Files:**
- Create: `scripts/import_postgres_seed.py`
- Create: `tests/test_import_postgres_seed.py`
- Modify: `Makefile`

**Interfaces:**
- Consumes: tables from Task 1.
- Produces: `scripts.import_postgres_seed.build_seed_records(manifest_path: Path, data_dir: Path) -> SeedRecords`
- Produces: `scripts.import_postgres_seed.annotation_rows_for_chapter(chapter_number: int, original_text: str, cards: list[dict[str, Any]]) -> list[dict[str, Any]]`
- Produces: `scripts.import_postgres_seed.trace_rows_for_card(card: dict[str, Any], relation_lookup: dict[str, dict[str, Any]], evidence_lookup: dict[str, dict[str, Any]]) -> list[dict[str, Any]]`
- Produces: idempotent database import via `upsert_seed_records(database_url: str, records: SeedRecords) -> None`.

- [ ] **Step 1: Write failing seed import tests**

Create `tests/test_import_postgres_seed.py`:

```python
from pathlib import Path

from scripts.import_postgres_seed import (
    annotation_rows_for_chapter,
    build_seed_records,
    trace_rows_for_card,
)


def test_build_seed_records_loads_existing_json_and_chapters():
    records = build_seed_records(Path("book/chapters_manifest.json"), Path("data/app"))

    assert len(records.chapters) == 120
    assert any(row["number"] == 27 and "黛玉" in row["original_text"] for row in records.chapters)
    assert any(row["id"] == "card-lindaiyu" for row in records.entities)
    assert any(row["id"] == "rel-daiyu-burying-flowers-fate" for row in records.relations)
    assert any(row["id"] == "ev-027-daiyu-burying-flowers" for row in records.evidence)
    assert any(row["chapter_number"] == 27 for row in records.chapter_cards)


def test_annotation_rows_for_chapter_uses_card_names_and_offsets():
    text = "袭人见宝玉回来。宝玉问袭人。"
    cards = [
        {"id": "card-xiren", "name": "袭人", "type": "person"},
        {"id": "card-baoyu", "name": "宝玉", "type": "person"},
    ]

    rows = annotation_rows_for_chapter(8, text, cards)

    assert [row["surface_text"] for row in rows] == ["袭人", "宝玉", "宝玉", "袭人"]
    assert rows[0]["start_offset"] == 0
    assert rows[0]["end_offset"] == 2
    assert rows[0]["entity_id"] == "card-xiren"
    assert rows[0]["annotation_type"] == "person"


def test_trace_rows_for_card_turns_relations_and_evidence_into_chapter_links():
    card = {
        "id": "card-lindaiyu",
        "name": "林黛玉",
        "graph_relation_ids": ["rel-daiyu-burying-flowers-fate"],
        "evidence_ids": ["ev-027-daiyu-burying-flowers"],
    }
    relation_lookup = {
        "rel-daiyu-burying-flowers-fate": {
            "id": "rel-daiyu-burying-flowers-fate",
            "description": "黛玉葬花表现身世悲感。",
            "chapters": [27],
            "evidence_ids": ["ev-027-daiyu-burying-flowers"],
        }
    }
    evidence_lookup = {
        "ev-027-daiyu-burying-flowers": {
            "id": "ev-027-daiyu-burying-flowers",
            "chapter": 27,
            "evidence_text": "黛玉葬花并吟唱《葬花吟》。",
        }
    }

    rows = trace_rows_for_card(card, relation_lookup, evidence_lookup)

    assert rows[0]["entity_id"] == "card-lindaiyu"
    assert rows[0]["chapter_number"] == 27
    assert rows[0]["relation_id"] == "rel-daiyu-burying-flowers-fate"
    assert rows[0]["evidence_id"] == "ev-027-daiyu-burying-flowers"
    assert "黛玉葬花" in rows[0]["description"]
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
pytest tests/test_import_postgres_seed.py -q
```

Expected: FAIL because `scripts.import_postgres_seed` does not exist.

- [ ] **Step 3: Implement seed record builder**

Create `scripts/import_postgres_seed.py` with:

```python
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from hlm_kg.postgres_config import load_database_url


@dataclass(frozen=True)
class SeedRecords:
    chapters: list[dict[str, Any]]
    chapter_cards: list[dict[str, Any]]
    entities: list[dict[str, Any]]
    aliases: list[dict[str, Any]]
    relations: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    annotations: list[dict[str, Any]]
    trace_items: list[dict[str, Any]]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_seed_records(manifest_path: Path, data_dir: Path) -> SeedRecords:
    manifest = _read_json(manifest_path)
    chapter_cards = list(_read_json(data_dir / "chapter_review_cards.json"))
    knowledge_cards = list(_read_json(data_dir / "knowledge_cards.json"))
    relations = list(_read_json(data_dir / "graph_relations.json"))
    evidence = list(_read_json(data_dir / "evidence.json"))
    relation_lookup = {str(row["id"]): row for row in relations}
    evidence_lookup = {str(row["id"]): row for row in evidence}
    entity_lookup = {str(row["id"]): row for row in knowledge_cards}

    chapters = []
    for item in manifest["chapters"]:
        number = int(item["number"])
        path = Path(item["file_path"])
        chapters.append(
            {
                "id": f"chapter-{number:03d}",
                "number": number,
                "title": str(item["title"]),
                "source_file": str(path),
                "original_text": path.read_text(encoding="utf-8"),
                "metadata": {},
            }
        )

    normalized_cards = [_chapter_card_row(row) for row in chapter_cards]
    aliases = [_alias_row(row) for row in knowledge_cards]
    normalized_relations = [_relation_row(row) for row in relations]
    normalized_evidence = [_evidence_row(row) for row in evidence]
    annotations = []
    for card in chapter_cards:
        chapter_number = int(card["chapter"])
        chapter_text = chapters[chapter_number - 1]["original_text"]
        cards_for_chapter = [entity_lookup[card_id] for card_id in card.get("key_characters", []) if card_id in entity_lookup]
        annotations.extend(annotation_rows_for_chapter(chapter_number, chapter_text, cards_for_chapter))
    trace_items = []
    for card in knowledge_cards:
        trace_items.extend(trace_rows_for_card(card, relation_lookup, evidence_lookup))

    return SeedRecords(
        chapters=chapters,
        chapter_cards=normalized_cards,
        entities=[_entity_row(row) for row in knowledge_cards],
        aliases=aliases,
        relations=normalized_relations,
        evidence=normalized_evidence,
        annotations=annotations,
        trace_items=trace_items,
    )
```

- [ ] **Step 4: Implement row helpers**

Append:

```python
def _chapter_card_row(row: dict[str, Any]) -> dict[str, Any]:
    source = dict(row.get("source", {}))
    return {
        "id": str(row["id"]),
        "chapter_number": int(row["chapter"]),
        "summary": str(row["plain_summary"]),
        "plot_chain": list(row.get("plot_chain", [])),
        "key_events": list(row.get("key_events", [])),
        "key_characters": list(row.get("key_characters", [])),
        "foreshadowing": list(row.get("current_chapter_foreshadowing_signals", [])),
        "later_association_relation_ids": list(row.get("later_association_relation_ids", [])),
        "quotable_fact_ids": list(row.get("quotable_fact_ids", [])),
        "retrieval_tags": list(row.get("retrieval_tags", [])),
        "understanding_focus": list(row.get("understanding_focus", [])),
        "raw_card": row,
        "prompt_name": str(source.get("prompt_name", "hongloumeng_chapter_review_card")),
        "prompt_version": str(source.get("prompt_version", "")),
        "generated_at": source.get("generated_at"),
    }


def _entity_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "name": str(row["name"]),
        "type": str(row["type"]),
        "brief": str(row.get("brief", "")),
        "description": "；".join(list(row.get("text_understanding", []))),
        "metadata": {
            "text_understanding": list(row.get("text_understanding", [])),
            "understanding_angles": list(row.get("understanding_angles", [])),
            "related_card_ids": list(row.get("related_card_ids", [])),
        },
    }


def _alias_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"alias-{row['id']}",
        "entity_id": str(row["id"]),
        "alias": str(row["name"]),
        "alias_type": "primary_name",
    }


def _relation_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "subject_entity_id": str(row["subject_id"]),
        "predicate": str(row["predicate"]),
        "object_entity_id": str(row["object_id"]),
        "chapters": list(row.get("chapters", [])),
        "evidence_ids": list(row.get("evidence_ids", [])),
        "provenance": str(row.get("provenance", "curated")),
        "confidence": "explicit",
        "description": str(row["description"]),
        "metadata": {},
    }


def _evidence_row(row: dict[str, Any]) -> dict[str, Any]:
    chapter = row.get("chapter")
    return {
        "id": str(row["id"]),
        "chapter_number": int(chapter) if chapter is not None else None,
        "source_type": str(row["source_type"]),
        "location": row.get("location"),
        "quote": row.get("quote"),
        "evidence_text": str(row["evidence_text"]),
        "entity_ids": list(row.get("entity_ids", [])),
        "relation_id": row.get("relation_id"),
        "confidence": str(row["confidence"]),
        "provenance": str(row["provenance"]),
        "derived_from_ids": list(row.get("derived_from_ids", [])),
        "metadata": {},
    }
```

- [ ] **Step 5: Implement annotations and trace derivation**

Append:

```python
def annotation_rows_for_chapter(chapter_number: int, original_text: str, cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for card in sorted(cards, key=lambda item: len(str(item["name"])), reverse=True):
        name = str(card["name"]).strip()
        if not name:
            continue
        start = 0
        while True:
            index = original_text.find(name, start)
            if index == -1:
                break
            rows.append(
                {
                    "id": f"ann-{chapter_number:03d}-{card['id']}-{index}",
                    "chapter_number": chapter_number,
                    "start_offset": index,
                    "end_offset": index + len(name),
                    "surface_text": name,
                    "annotation_type": str(card.get("type", "entity")),
                    "entity_id": str(card["id"]),
                    "relation_id": None,
                    "evidence_id": None,
                    "display_priority": 100,
                    "metadata": {},
                }
            )
            start = index + len(name)
    return sorted(rows, key=lambda row: (row["start_offset"], row["end_offset"]))


def trace_rows_for_card(
    card: dict[str, Any],
    relation_lookup: dict[str, dict[str, Any]],
    evidence_lookup: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    order = 0
    for relation_id in card.get("graph_relation_ids", []):
        relation = relation_lookup.get(str(relation_id))
        if relation is None:
            continue
        evidence_id = next((item for item in relation.get("evidence_ids", []) if item in evidence_lookup), None)
        evidence = evidence_lookup.get(str(evidence_id)) if evidence_id else None
        chapter = _first_chapter(relation.get("chapters", []), evidence)
        if chapter is None:
            continue
        rows.append(
            {
                "id": f"trace-{card['id']}-{relation['id']}",
                "entity_id": str(card["id"]),
                "chapter_number": chapter,
                "relation_id": str(relation["id"]),
                "evidence_id": str(evidence_id) if evidence_id else None,
                "title": f"第{chapter}回线索",
                "description": str(relation["description"]),
                "trace_type": "relation",
                "sort_order": order,
                "importance": 80,
                "metadata": {},
            }
        )
        order += 1
    for evidence_id in card.get("evidence_ids", []):
        evidence = evidence_lookup.get(str(evidence_id))
        if evidence is None or evidence.get("chapter") is None:
            continue
        rows.append(
            {
                "id": f"trace-{card['id']}-{evidence['id']}",
                "entity_id": str(card["id"]),
                "chapter_number": int(evidence["chapter"]),
                "relation_id": evidence.get("relation_id"),
                "evidence_id": str(evidence["id"]),
                "title": f"第{int(evidence['chapter'])}回依据",
                "description": str(evidence["evidence_text"]),
                "trace_type": "evidence",
                "sort_order": order,
                "importance": 60,
                "metadata": {},
            }
        )
        order += 1
    unique = {row["id"]: row for row in rows}
    return list(unique.values())


def _first_chapter(chapters: list[Any], evidence: dict[str, Any] | None) -> int | None:
    if chapters:
        return int(chapters[0])
    if evidence is not None and evidence.get("chapter") is not None:
        return int(evidence["chapter"])
    return None
```

- [ ] **Step 6: Implement database upsert**

Append:

```python
def upsert_seed_records(database_url: str, records: SeedRecords) -> None:
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            _upsert_chapters(cur, records.chapters)
            _upsert_chapter_cards(cur, records.chapter_cards)
            _upsert_entities(cur, records.entities)
            _upsert_aliases(cur, records.aliases)
            _upsert_relations(cur, records.relations)
            _upsert_evidence(cur, records.evidence)
            _upsert_annotations(cur, records.annotations)
            _upsert_trace_items(cur, records.trace_items)
        conn.commit()
```

Add helper functions using `executemany` and `ON CONFLICT (id) DO UPDATE` for all record lists. Convert JSON-like values with `Jsonb(value)`. Use chapter subqueries:

```sql
(SELECT id FROM chapters WHERE number = %(chapter_number)s)
```

for `chapter_id`.

- [ ] **Step 7: Add CLI and Makefile target**

Append CLI:

```python
def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    manifest_path = Path(args[0]) if len(args) >= 1 else Path("book/chapters_manifest.json")
    data_dir = Path(args[1]) if len(args) >= 2 else Path("data/app")
    database_url = load_database_url()
    if database_url is None:
        print("error: DATABASE_URL is not set", file=sys.stderr)
        return 2
    records = build_seed_records(manifest_path, data_dir)
    upsert_seed_records(database_url, records)
    print(
        "PostgreSQL seed imported: "
        f"{len(records.chapters)} chapters, "
        f"{len(records.entities)} entities, "
        f"{len(records.relations)} relations, "
        f"{len(records.evidence)} evidence items"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Modify `Makefile` phony line to include `postgres-import-seed`; add help line:

```make
	@echo "  make postgres-import-seed  Import book/data seed content into PostgreSQL"
```

Add target:

```make
postgres-import-seed:
	python scripts/import_postgres_seed.py
```

- [ ] **Step 8: Run focused tests**

Run:

```bash
pytest tests/test_import_postgres_seed.py tests/test_postgres_migration.py -q
```

Expected: PASS.

- [ ] **Step 9: Run full tests**

Run:

```bash
pytest -q
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add scripts/import_postgres_seed.py tests/test_import_postgres_seed.py Makefile
git commit -m "feat: import seed content into postgres"
```

---

### Task 3: PostgreSQL Store And Web API

**Files:**
- Create: `hlm_kg/postgres_store.py`
- Create: `tests/test_postgres_store.py`
- Modify: `hlm_kg/domain.py`
- Modify: `hlm_kg/web_app.py`
- Modify: `tests/test_web_app.py`

**Interfaces:**
- Consumes: Task 1 tables and Task 2 imported data.
- Produces: dataclasses `ChapterAnnotation` and `TraceItem`.
- Produces: `PostgresContentStore` with methods used by `web_app`: `chapter`, `chapter_text`, `maybe_review_card_for_chapter`, `knowledge_card`, `graph_relation`, `evidence`, `evidence_by_id`, `topics`, `knowledge_cards`, `graph_relations`, `annotations_for_chapter`, `trace_items_for_entity`.
- Produces: API payload additions:
  - `GET /api/chapters/:number` includes `annotations`.
  - `GET /api/cards/:id` includes `traceItems`.

- [ ] **Step 1: Write failing domain/store tests**

Create `tests/test_postgres_store.py`:

```python
from hlm_kg.domain import ChapterAnnotation, TraceItem


def test_chapter_annotation_exposes_jump_target_fields():
    annotation = ChapterAnnotation(
        id="ann-008-card-xiren-0",
        chapter=8,
        start_offset=0,
        end_offset=2,
        surface_text="袭人",
        annotation_type="person",
        entity_id="card-xiren",
        relation_id=None,
        evidence_id=None,
        display_priority=100,
    )

    assert annotation.chapter == 8
    assert annotation.surface_text == "袭人"
    assert annotation.entity_id == "card-xiren"


def test_trace_item_exposes_chapter_jump_and_evidence():
    item = TraceItem(
        id="trace-card-xiren-001",
        entity_id="card-xiren",
        chapter=8,
        relation_id="rel-xiren-baoyu",
        evidence_id="ev-008-xiren",
        title="第8回线索",
        description="袭人与宝玉相关。",
        trace_type="relation",
        sort_order=1,
        importance=80,
    )

    assert item.chapter == 8
    assert item.evidence_id == "ev-008-xiren"
```

- [ ] **Step 2: Write failing web API test with fake store**

Append to `tests/test_web_app.py`:

```python
from dataclasses import dataclass

from hlm_kg.domain import ChapterAnnotation, TraceItem


def test_api_chapter_payload_includes_annotations():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )

    status, payload = handle_api_request(context, "GET", "/api/chapters/27")

    assert status == 200
    assert "annotations" in payload
    assert isinstance(payload["annotations"], list)


def test_api_card_payload_includes_trace_items():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )

    status, payload = handle_api_request(context, "GET", "/api/cards/card-lindaiyu")

    assert status == 200
    assert "traceItems" in payload
    assert isinstance(payload["traceItems"], list)
    assert payload["traceItems"]
    assert payload["traceItems"][0]["chapter"]
```

- [ ] **Step 3: Run tests to verify RED**

Run:

```bash
pytest tests/test_postgres_store.py tests/test_web_app.py -q
```

Expected: FAIL because domain dataclasses and API fields do not exist.

- [ ] **Step 4: Add domain dataclasses**

Modify `hlm_kg/domain.py` after `ChapterReviewCard`:

```python
@dataclass(frozen=True)
class ChapterAnnotation:
    id: str
    chapter: int
    start_offset: int
    end_offset: int
    surface_text: str
    annotation_type: str
    entity_id: str | None
    relation_id: str | None
    evidence_id: str | None
    display_priority: int


@dataclass(frozen=True)
class TraceItem:
    id: str
    entity_id: str
    chapter: int
    relation_id: str | None
    evidence_id: str | None
    title: str
    description: str
    trace_type: str
    sort_order: int
    importance: int
```

- [ ] **Step 5: Add fallback methods to JSON ContentStore**

Modify `hlm_kg/content_store.py` imports to include `ChapterAnnotation` and `TraceItem`.

Add methods:

```python
    def annotations_for_chapter(self, number: int) -> list[ChapterAnnotation]:
        review_card = self.maybe_review_card_for_chapter(number)
        if review_card is None:
            return []
        text = self.chapter_text(number)
        cards = [self._knowledge_cards[card_id] for card_id in review_card.key_characters if card_id in self._knowledge_cards]
        annotations: list[ChapterAnnotation] = []
        for card in sorted(cards, key=lambda item: len(item.name), reverse=True):
            start = 0
            while True:
                index = text.find(card.name, start)
                if index == -1:
                    break
                annotations.append(
                    ChapterAnnotation(
                        id=f"ann-{number:03d}-{card.id}-{index}",
                        chapter=number,
                        start_offset=index,
                        end_offset=index + len(card.name),
                        surface_text=card.name,
                        annotation_type=card.type,
                        entity_id=card.id,
                        relation_id=None,
                        evidence_id=None,
                        display_priority=100,
                    )
                )
                start = index + len(card.name)
        return sorted(annotations, key=lambda item: (item.start_offset, item.end_offset))

    def trace_items_for_entity(self, entity_id: str) -> list[TraceItem]:
        card = self.knowledge_card(entity_id)
        items: list[TraceItem] = []
        order = 0
        for relation_id in card.graph_relation_ids:
            relation = self._graph_relations.get(relation_id)
            if relation is None:
                continue
            evidence_id = next((item for item in relation.evidence_ids if item in self._evidence), None)
            evidence = self._evidence.get(evidence_id) if evidence_id else None
            chapter = relation.chapters[0] if relation.chapters else evidence.chapter if evidence else None
            if chapter is None:
                continue
            items.append(
                TraceItem(
                    id=f"trace-{entity_id}-{relation.id}",
                    entity_id=entity_id,
                    chapter=int(chapter),
                    relation_id=relation.id,
                    evidence_id=evidence_id,
                    title=f"第{int(chapter)}回线索",
                    description=relation.description,
                    trace_type="relation",
                    sort_order=order,
                    importance=80,
                )
            )
            order += 1
        for evidence_id in card.evidence_ids:
            evidence = self._evidence.get(evidence_id)
            if evidence is None or evidence.chapter is None:
                continue
            trace_id = f"trace-{entity_id}-{evidence.id}"
            if any(item.id == trace_id for item in items):
                continue
            items.append(
                TraceItem(
                    id=trace_id,
                    entity_id=entity_id,
                    chapter=int(evidence.chapter),
                    relation_id=evidence.relation_id,
                    evidence_id=evidence.id,
                    title=f"第{int(evidence.chapter)}回依据",
                    description=evidence.evidence_text,
                    trace_type="evidence",
                    sort_order=order,
                    importance=60,
                )
            )
            order += 1
        return items
```

- [ ] **Step 6: Add PostgreSQL store implementation**

Create `hlm_kg/postgres_store.py` implementing the same read methods as `ContentStore` using `psycopg.connect(database_url)`. Convert rows into existing dataclasses. Keep methods small:

```python
from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row

from hlm_kg.domain import (
    Chapter,
    ChapterAnnotation,
    ChapterReviewCard,
    Evidence,
    GraphRelation,
    KnowledgeCard,
    ProcessedMaterialSource,
    Topic,
    TraceItem,
)


class PostgresContentStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.common_entries: list[dict[str, Any]] = []
```

Implement `_fetchone`, `_fetchall`, and read methods. For this task, topics/common entries may remain JSON fallback if not present in PostgreSQL by accepting optional `fallback_store`:

```python
    def __init__(self, database_url: str, fallback_store: Any | None = None) -> None:
        self.database_url = database_url
        self.fallback_store = fallback_store
        self.common_entries = list(getattr(fallback_store, "common_entries", []))
```

Use fallback for `topics`, `topic`, and any missing common entry behavior.

- [ ] **Step 7: Wire web app store selection**

Modify `hlm_kg/web_app.py`:

```python
from hlm_kg.postgres_config import load_database_url, parse_bool
from hlm_kg.postgres_store import PostgresContentStore
```

Change `create_app_context` signature:

```python
    use_postgres_store: bool = False,
```

Inside:

```python
    json_store = ContentStore.from_paths(manifest_path, data_dir)
    if use_postgres_store or parse_bool(os.environ.get("HLM_CONTENT_STORE") == "postgres"):
        database_url = load_database_url()
        store = PostgresContentStore(database_url, fallback_store=json_store) if database_url else json_store
    else:
        store = json_store
```

Use `store` in returned context.

- [ ] **Step 8: Add annotations and trace items to API payloads**

Modify `handle_api_request`:

For chapters payload add:

```python
"annotations": [_camel(asdict(item)) for item in context.store.annotations_for_chapter(number)],
```

For cards payload:

```python
trace_items = context.store.trace_items_for_entity(card_id)
...
"traceItems": [_camel(asdict(item)) for item in trace_items],
```

- [ ] **Step 9: Run focused tests**

Run:

```bash
pytest tests/test_postgres_store.py tests/test_content_store.py tests/test_web_app.py -q
```

Expected: PASS.

- [ ] **Step 10: Run full tests**

Run:

```bash
pytest -q
```

Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add hlm_kg/domain.py hlm_kg/content_store.py hlm_kg/postgres_store.py hlm_kg/web_app.py tests/test_postgres_store.py tests/test_content_store.py tests/test_web_app.py
git commit -m "feat: expose trace graph through content API"
```

---

### Task 4: Frontend Annotation And Trace Navigation

**Files:**
- Modify: `static/app.js`
- Modify: `static/styles.css`
- Modify: `tests/test_web_app.py`

**Interfaces:**
- Consumes: API fields from Task 3: chapter `annotations`, card `traceItems`.
- Produces: original text rendered from offset-based annotations, not name replacement.
- Produces: trace buttons with `data-trace-chapter-number` and optional `data-trace-id`.

- [ ] **Step 1: Write failing static behavior tests**

Append to `tests/test_web_app.py`:

```python
def test_static_chapter_view_uses_offset_annotations_not_name_replacement():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "renderAnnotatedOriginalText(text, annotations)" in js
    assert "data-annotation-id" in js
    assert "data-card-id" in js
    assert "sort((left, right) => left.startOffset - right.startOffset" in js


def test_static_knowledge_panel_renders_trace_jump_buttons():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "renderTraceItems" in js
    assert "data-trace-chapter-number" in js
    assert "traceItems" in js


def test_static_styles_include_trace_and_annotation_states():
    css = Path("static/styles.css").read_text(encoding="utf-8")

    assert ".trace-list" in css
    assert ".annotation-link" in css
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
pytest tests/test_web_app.py -q
```

Expected: FAIL because the static files still use name-replacement rendering.

- [ ] **Step 3: Replace annotation renderer**

Modify `static/app.js`:

```javascript
function renderAnnotatedOriginalText(text, annotations = []) {
  if (!annotations.length) return escapeHtml(text);
  const sortedAnnotations = [...annotations]
    .filter((item) => item.entityId && item.startOffset >= 0 && item.endOffset > item.startOffset)
    .sort((left, right) => left.startOffset - right.startOffset || right.endOffset - left.endOffset);
  let cursor = 0;
  let html = "";
  sortedAnnotations.forEach((annotation) => {
    if (annotation.startOffset < cursor) return;
    html += escapeHtml(text.slice(cursor, annotation.startOffset));
    const label = text.slice(annotation.startOffset, annotation.endOffset);
    html += `<button class="annotation-link" data-annotation-id="${escapeHtml(annotation.id)}" data-card-id="${escapeHtml(annotation.entityId)}">${escapeHtml(label)}</button>`;
    cursor = annotation.endOffset;
  });
  html += escapeHtml(text.slice(cursor));
  return html;
}
```

- [ ] **Step 4: Add trace renderer**

Modify `static/app.js`:

```javascript
function renderTraceItems(traceItems = []) {
  if (!traceItems.length) return "<li>暂无可靠资料</li>";
  return traceItems
    .map(
      (item) =>
        `<li><button class="trace-link" data-trace-chapter-number="${escapeHtml(item.chapter)}" data-trace-id="${escapeHtml(item.id)}">${escapeHtml(item.title)}</button><p>${escapeHtml(item.description)}</p></li>`,
    )
    .join("");
}
```

In `loadKnowledgeCard`, add:

```javascript
const traceItems = renderTraceItems(data.traceItems || []);
```

And panel HTML section:

```html
<h4>全书线索</h4>
<ul class="trace-list">${traceItems}</ul>
```

- [ ] **Step 5: Use annotations in chapter rendering**

Modify `loadChapter` original text section:

```javascript
<section><h4>原文</h4><pre class="annotated-original">${renderAnnotatedOriginalText(data.originalText, data.annotations || [])}</pre></section>
```

- [ ] **Step 6: Add trace click handling**

Modify document click listener:

```javascript
  if (target.matches("[data-trace-chapter-number]")) {
    showView("chapters");
    loadChapter(Number(target.dataset.traceChapterNumber));
  }
```

Keep existing `[data-chapter-number]` behavior.

- [ ] **Step 7: Add styles**

Modify `static/styles.css`:

```css
.annotation-link {
  min-height: 0;
  padding: 0 2px;
  border: 0;
  border-bottom: 1px solid #7d6f52;
  border-radius: 0;
  background: #fff6cc;
  color: #3d3524;
  font: inherit;
  line-height: inherit;
}

.trace-list {
  display: grid;
  gap: 10px;
  padding-left: 0;
  list-style: none;
}

.trace-list li {
  border-left: 3px solid #5f7f71;
  padding-left: 10px;
}

.trace-list p {
  margin: 6px 0 0;
}

.trace-link {
  min-height: 32px;
  padding: 4px 8px;
}
```

- [ ] **Step 8: Run focused tests**

Run:

```bash
pytest tests/test_web_app.py -q
```

Expected: PASS.

- [ ] **Step 9: Run full tests**

Run:

```bash
pytest -q
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add static/app.js static/styles.css tests/test_web_app.py
git commit -m "feat: navigate chapter traces from annotations"
```

---

### Task 5: Live PostgreSQL Smoke Verification And Documentation

**Files:**
- Create: `docs/postgres_trace_graph.md`
- Create: `tests/test_postgres_docs.py`

**Interfaces:**
- Consumes: all previous tasks.
- Produces: operator instructions for `.env`, migration, seed import, web launch, and smoke checks.

- [ ] **Step 1: Write failing docs test**

Create `tests/test_postgres_docs.py`:

```python
from pathlib import Path


def test_postgres_trace_graph_docs_cover_safe_operations():
    text = Path("docs/postgres_trace_graph.md").read_text(encoding="utf-8")

    assert "DATABASE_URL" in text
    assert "make postgres-migrate" in text
    assert "make postgres-import-seed" in text
    assert "HLM_CONTENT_STORE=postgres" in text
    assert "不要提交 `.env`" in text
```

- [ ] **Step 2: Run docs test to verify RED**

Run:

```bash
pytest tests/test_postgres_docs.py -q
```

Expected: FAIL because docs file does not exist.

- [ ] **Step 3: Add docs**

Create `docs/postgres_trace_graph.md`:

```markdown
# PostgreSQL 信息卡线索数据层

本项目可以使用 PostgreSQL 承载章节、章节卡、信息卡、关系、证据、原文标注和全书线索。PostgreSQL 模式是可选模式；没有配置时仍使用 `data/app/*.json`。

## 环境变量

在本地 `.env` 配置：

```bash
DATABASE_URL=postgresql://用户:密码@主机:5432/数据库名
PGVECTOR_AVAILABLE=true
HLM_CONTENT_STORE=postgres
```

不要提交 `.env`，不要在 Issue、PR 或日志中粘贴真实密码。

## 初始化

```bash
make postgres-migrate
make postgres-import-seed
```

## 启动网站

```bash
HLM_CONTENT_STORE=postgres make web
```

章节接口会返回 `annotations`，信息卡接口会返回 `traceItems`。前端用这些结构渲染原文内标注、信息卡侧边栏和线索跳转。

## 安全边界

用户可见内容必须来自原文、章节卡、关系或证据数据。资料不足时显示空状态，不用模型常识补全。
```

- [ ] **Step 4: Run docs test**

Run:

```bash
pytest tests/test_postgres_docs.py -q
```

Expected: PASS.

- [ ] **Step 5: Run optional live database smoke**

If `.env` contains `DATABASE_URL`, run:

```bash
python scripts/migrate_postgres.py
python scripts/import_postgres_seed.py
HLM_CONTENT_STORE=postgres python - <<'PY'
from pathlib import Path
from hlm_kg.web_app import create_app_context, handle_api_request

context = create_app_context(
    manifest_path=Path("book/chapters_manifest.json"),
    data_dir=Path("data/app"),
    static_dir=Path("static"),
    use_postgres_store=True,
)
status, chapter = handle_api_request(context, "GET", "/api/chapters/27")
print(status, chapter["chapter"]["number"], len(chapter["originalText"]), len(chapter["annotations"]))
status, card = handle_api_request(context, "GET", "/api/cards/card-lindaiyu")
print(status, card["card"]["name"], len(card["traceItems"]))
PY
```

Expected: first line starts with `200 27`, second line starts with `200 林黛玉`. Do not print `DATABASE_URL`.

- [ ] **Step 6: Run full tests**

Run:

```bash
pytest -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add docs/postgres_trace_graph.md tests/test_postgres_docs.py
git commit -m "docs: document postgres trace graph workflow"
```

---

## Self-Review

- Spec coverage: #31 goals are covered by schema/migration, seed import, store/API, frontend navigation, live smoke docs.
- Placeholder scan: no TBD/TODO placeholders are intentionally left; optional live smoke has exact commands and expected output shape.
- Type consistency: `ChapterAnnotation` and `TraceItem` are defined in Task 3 and consumed by API/frontend tasks.
- Risk: Chinese full-text search and embedding query UX are not implemented in this issue; schema keeps `embeddings` ready for future work.

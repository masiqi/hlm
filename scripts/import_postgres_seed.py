from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hlm_kg.annotation_builder import generated_annotation_rows
from hlm_kg.postgres_config import load_database_url, load_dotenv


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
    entity_trace_cache: list[dict[str, Any]]
    entity_graph_cache: list[dict[str, Any]]


def build_seed_records(manifest_path: Path, data_dir: Path) -> SeedRecords:
    manifest = _read_json(manifest_path)
    chapter_cards = list(_read_json(data_dir / "chapter_review_cards.json"))
    knowledge_cards = list(_read_json(data_dir / "knowledge_cards.json"))
    relations = list(_read_json(data_dir / "graph_relations.json"))
    evidence = list(_read_json(data_dir / "evidence.json"))
    entity_trace_cache_path = data_dir / "entity_trace_cache.json"
    entity_trace_cache = _read_json(entity_trace_cache_path) if entity_trace_cache_path.exists() else {}
    entity_graph_cache_path = data_dir / "entity_graph_cache.json"
    entity_graph_cache = _read_json(entity_graph_cache_path) if entity_graph_cache_path.exists() else {}
    relation_lookup = {str(row["id"]): row for row in relations}
    evidence_lookup = {str(row["id"]): row for row in evidence}
    entity_lookup = {str(row["id"]): row for row in knowledge_cards}

    chapters = []
    chapter_text_by_number: dict[int, str] = {}
    for item in manifest["chapters"]:
        number = int(item["number"])
        path = Path(item["file_path"])
        original_text = path.read_text(encoding="utf-8")
        chapter_text_by_number[number] = original_text
        chapters.append(
            {
                "id": f"chapter-{number:03d}",
                "number": number,
                "title": str(item["title"]),
                "source_file": str(path),
                "original_text": original_text,
                "metadata": {},
            }
        )

    annotations = []
    target_lookup = _annotation_target_lookup(knowledge_cards)
    for card in chapter_cards:
        chapter_number = int(card["chapter"])
        cards_for_chapter = [entity_lookup[card_id] for card_id in card.get("key_characters", []) if card_id in entity_lookup]
        annotations.extend(
            annotation_rows_for_chapter(
                chapter_number,
                chapter_text_by_number[chapter_number],
                cards_for_chapter,
                review_annotations=list(card.get("annotations", [])),
                target_lookup=target_lookup,
            )
        )

    trace_items = []
    for card in knowledge_cards:
        trace_items.extend(trace_rows_for_card(card, relation_lookup, evidence_lookup))

    return SeedRecords(
        chapters=chapters,
        chapter_cards=[_chapter_card_row(row) for row in chapter_cards],
        entities=[_entity_row(row) for row in knowledge_cards],
        aliases=[_alias_row(row) for row in knowledge_cards],
        relations=[_relation_row(row) for row in relations],
        evidence=[_evidence_row(row) for row in evidence],
        annotations=annotations,
        trace_items=trace_items,
        entity_trace_cache=entity_trace_cache_rows(entity_trace_cache),
        entity_graph_cache=entity_graph_cache_rows(entity_graph_cache),
    )


def annotation_rows_for_chapter(
    chapter_number: int,
    original_text: str,
    cards: list[dict[str, Any]],
    *,
    review_annotations: list[Any] | None = None,
    target_lookup: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    generated_rows = generated_annotation_rows(
        chapter_number,
        original_text,
        review_annotations or [],
        target_lookup=target_lookup,
        keep_unresolved_target=target_lookup is None,
    )
    if generated_rows:
        return [row for row in generated_rows if row.get("entity_id")]
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


def _annotation_target_lookup(knowledge_cards: list[dict[str, Any]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for card in knowledge_cards:
        card_id = str(card.get("id") or "").strip()
        if not card_id:
            continue
        lookup[card_id] = card_id
        name = str(card.get("name") or "").strip()
        if name:
            lookup[name] = card_id
    return lookup


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
        for chapter in _relation_chapters(relation.get("chapters", []), evidence):
            rows.append(
                {
                    "id": f"trace-{card['id']}-{relation['id']}-{chapter:03d}",
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


def entity_trace_cache_rows(cache: Any) -> list[dict[str, Any]]:
    if not isinstance(cache, dict):
        return []
    rows: list[dict[str, Any]] = []
    for chapter_key, chapter_cache in cache.items():
        if not isinstance(chapter_cache, dict):
            continue
        try:
            chapter_number = int(chapter_key)
        except (TypeError, ValueError):
            continue
        for entity_name, payload in chapter_cache.items():
            if not isinstance(payload, dict):
                continue
            clean_name = str(entity_name).strip()
            if not clean_name:
                continue
            rows.append(
                {
                    "id": f"trace-cache-{chapter_number:03d}-{clean_name}",
                    "chapter_number": chapter_number,
                    "entity_name": clean_name,
                    "trace_items": list(payload.get("trace_items", [])),
                    "theme_extensions": list(payload.get("theme_extensions", [])),
                    "metadata": {},
                }
            )
    return rows


def entity_graph_cache_rows(cache: Any) -> list[dict[str, Any]]:
    if not isinstance(cache, dict):
        return []
    rows: list[dict[str, Any]] = []
    for entity_name, payload in cache.items():
        if not isinstance(payload, dict):
            continue
        clean_name = str(entity_name).strip()
        if not clean_name:
            continue
        rows.append(
            {
                "entity_name": clean_name,
                "description": str(payload.get("description") or ""),
                "neighbors": list(payload.get("neighbors") or []),
                "extended_neighbors": list(payload.get("extended_neighbors") or []),
                "raw_graph": dict(payload.get("raw_graph") or {}),
                "metadata": dict(payload.get("metadata") or {}),
            }
        )
    return rows


def upsert_seed_records(database_url: str, records: SeedRecords) -> None:
    import psycopg

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
            _upsert_entity_trace_cache(cur, records.entity_trace_cache)
            _upsert_entity_graph_cache(cur, records.entity_graph_cache)
        conn.commit()


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    manifest_path = Path(args[0]) if len(args) >= 1 else Path("book/chapters_manifest.json")
    data_dir = Path(args[1]) if len(args) >= 2 else Path("data/app")
    database_url = load_database_url(load_dotenv()) or load_database_url()
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


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def _relation_chapters(chapters: list[Any], evidence: dict[str, Any] | None) -> list[int]:
    if chapters:
        return [int(chapter) for chapter in chapters]
    if evidence is not None and evidence.get("chapter") is not None:
        return [int(evidence["chapter"])]
    return []


def _jsonb(value: Any) -> Any:
    from psycopg.types.json import Jsonb

    return Jsonb(value)


def _upsert_chapters(cur: Any, rows: list[dict[str, Any]]) -> None:
    cur.executemany(
        """
        INSERT INTO chapters (id, number, title, source_file, original_text, metadata)
        VALUES (%(id)s, %(number)s, %(title)s, %(source_file)s, %(original_text)s, %(metadata)s)
        ON CONFLICT (id) DO UPDATE SET
            number = EXCLUDED.number,
            title = EXCLUDED.title,
            source_file = EXCLUDED.source_file,
            original_text = EXCLUDED.original_text,
            metadata = EXCLUDED.metadata,
            updated_at = now()
        """,
        [{**row, "metadata": _jsonb(row["metadata"])} for row in rows],
    )


def _upsert_chapter_cards(cur: Any, rows: list[dict[str, Any]]) -> None:
    cur.executemany(
        """
        INSERT INTO chapter_cards (
            id, chapter_id, summary, plot_chain, key_events, key_characters, foreshadowing,
            later_association_relation_ids, quotable_fact_ids, retrieval_tags, understanding_focus,
            raw_card, prompt_name, prompt_version, generated_at
        )
        VALUES (
            %(id)s, (SELECT id FROM chapters WHERE number = %(chapter_number)s), %(summary)s,
            %(plot_chain)s, %(key_events)s, %(key_characters)s, %(foreshadowing)s,
            %(later_association_relation_ids)s, %(quotable_fact_ids)s, %(retrieval_tags)s,
            %(understanding_focus)s, %(raw_card)s, %(prompt_name)s, %(prompt_version)s, %(generated_at)s
        )
        ON CONFLICT (id) DO UPDATE SET
            chapter_id = EXCLUDED.chapter_id,
            summary = EXCLUDED.summary,
            plot_chain = EXCLUDED.plot_chain,
            key_events = EXCLUDED.key_events,
            key_characters = EXCLUDED.key_characters,
            foreshadowing = EXCLUDED.foreshadowing,
            later_association_relation_ids = EXCLUDED.later_association_relation_ids,
            quotable_fact_ids = EXCLUDED.quotable_fact_ids,
            retrieval_tags = EXCLUDED.retrieval_tags,
            understanding_focus = EXCLUDED.understanding_focus,
            raw_card = EXCLUDED.raw_card,
            prompt_name = EXCLUDED.prompt_name,
            prompt_version = EXCLUDED.prompt_version,
            generated_at = EXCLUDED.generated_at,
            updated_at = now()
        """,
        [
            {
                **row,
                "plot_chain": _jsonb(row["plot_chain"]),
                "key_events": _jsonb(row["key_events"]),
                "key_characters": _jsonb(row["key_characters"]),
                "foreshadowing": _jsonb(row["foreshadowing"]),
                "later_association_relation_ids": _jsonb(row["later_association_relation_ids"]),
                "quotable_fact_ids": _jsonb(row["quotable_fact_ids"]),
                "retrieval_tags": _jsonb(row["retrieval_tags"]),
                "understanding_focus": _jsonb(row["understanding_focus"]),
                "raw_card": _jsonb(row["raw_card"]),
            }
            for row in rows
        ],
    )


def _upsert_entities(cur: Any, rows: list[dict[str, Any]]) -> None:
    cur.executemany(
        """
        INSERT INTO entities (id, name, type, brief, description, metadata)
        VALUES (%(id)s, %(name)s, %(type)s, %(brief)s, %(description)s, %(metadata)s)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            type = EXCLUDED.type,
            brief = EXCLUDED.brief,
            description = EXCLUDED.description,
            metadata = EXCLUDED.metadata,
            updated_at = now()
        """,
        [{**row, "metadata": _jsonb(row["metadata"])} for row in rows],
    )


def _upsert_aliases(cur: Any, rows: list[dict[str, Any]]) -> None:
    cur.executemany(
        """
        INSERT INTO entity_aliases (id, entity_id, alias, alias_type)
        VALUES (%(id)s, %(entity_id)s, %(alias)s, %(alias_type)s)
        ON CONFLICT (id) DO UPDATE SET
            entity_id = EXCLUDED.entity_id,
            alias = EXCLUDED.alias,
            alias_type = EXCLUDED.alias_type
        """,
        rows,
    )


def _upsert_relations(cur: Any, rows: list[dict[str, Any]]) -> None:
    cur.executemany(
        """
        INSERT INTO relations (
            id, subject_entity_id, predicate, object_entity_id, chapters, evidence_ids,
            provenance, confidence, description, metadata
        )
        VALUES (
            %(id)s, %(subject_entity_id)s, %(predicate)s, %(object_entity_id)s, %(chapters)s,
            %(evidence_ids)s, %(provenance)s, %(confidence)s, %(description)s, %(metadata)s
        )
        ON CONFLICT (id) DO UPDATE SET
            subject_entity_id = EXCLUDED.subject_entity_id,
            predicate = EXCLUDED.predicate,
            object_entity_id = EXCLUDED.object_entity_id,
            chapters = EXCLUDED.chapters,
            evidence_ids = EXCLUDED.evidence_ids,
            provenance = EXCLUDED.provenance,
            confidence = EXCLUDED.confidence,
            description = EXCLUDED.description,
            metadata = EXCLUDED.metadata,
            updated_at = now()
        """,
        [{**row, "chapters": _jsonb(row["chapters"]), "evidence_ids": _jsonb(row["evidence_ids"]), "metadata": _jsonb(row["metadata"])} for row in rows],
    )


def _upsert_evidence(cur: Any, rows: list[dict[str, Any]]) -> None:
    cur.executemany(
        """
        INSERT INTO evidence (
            id, chapter_id, source_type, location, quote, evidence_text, entity_ids,
            relation_id, confidence, provenance, derived_from_ids, metadata
        )
        VALUES (
            %(id)s, (SELECT id FROM chapters WHERE number = %(chapter_number)s), %(source_type)s,
            %(location)s, %(quote)s, %(evidence_text)s, %(entity_ids)s, %(relation_id)s,
            %(confidence)s, %(provenance)s, %(derived_from_ids)s, %(metadata)s
        )
        ON CONFLICT (id) DO UPDATE SET
            chapter_id = EXCLUDED.chapter_id,
            source_type = EXCLUDED.source_type,
            location = EXCLUDED.location,
            quote = EXCLUDED.quote,
            evidence_text = EXCLUDED.evidence_text,
            entity_ids = EXCLUDED.entity_ids,
            relation_id = EXCLUDED.relation_id,
            confidence = EXCLUDED.confidence,
            provenance = EXCLUDED.provenance,
            derived_from_ids = EXCLUDED.derived_from_ids,
            metadata = EXCLUDED.metadata
        """,
        [{**row, "entity_ids": _jsonb(row["entity_ids"]), "derived_from_ids": _jsonb(row["derived_from_ids"]), "metadata": _jsonb(row["metadata"])} for row in rows],
    )


def _upsert_annotations(cur: Any, rows: list[dict[str, Any]]) -> None:
    cur.executemany(
        """
        INSERT INTO chapter_annotations (
            id, chapter_id, start_offset, end_offset, surface_text, annotation_type,
            entity_id, relation_id, evidence_id, display_priority, metadata
        )
        VALUES (
            %(id)s, (SELECT id FROM chapters WHERE number = %(chapter_number)s), %(start_offset)s,
            %(end_offset)s, %(surface_text)s, %(annotation_type)s, %(entity_id)s, %(relation_id)s,
            %(evidence_id)s, %(display_priority)s, %(metadata)s
        )
        ON CONFLICT (id) DO UPDATE SET
            chapter_id = EXCLUDED.chapter_id,
            start_offset = EXCLUDED.start_offset,
            end_offset = EXCLUDED.end_offset,
            surface_text = EXCLUDED.surface_text,
            annotation_type = EXCLUDED.annotation_type,
            entity_id = EXCLUDED.entity_id,
            relation_id = EXCLUDED.relation_id,
            evidence_id = EXCLUDED.evidence_id,
            display_priority = EXCLUDED.display_priority,
            metadata = EXCLUDED.metadata
        """,
        [{**row, "metadata": _jsonb(row["metadata"])} for row in rows],
    )


def _upsert_trace_items(cur: Any, rows: list[dict[str, Any]]) -> None:
    cur.executemany(
        """
        INSERT INTO trace_items (
            id, entity_id, chapter_id, relation_id, evidence_id, title, description,
            trace_type, sort_order, importance, metadata
        )
        VALUES (
            %(id)s, %(entity_id)s, (SELECT id FROM chapters WHERE number = %(chapter_number)s),
            %(relation_id)s, %(evidence_id)s, %(title)s, %(description)s, %(trace_type)s,
            %(sort_order)s, %(importance)s, %(metadata)s
        )
        ON CONFLICT (id) DO UPDATE SET
            entity_id = EXCLUDED.entity_id,
            chapter_id = EXCLUDED.chapter_id,
            relation_id = EXCLUDED.relation_id,
            evidence_id = EXCLUDED.evidence_id,
            title = EXCLUDED.title,
            description = EXCLUDED.description,
            trace_type = EXCLUDED.trace_type,
            sort_order = EXCLUDED.sort_order,
            importance = EXCLUDED.importance,
            metadata = EXCLUDED.metadata
        """,
        [{**row, "metadata": _jsonb(row["metadata"])} for row in rows],
    )


def _upsert_entity_trace_cache(cur: Any, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    cur.executemany(
        """
        INSERT INTO entity_trace_cache (
            id, chapter_id, entity_name, trace_items, theme_extensions, metadata
        )
        VALUES (
            %(id)s, (SELECT id FROM chapters WHERE number = %(chapter_number)s),
            %(entity_name)s, %(trace_items)s, %(theme_extensions)s, %(metadata)s
        )
        ON CONFLICT (id) DO UPDATE SET
            chapter_id = EXCLUDED.chapter_id,
            entity_name = EXCLUDED.entity_name,
            trace_items = EXCLUDED.trace_items,
            theme_extensions = EXCLUDED.theme_extensions,
            metadata = EXCLUDED.metadata,
            updated_at = now()
        """,
        [
            {
                **row,
                "trace_items": _jsonb(row["trace_items"]),
                "theme_extensions": _jsonb(row["theme_extensions"]),
                "metadata": _jsonb(row["metadata"]),
            }
            for row in rows
        ],
    )


def _upsert_entity_graph_cache(cur: Any, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    cur.executemany(
        """
        INSERT INTO entity_graph_cache (
            entity_name, description, neighbors, extended_neighbors, raw_graph, metadata
        )
        VALUES (
            %(entity_name)s, %(description)s, %(neighbors)s, %(extended_neighbors)s, %(raw_graph)s, %(metadata)s
        )
        ON CONFLICT (entity_name) DO UPDATE SET
            description = EXCLUDED.description,
            neighbors = EXCLUDED.neighbors,
            extended_neighbors = EXCLUDED.extended_neighbors,
            raw_graph = EXCLUDED.raw_graph,
            metadata = EXCLUDED.metadata,
            updated_at = now()
        """,
        [
            {
                **row,
                "neighbors": _jsonb(row["neighbors"]),
                "extended_neighbors": _jsonb(row["extended_neighbors"]),
                "raw_graph": _jsonb(row["raw_graph"]),
                "metadata": _jsonb(row["metadata"]),
            }
            for row in rows
        ],
    )


if __name__ == "__main__":
    raise SystemExit(main())

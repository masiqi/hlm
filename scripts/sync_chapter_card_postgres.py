from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hlm_kg.postgres_config import load_database_url, load_dotenv
from hlm_kg.annotation_builder import generated_annotation_rows
from scripts.import_chapter_cards import normalize_import_cards
from scripts.import_postgres_seed import _chapter_card_row, _upsert_annotations, _upsert_chapter_cards


def load_single_chapter_card_row(input_path: Path, *, expected_chapter: int) -> dict[str, Any]:
    raw_payload = json.loads(input_path.read_text(encoding="utf-8"))
    if isinstance(raw_payload, dict):
        raw_cards = [raw_payload]
    elif isinstance(raw_payload, list):
        raw_cards = raw_payload
    else:
        raise ValueError(f"{input_path} must contain one JSON object or one-item JSON array")
    cards = normalize_import_cards(raw_cards)

    if len(cards) != 1:
        raise ValueError(f"{input_path} must contain exactly one chapter card")
    card = cards[0]
    chapter = int(card["chapter"])
    if chapter != expected_chapter:
        raise ValueError(f"input chapter {chapter} does not match --chapter {expected_chapter}")
    return _chapter_card_row(card)


def upsert_single_chapter_card(database_url: str, row: dict[str, Any]) -> None:
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            _upsert_chapter_cards(cur, [row])
            original_text = _chapter_text_for_sync(cur, int(row["chapter_number"]))
            target_lookup = _annotation_target_lookup_for_sync(cur)
            replace_generated_annotations_for_chapter(cur, row, original_text=original_text, target_lookup=target_lookup)
        conn.commit()


def _chapter_text_for_sync(cur: Any, chapter_number: int) -> str:
    cur.execute("SELECT original_text FROM chapters WHERE number = %s", (chapter_number,))
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"chapter {chapter_number} does not exist in PostgreSQL")
    return str(row["original_text"])


def _annotation_target_lookup_for_sync(cur: Any) -> dict[str, str]:
    cur.execute("SELECT id, name FROM entities")
    rows = cur.fetchall()
    lookup: dict[str, str] = {}
    for row in rows:
        entity_id = str(row.get("id") or "").strip()
        if not entity_id:
            continue
        lookup[entity_id] = entity_id
        name = str(row.get("name") or "").strip()
        if name:
            lookup[name] = entity_id
    return lookup


def replace_generated_annotations_for_chapter(
    cur: Any,
    row: dict[str, Any],
    *,
    original_text: str,
    target_lookup: dict[str, str] | None = None,
) -> None:
    chapter_number = int(row.get("chapter_number") or row["chapter"])
    cur.execute(
        """
        DELETE FROM chapter_annotations
        WHERE chapter_id = (SELECT id FROM chapters WHERE number = %s)
          AND metadata->>'source' = 'chapter_card.annotations'
        """,
        (chapter_number,),
    )
    annotation_rows = [
        item
        for item in generated_annotation_rows(
            chapter_number,
            original_text,
            list((row.get("raw_card") or row).get("annotations", [])),
            target_lookup=target_lookup,
            keep_unresolved_target=target_lookup is None,
        )
        if item.get("entity_id")
    ]
    if annotation_rows:
        _upsert_annotations(cur, annotation_rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync one checked chapter card into PostgreSQL.")
    parser.add_argument("--chapter", required=True, type=int, help="Chapter number in 1..120.")
    parser.add_argument("--input", required=True, type=Path, help="Per-chapter AppImportJSON file.")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.chapter < 1 or args.chapter > 120:
        print("error: --chapter must be in 1..120", file=sys.stderr)
        return 2

    database_url = load_database_url(load_dotenv()) or load_database_url()
    if database_url is None:
        print("error: DATABASE_URL is not set", file=sys.stderr)
        return 2

    try:
        row = load_single_chapter_card_row(args.input, expected_chapter=args.chapter)
        upsert_single_chapter_card(database_url, row)
    except Exception as exc:  # noqa: BLE001 - CLI should report actionable errors.
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"PostgreSQL chapter card synced: {args.chapter:03d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

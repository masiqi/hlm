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
from scripts.import_chapter_cards import normalize_import_cards
from scripts.import_postgres_seed import _chapter_card_row, _upsert_chapter_cards


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

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            _upsert_chapter_cards(cur, [row])
        conn.commit()


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

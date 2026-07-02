from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_PROMPT_NAME = "hongloumeng_chapter_review_card"
DEFAULT_PROMPT_VERSION = "2026-07-01"

REQUIRED_FIELDS = [
    "chapter",
    "plain_summary",
    "plot_chain",
    "key_events",
    "key_characters",
    "current_chapter_foreshadowing_signals",
    "later_association_relation_ids",
    "quotable_fact_ids",
    "retrieval_tags",
    "understanding_focus",
]


def load_import_cards(input_path: Path) -> list[dict]:
    raw_cards = _read_cards(input_path)
    cards = [_normalize_card(raw_card, index) for index, raw_card in enumerate(raw_cards)]
    return sorted(cards, key=lambda card: card["chapter"])


def write_import_cards(cards: list[dict], output_path: Path) -> None:
    sorted_cards = sorted(cards, key=lambda card: int(card["chapter"]))
    try:
        output_path.write_text(
            json.dumps(sorted_cards, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise ValueError(f"cannot write {output_path}: {exc}") from exc


def _read_cards(input_path: Path) -> list[Any]:
    try:
        data = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {input_path}: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"cannot read {input_path}: {exc}") from exc

    if not isinstance(data, list):
        raise ValueError(f"{input_path} must contain a JSON array")
    return data


def _normalize_card(raw_card: Any, index: int) -> dict:
    if not isinstance(raw_card, dict):
        raise ValueError(f"card[{index}] must be a JSON object")

    _require_fields(raw_card, index)
    chapter = _normalize_chapter(raw_card["chapter"], index)
    plain_summary = _normalize_plain_summary(raw_card["plain_summary"], index)
    plot_chain = _normalize_list(raw_card["plot_chain"], index, "plot_chain")
    if not plot_chain:
        raise ValueError(f"card[{index}] plot_chain must be non-empty")

    return {
        "id": str(raw_card.get("id") or f"review-{chapter:03d}"),
        "chapter": chapter,
        "source": _normalize_source(raw_card.get("source"), index),
        "plain_summary": plain_summary,
        "plot_chain": plot_chain,
        "key_events": _normalize_list(raw_card["key_events"], index, "key_events"),
        "key_characters": _normalize_list(raw_card["key_characters"], index, "key_characters"),
        "current_chapter_foreshadowing_signals": _normalize_list(
            raw_card["current_chapter_foreshadowing_signals"],
            index,
            "current_chapter_foreshadowing_signals",
        ),
        "later_association_relation_ids": _normalize_list(
            raw_card["later_association_relation_ids"],
            index,
            "later_association_relation_ids",
        ),
        "quotable_fact_ids": _normalize_list(raw_card["quotable_fact_ids"], index, "quotable_fact_ids"),
        "retrieval_tags": _normalize_list(raw_card["retrieval_tags"], index, "retrieval_tags"),
        "understanding_focus": _normalize_list(raw_card["understanding_focus"], index, "understanding_focus"),
    }


def _require_fields(raw_card: dict, index: int) -> None:
    missing = [field for field in REQUIRED_FIELDS if field not in raw_card]
    if missing:
        raise ValueError(f"card[{index}] missing required fields: {', '.join(missing)}")


def _normalize_chapter(value: Any, index: int) -> int:
    try:
        chapter = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"card[{index}] chapter must be an integer in 1..120") from exc

    if chapter < 1 or chapter > 120:
        raise ValueError(f"card[{index}] chapter must be an integer in 1..120")
    return chapter


def _normalize_plain_summary(value: Any, index: int) -> str:
    summary = str(value).strip() if value is not None else ""
    if not summary:
        raise ValueError(f"card[{index}] plain_summary must be non-empty")
    return summary


def _normalize_list(value: Any, index: int, field: str) -> list:
    if not isinstance(value, list):
        raise ValueError(f"card[{index}] {field} must be a list")
    return list(value)


def _normalize_source(value: Any, index: int) -> dict:
    if value is None:
        return {
            "prompt_name": DEFAULT_PROMPT_NAME,
            "prompt_version": DEFAULT_PROMPT_VERSION,
            "generated_at": None,
        }
    if not isinstance(value, dict):
        raise ValueError(f"card[{index}] source must be an object when provided")
    return dict(value)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("Usage: python scripts/import_chapter_cards.py INPUT_JSON OUTPUT_JSON", file=sys.stderr)
        return 2

    input_path = Path(args[0])
    output_path = Path(args[1])
    try:
        cards = load_import_cards(input_path)
        write_import_cards(cards, output_path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

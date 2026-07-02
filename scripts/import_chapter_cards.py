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
    "characters",
    "relationships",
    "places",
    "objects",
    "literary_texts",
    "modern_explanations",
    "later_associations",
    "annotations",
]

REFERENCE_FIELDS = {
    "key_characters": "knowledge_cards.json",
    "later_association_relation_ids": "graph_relations.json",
    "quotable_fact_ids": "evidence.json",
}

RENDERED_TEXT_FIELDS = [
    "plain_summary",
    "plot_chain",
    "key_events",
    "current_chapter_foreshadowing_signals",
    "understanding_focus",
    "characters",
    "relationships",
    "places",
    "objects",
    "literary_texts",
    "modern_explanations",
    "later_associations",
    "annotations",
]

FORBIDDEN_STUDENT_TERMS = [
    "LightRAG",
    "RAG",
    "知识图谱",
    "向量检索",
    "置信度",
    "模型分数",
    "标准答案",
    "题库",
    "下一题",
    "提交答案",
    "批改",
]


def load_import_cards(input_path: Path, data_dir: Path | None = None) -> list[dict]:
    raw_cards = _read_cards(input_path)
    cards = [_normalize_card(raw_card, index) for index, raw_card in enumerate(raw_cards)]
    _reject_duplicate_chapters(cards)
    if data_dir is not None:
        _validate_reference_ids(cards, data_dir)
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

    card = {
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
        "characters": _normalize_structured_list(raw_card["characters"], index, "characters"),
        "relationships": _normalize_structured_list(raw_card["relationships"], index, "relationships"),
        "places": _normalize_structured_list(raw_card["places"], index, "places"),
        "objects": _normalize_structured_list(raw_card["objects"], index, "objects"),
        "literary_texts": _normalize_structured_list(raw_card["literary_texts"], index, "literary_texts"),
        "modern_explanations": _normalize_structured_list(raw_card["modern_explanations"], index, "modern_explanations"),
        "later_associations": _normalize_structured_list(raw_card["later_associations"], index, "later_associations"),
        "annotations": _normalize_structured_list(raw_card["annotations"], index, "annotations"),
    }
    _reject_forbidden_student_terms(card, index)
    return card


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
    items: list[str] = []
    for item_index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"card[{index}] {field}[{item_index}] must be a non-empty string")
        items.append(item.strip())
    return items


def _normalize_structured_list(value: Any, index: int, field: str) -> list:
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


def _reject_duplicate_chapters(cards: list[dict]) -> None:
    seen: set[int] = set()
    duplicates: list[int] = []
    for card in cards:
        chapter = int(card["chapter"])
        if chapter in seen:
            duplicates.append(chapter)
        seen.add(chapter)
    if duplicates:
        raise ValueError(f"duplicate chapter cards: {duplicates}")


def _validate_reference_ids(cards: list[dict], data_dir: Path) -> None:
    known_ids = {field: _load_ids(data_dir / filename) for field, filename in REFERENCE_FIELDS.items()}
    for card in cards:
        chapter = card["chapter"]
        for field, allowed in known_ids.items():
            missing = [value for value in card[field] if value not in allowed]
            if missing:
                raise ValueError(f"chapter {chapter} {field} contains unknown ids: {missing}")


def _load_ids(path: Path) -> set[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read reference data {path}: {exc}") from exc
    if not isinstance(data, list):
        raise ValueError(f"reference data {path} must contain a JSON array")
    return {str(item.get("id")) for item in data if isinstance(item, dict) and item.get("id")}


def _reject_forbidden_student_terms(card: dict, index: int) -> None:
    for field in RENDERED_TEXT_FIELDS:
        for value in _iter_text(card[field]):
            for term in FORBIDDEN_STUDENT_TERMS:
                if term in value:
                    raise ValueError(f"card[{index}] {field} contains forbidden student-facing term: {term}")


def _iter_text(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _iter_text(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_text(item)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) not in {2, 3}:
        print("Usage: python scripts/import_chapter_cards.py INPUT_JSON OUTPUT_JSON [DATA_DIR]", file=sys.stderr)
        return 2

    input_path = Path(args[0])
    output_path = Path(args[1])
    data_dir = Path(args[2]) if len(args) == 3 else None
    try:
        cards = load_import_cards(input_path, data_dir=data_dir)
        write_import_cards(cards, output_path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

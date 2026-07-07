from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hlm_kg.topic_index import TopicIndexResult, build_topic_index


TOPIC_INDEX_FILES = {
    "topics": "topics.json",
    "evidence": "evidence.json",
    "knowledge_cards": "knowledge_cards.json",
    "graph_relations": "graph_relations.json",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the student-facing topic index from chapter review cards.")
    parser.add_argument("--data-dir", type=Path, default=Path("data/app"), help="Directory containing topic index JSON files.")
    parser.add_argument(
        "--review-cards",
        type=Path,
        default=Path("data/app/chapter_review_cards.json"),
        help="Chapter review card JSON file.",
    )
    parser.add_argument("--write", action="store_true", help="Write generated topic index files. Defaults to dry-run.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data_dir: Path = args.data_dir
    review_cards = _load_json_list(args.review_cards)
    result = build_topic_index(
        review_cards=review_cards,
        topics=_load_json_list(data_dir / TOPIC_INDEX_FILES["topics"]),
        evidence=_load_json_list(data_dir / TOPIC_INDEX_FILES["evidence"]),
        knowledge_cards=_load_json_list(data_dir / TOPIC_INDEX_FILES["knowledge_cards"]),
        graph_relations=_load_json_list(data_dir / TOPIC_INDEX_FILES["graph_relations"]),
    )

    mode = "write" if args.write else "dry-run"
    print(f"mode: {mode}")
    print(json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.write:
        _write_result(data_dir, result)
    return 0


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array")
    return data


def _write_result(data_dir: Path, result: TopicIndexResult) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    _write_json(data_dir / TOPIC_INDEX_FILES["topics"], result.topics)
    _write_json(data_dir / TOPIC_INDEX_FILES["evidence"], result.evidence)
    _write_json(data_dir / TOPIC_INDEX_FILES["knowledge_cards"], result.knowledge_cards)
    _write_json(data_dir / TOPIC_INDEX_FILES["graph_relations"], result.graph_relations)


def _write_json(path: Path, data: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())

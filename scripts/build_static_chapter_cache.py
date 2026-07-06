from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hlm_kg.web_app import chapter_payload, create_app_context
from scripts.build_entity_trace_cache import parse_chapter_selection


def cache_path_for_chapter(output_dir: Path, chapter: int) -> Path:
    return output_dir / f"{chapter:03d}.json"


def build_static_chapter_cache(*, context: Any, chapters: list[int], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for index, chapter in enumerate(chapters, start=1):
        payload = chapter_payload(context, chapter)
        path = cache_path_for_chapter(output_dir, chapter)
        path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        written.append(path)
        print(f"[{index}/{len(chapters)}] wrote static chapter cache: {path.name}", flush=True)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build static JSON cache files for chapter reading pages.")
    parser.add_argument("--chapters", default="1-120", help="Chapter selection, e.g. 1-3 or 1,2,3.")
    parser.add_argument("--manifest", type=Path, default=Path("book/chapters_manifest.json"))
    parser.add_argument("--data-dir", type=Path, default=Path("data/app"))
    parser.add_argument("--static-dir", type=Path, default=Path("static"))
    parser.add_argument("--output-dir", type=Path, default=Path("static/chapter_cache"))
    parser.add_argument("--postgres", action="store_true", default=True, help="Read chapter payloads from PostgreSQL.")
    parser.add_argument("--json-store", action="store_false", dest="postgres", help="Read chapter payloads from local JSON files.")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    try:
        chapters = parse_chapter_selection(args.chapters)
        context = create_app_context(
            manifest_path=args.manifest,
            data_dir=args.data_dir,
            static_dir=args.static_dir,
            use_env_content_store=args.postgres,
            use_postgres_store=args.postgres,
        )
        written = build_static_chapter_cache(context=context, chapters=chapters, output_dir=args.output_dir)
    except Exception as exc:  # noqa: BLE001 - CLI reports actionable failures.
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Static chapter cache built: {len(written)} chapters")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

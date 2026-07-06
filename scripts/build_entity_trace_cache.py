from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hlm_kg.postgres_config import load_database_url, load_dotenv
from hlm_kg.lightrag_client import LightRAGClient, LightRAGConfig
from hlm_kg.web_app import (
    _attach_generated_chapter_jumps,
    _clean_student_payload,
    _entity_trace_payload,
    _inline_entities_for_review_card,
    _sort_trace_items,
    _unique_dicts,
    create_app_context,
)
from scripts.import_postgres_seed import _upsert_entity_trace_cache, entity_trace_cache_rows


def parse_chapter_selection(value: str) -> list[int]:
    chapters: list[int] = []
    for part in value.split(","):
        clean = part.strip()
        if not clean:
            continue
        if "-" in clean:
            start_text, end_text = clean.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            chapters.extend(range(start, end + 1))
        else:
            chapters.append(int(clean))
    unique = sorted(dict.fromkeys(chapters))
    if any(chapter < 1 or chapter > 120 for chapter in unique):
        raise ValueError("chapters must be in 1..120")
    return unique


def build_entity_trace_cache(
    *,
    chapters: list[int],
    manifest_path: Path,
    data_dir: Path,
    static_dir: Path,
    use_postgres_store: bool,
    use_live_retrieval: bool = False,
    include_generated: bool = True,
) -> dict[str, dict[str, dict[str, Any]]]:
    context = create_app_context(
        manifest_path=manifest_path,
        data_dir=data_dir,
        static_dir=static_dir,
        use_env_retrieval=use_live_retrieval,
        use_env_content_store=use_postgres_store,
        use_postgres_store=use_postgres_store,
    )
    if use_live_retrieval and context.retrieval_client is None:
        raise RuntimeError("LIGHTRAG_BASE_URL is not set; cannot build entity trace cache")

    cache: dict[str, dict[str, dict[str, Any]]] = {}
    for chapter in chapters:
        review_card = context.store.maybe_review_card_for_chapter(chapter)
        if review_card is None:
            cache[str(chapter)] = {}
            continue
        inline_entities = _inline_entities_for_review_card(review_card)
        chapter_cache: dict[str, dict[str, Any]] = {}
        for entity in inline_entities:
            name = str(entity.get("name") or "").strip()
            if not name:
                continue
            payload = _entity_trace_payload(
                name,
                store=context.store,
                retrieval_client=context.retrieval_client,
                current_chapter=chapter,
                entity_type=str(entity.get("type") or ""),
                use_cache=False,
                include_generated=include_generated,
            )
            chapter_cache[name] = _clean_student_payload(payload)
        cache[str(chapter)] = chapter_cache
    return cache


def build_entity_trace_cache_for_context(
    *,
    context: Any,
    chapters: list[int],
    include_generated: bool = True,
    use_live_retrieval: bool = False,
) -> dict[str, dict[str, dict[str, Any]]]:
    if use_live_retrieval and context.retrieval_client is None:
        raise RuntimeError("LIGHTRAG_BASE_URL is not set; cannot build entity trace cache")

    cache: dict[str, dict[str, dict[str, Any]]] = {}
    for chapter in chapters:
        review_card = context.store.maybe_review_card_for_chapter(chapter)
        if review_card is None:
            cache[str(chapter)] = {}
            continue
        inline_entities = _inline_entities_for_review_card(review_card)
        direct_cache: dict[str, dict[str, Any]] = {}
        for entity in inline_entities:
            name = str(entity.get("name") or "").strip()
            if not name:
                continue
            payload = _entity_trace_payload(
                name,
                store=context.store,
                retrieval_client=context.retrieval_client if use_live_retrieval else None,
                current_chapter=chapter,
                entity_type=str(entity.get("type") or ""),
                use_cache=False,
                include_generated=include_generated,
            )
            direct_cache[name] = _clean_student_payload(payload)
        materialized_store = _TraceCacheOverlayStore(context.store, {str(chapter): direct_cache})
        _attach_generated_chapter_jumps(inline_entities, store=materialized_store, current_chapter=chapter)
        chapter_cache = {
            str(entity.get("name") or "").strip(): _trace_cache_payload_from_inline_entity(entity)
            for entity in inline_entities
            if str(entity.get("name") or "").strip()
        }
        cache[str(chapter)] = chapter_cache
    return cache


class _TraceCacheOverlayStore:
    def __init__(self, wrapped_store: Any, cache: dict[str, dict[str, dict[str, Any]]]) -> None:
        self.wrapped_store = wrapped_store
        self.cache = cache
        self.common_entries = getattr(wrapped_store, "common_entries", [])

    def __getattr__(self, name: str) -> Any:
        return getattr(self.wrapped_store, name)

    def entity_trace_payloads_for_chapter(self, current_chapter: int | None) -> dict[str, dict[str, Any]] | None:
        chapter_cache = self.cache.get(str(current_chapter or ""))
        return chapter_cache if isinstance(chapter_cache, dict) else None


def _trace_cache_payload_from_inline_entity(entity: dict[str, Any]) -> dict[str, Any]:
    trace_items = _sort_trace_items(
        _unique_dicts(
            [
                {
                    "chapter": item.get("chapter"),
                    "label": item.get("label"),
                    "description": item.get("description") or "",
                    "importance": item.get("importance") or 0,
                }
                for item in [
                    *list(entity.get("previousChapterJumps") or []),
                    *list(entity.get("laterChapterJumps") or []),
                    *list(entity.get("chapterJumps") or []),
                ]
                if isinstance(item, dict) and item.get("chapter") is not None
            ]
        )
    )
    return _clean_student_payload(
        {
            "trace_items": trace_items,
            "theme_extensions": list(entity.get("themeExtensions") or []),
        }
    )


def merge_cache(
    existing: dict[str, Any],
    generated: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    merged = dict(existing)
    for chapter, chapter_cache in generated.items():
        merged[chapter] = chapter_cache
    return merged


def merge_chapter_cache(existing: dict[str, Any], chapter: int, chapter_cache: dict[str, Any]) -> dict[str, Any]:
    return merge_cache(existing, {str(chapter): chapter_cache})


def chapters_to_build(chapters: list[int], existing: dict[str, Any], *, skip_existing: bool) -> list[int]:
    if not skip_existing:
        return chapters
    return [
        chapter
        for chapter in chapters
        if not isinstance(existing.get(str(chapter)), dict) or not existing.get(str(chapter))
    ]


def initial_cache(existing: dict[str, Any], *, replace: bool) -> dict[str, Any]:
    return {} if replace else dict(existing)


def final_cache(
    merged: dict[str, Any],
    *,
    generated: dict[str, dict[str, dict[str, Any]]],
    replace: bool,
) -> dict[str, Any]:
    return merged


def override_retrieval_timeout(client: Any, *, timeout_seconds: float | None) -> Any:
    if timeout_seconds is None or not isinstance(client, LightRAGClient):
        return client
    config = client.config
    return LightRAGClient(
        LightRAGConfig(
            base_url=config.base_url,
            api_key=config.api_key,
            timeout_seconds=timeout_seconds,
        )
    )


def context_with_retrieval_timeout(context: Any, *, timeout_seconds: float | None) -> Any:
    updated_client = override_retrieval_timeout(context.retrieval_client, timeout_seconds=timeout_seconds)
    if updated_client is context.retrieval_client:
        return context
    return replace(context, retrieval_client=updated_client)


def sync_cache_to_postgres(cache: dict[str, Any], database_url: str) -> None:
    import psycopg

    rows = entity_trace_cache_rows(cache)
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            _upsert_entity_trace_cache(cur, rows)
        conn.commit()


def read_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def write_cache(path: Path, cache: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build page-ready entity trace cache for selected chapters.")
    parser.add_argument("--chapters", default="1-3", help="Chapter selection, e.g. 1-3 or 1,2,3.")
    parser.add_argument("--manifest", type=Path, default=Path("book/chapters_manifest.json"))
    parser.add_argument("--data-dir", type=Path, default=Path("data/app"))
    parser.add_argument("--static-dir", type=Path, default=Path("static"))
    parser.add_argument("--output", type=Path, default=Path("data/app/entity_trace_cache.json"))
    parser.add_argument("--postgres", action="store_true", help="Read chapter cards from PostgreSQL.")
    parser.add_argument("--sync-postgres", action="store_true", help="Upsert generated cache rows into PostgreSQL.")
    parser.add_argument("--replace", action="store_true", help="Replace the output file instead of merging selected chapters.")
    parser.add_argument("--skip-existing", action="store_true", help="Skip chapters already present with non-empty cache in output file.")
    parser.add_argument("--flush-each-chapter", action="store_true", help="Write output file and sync PostgreSQL after each chapter.")
    parser.add_argument("--live-retrieval", action="store_true", help="Allow live LightRAG fallback while building the cache.")
    parser.add_argument("--include-generated", action="store_true", default=True, help=argparse.SUPPRESS)
    parser.add_argument("--no-generated", action="store_false", dest="include_generated", help="Do not scan generated chapter cards.")
    parser.add_argument("--lightrag-timeout", type=float, default=None, help="Override LightRAG request timeout in seconds.")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    try:
        chapters = parse_chapter_selection(args.chapters)
        context = create_app_context(
            manifest_path=args.manifest,
            data_dir=args.data_dir,
            static_dir=args.static_dir,
            use_env_retrieval=args.live_retrieval,
            use_env_content_store=args.postgres,
            use_postgres_store=args.postgres,
        )
        if args.live_retrieval and context.retrieval_client is None:
            raise RuntimeError("LIGHTRAG_BASE_URL is not set; cannot build entity trace cache")
        context = context_with_retrieval_timeout(context, timeout_seconds=args.lightrag_timeout)

        existing = initial_cache(read_cache(args.output), replace=args.replace)
        build_chapters = chapters_to_build(chapters, existing, skip_existing=args.skip_existing)
        database_url = None
        if args.sync_postgres:
            database_url = load_database_url(load_dotenv()) or load_database_url()
            if database_url is None:
                raise RuntimeError("DATABASE_URL is not set for PostgreSQL sync")

        generated: dict[str, dict[str, dict[str, Any]]] = {}
        for index, chapter in enumerate(build_chapters, start=1):
            print(f"[{index}/{len(build_chapters)}] building chapter {chapter:03d}...", flush=True)
            chapter_payload = build_entity_trace_cache_for_context(
                context=context,
                chapters=[chapter],
                include_generated=args.include_generated,
                use_live_retrieval=args.live_retrieval,
            )
            chapter_cache = chapter_payload.get(str(chapter), {})
            generated[str(chapter)] = chapter_cache
            existing = merge_chapter_cache(existing, chapter, chapter_cache)
            if args.flush_each_chapter:
                write_cache(args.output, existing)
                if database_url:
                    sync_cache_to_postgres({str(chapter): chapter_cache}, database_url)
            print(f"[{index}/{len(build_chapters)}] chapter {chapter:03d}: {len(chapter_cache)} entities", flush=True)

        if not args.flush_each_chapter:
            write_cache(args.output, final_cache(existing, generated=generated, replace=args.replace))
            if database_url:
                sync_cache_to_postgres(generated, database_url)
    except Exception as exc:  # noqa: BLE001 - CLI reports actionable failures.
        print(f"error: {exc}", file=sys.stderr)
        return 1

    total_entities = sum(len(items) for items in generated.values())
    print(f"Entity trace cache built: {len(generated)} chapters, {total_entities} entities")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

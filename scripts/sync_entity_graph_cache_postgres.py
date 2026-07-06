from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hlm_kg.postgres_config import load_database_url, load_dotenv
from scripts.import_postgres_seed import _upsert_entity_graph_cache


Progress = Callable[[str], None]


def read_graph_cache(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def graph_cache_rows_for_sync(
    cache: Mapping[str, Any],
    *,
    include_raw_graph: bool = False,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entity_name, payload in cache.items():
        clean_name = str(entity_name or "").strip()
        if not clean_name or not isinstance(payload, Mapping):
            continue
        metadata = dict(payload.get("metadata") or {})
        raw_graph = {}
        if include_raw_graph:
            raw_value = payload.get("raw_graph")
            raw_graph = dict(raw_value) if isinstance(raw_value, Mapping) else {}
        else:
            metadata["raw_graph_omitted"] = True
        rows.append(
            {
                "entity_name": clean_name,
                "description": str(payload.get("description") or ""),
                "neighbors": _list_or_empty(payload.get("neighbors")),
                "extended_neighbors": _list_or_empty(payload.get("extended_neighbors")),
                "raw_graph": raw_graph,
                "metadata": metadata,
            }
        )
    return rows


def sync_rows_to_postgres(
    rows: Sequence[dict[str, Any]],
    database_url: str,
    *,
    batch_size: int = 50,
    delete_existing: bool = False,
    prune_missing: bool = False,
    connect: Callable[[str], Any] | None = None,
    progress: Progress = print,
) -> None:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    if prune_missing and not rows:
        raise ValueError("refusing to prune entity_graph_cache with an empty input")

    if connect is None:
        import psycopg

        connect = psycopg.connect

    names = [str(row["entity_name"]) for row in rows]
    total = len(rows)
    total_batches = _batch_count(total, batch_size)
    with connect(database_url) as conn:
        if delete_existing:
            _delete_existing_rows(conn, names, batch_size=batch_size, progress=progress)
        for index, batch in enumerate(iter_batches(list(rows), batch_size), start=1):
            start = ((index - 1) * batch_size) + 1
            end = start + len(batch) - 1
            with conn.cursor() as cur:
                _upsert_entity_graph_cache(cur, list(batch))
            conn.commit()
            progress(f"[{index}/{total_batches}] synced entity_graph_cache rows {start}-{end} of {total}")
        if prune_missing:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM entity_graph_cache WHERE NOT (entity_name = ANY(%s))", (names,))
            conn.commit()
            progress(f"[prune] deleted entity_graph_cache rows not present in input ({len(names)} kept)")


def iter_batches[T](items: Sequence[T], batch_size: int) -> Iterator[list[T]]:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    for start in range(0, len(items), batch_size):
        yield list(items[start : start + batch_size])


def _delete_existing_rows(conn: Any, names: Sequence[str], *, batch_size: int, progress: Progress) -> None:
    total = len(names)
    total_batches = _batch_count(total, batch_size)
    for index, batch in enumerate(iter_batches(list(names), batch_size), start=1):
        start = ((index - 1) * batch_size) + 1
        end = start + len(batch) - 1
        with conn.cursor() as cur:
            cur.execute("DELETE FROM entity_graph_cache WHERE entity_name = ANY(%s)", (batch,))
        conn.commit()
        progress(f"[delete {index}/{total_batches}] deleted existing entity_graph_cache rows {start}-{end} of {total}")


def _batch_count(total: int, batch_size: int) -> int:
    return (total + batch_size - 1) // batch_size if total else 0


def _list_or_empty(value: object) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync cached entity graph JSON into PostgreSQL in visible batches.")
    parser.add_argument("--input", type=Path, default=Path("data/app/entity_graph_cache.json"))
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--include-raw-graph", action="store_true", help="Also write raw_graph JSONB into PostgreSQL.")
    parser.add_argument(
        "--delete-existing",
        action="store_true",
        help="Delete rows for input entity names before upserting them.",
    )
    parser.add_argument(
        "--prune-missing",
        action="store_true",
        help="After a successful sync, delete entity_graph_cache rows whose names are absent from the input JSON.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Load and count rows without writing PostgreSQL.")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    try:
        cache = read_graph_cache(args.input)
        rows = graph_cache_rows_for_sync(cache, include_raw_graph=args.include_raw_graph)
        print(
            f"Loaded {len(rows)} entity_graph_cache rows from {args.input}; "
            f"raw_graph={'included' if args.include_raw_graph else 'omitted'}",
            flush=True,
        )
        if args.dry_run:
            print("Dry run complete; PostgreSQL was not modified.", flush=True)
            return 0
        database_url = load_database_url(load_dotenv()) or load_database_url()
        if database_url is None:
            raise RuntimeError("DATABASE_URL is not set for PostgreSQL sync")
        sync_rows_to_postgres(
            rows,
            database_url,
            batch_size=args.batch_size,
            delete_existing=args.delete_existing,
            prune_missing=args.prune_missing,
        )
    except Exception as exc:  # noqa: BLE001 - CLI reports actionable failures.
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Entity graph cache PostgreSQL sync complete: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

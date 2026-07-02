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

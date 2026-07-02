from __future__ import annotations

import os
from collections.abc import Mapping


def load_database_url(env: Mapping[str, str] | None = None) -> str | None:
    source = os.environ if env is None else env
    value = source.get("DATABASE_URL")
    if value is None or not value.strip():
        return None
    return value.strip()


def parse_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path


def load_database_url(env: Mapping[str, str] | None = None) -> str | None:
    source = os.environ if env is None else env
    value = source.get("DATABASE_URL")
    if value is None or not value.strip():
        return None
    return value.strip()


def load_dotenv(path: Path = Path(".env")) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        values[key] = value
    return values


def parse_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

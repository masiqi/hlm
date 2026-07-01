from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_validation_samples(path: Path) -> list[dict[str, Any]]:
    samples = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(samples, list):
        raise ValueError("validation samples must be a list")
    return samples


def sample_categories(samples: list[dict[str, Any]]) -> set[str]:
    return {str(sample["category"]) for sample in samples}

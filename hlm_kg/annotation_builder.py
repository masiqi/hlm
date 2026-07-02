from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


def generated_annotation_rows(
    chapter_number: int,
    original_text: str,
    review_annotations: list[Any],
    *,
    target_lookup: Mapping[str, str] | None = None,
    keep_unresolved_target: bool = True,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for annotation in review_annotations:
        if not isinstance(annotation, Mapping):
            continue
        surface_text = str(annotation.get("text") or "").strip()
        target = str(annotation.get("target") or "").strip()
        if not surface_text or not target:
            continue
        entity_id = _resolve_target(target, target_lookup, keep_unresolved_target=keep_unresolved_target)
        annotation_type = str(annotation.get("kind") or "entity").strip() or "entity"
        metadata = {"source": "chapter_card.annotations"}
        note = str(annotation.get("note") or "").strip()
        if note:
            metadata["note"] = note

        start = 0
        while True:
            index = original_text.find(surface_text, start)
            if index == -1:
                break
            rows.append(
                {
                    "id": f"ann-{chapter_number:03d}-generated-{_stable_id_part(target)}-{index}",
                    "chapter_number": chapter_number,
                    "start_offset": index,
                    "end_offset": index + len(surface_text),
                    "surface_text": surface_text,
                    "annotation_type": annotation_type,
                    "entity_id": entity_id,
                    "relation_id": None,
                    "evidence_id": None,
                    "display_priority": 80,
                    "metadata": metadata,
                }
            )
            start = index + len(surface_text)
    unique = {row["id"]: row for row in rows}
    return sorted(unique.values(), key=lambda row: (row["start_offset"], row["end_offset"], row["id"]))


def _resolve_target(target: str, target_lookup: Mapping[str, str] | None, *, keep_unresolved_target: bool) -> str | None:
    if target_lookup is None:
        return target
    resolved = target_lookup.get(target)
    if resolved is not None:
        return resolved
    return target if keep_unresolved_target else None


def _stable_id_part(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z_-]+", "-", value).strip("-") or "target"

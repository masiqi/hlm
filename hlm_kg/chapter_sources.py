from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePath


_CHAPTER_FILE_RE = re.compile(r"^(?P<padded>\d{3})-(?P<label>.+?回)-(?P<title>.+)\.txt$")
_SOURCE_SEPARATOR = "<SEP>"


@dataclass(frozen=True)
class ChapterSource:
    chapter_number: int
    chapter_label: str
    chapter_title: str
    source_file: str


def parse_chapter_source(file_path: str) -> ChapterSource | None:
    source_file = PurePath(file_path).name
    match = _CHAPTER_FILE_RE.match(source_file)
    if match is None:
        return None
    chapter_number = int(match.group("padded"))
    if chapter_number < 1 or chapter_number > 120:
        return None
    return ChapterSource(
        chapter_number=chapter_number,
        chapter_label=match.group("label"),
        chapter_title=match.group("title"),
        source_file=source_file,
    )


def parse_chapter_sources(value: str | None) -> list[ChapterSource]:
    if not value:
        return []

    sources: list[ChapterSource] = []
    seen: set[str] = set()
    for raw_part in value.split(_SOURCE_SEPARATOR):
        part = raw_part.strip()
        if not part:
            continue
        source = parse_chapter_source(part)
        if source is None or source.source_file in seen:
            continue
        seen.add(source.source_file)
        sources.append(source)
    return sources

from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CHAPTER_HEADING_RE = re.compile(
    r"(?m)^第([0-9０-９一二三四五六七八九十百零〇两]+)(?:章|回)[ \t　]*(.+?)\s*$"
)

CN_DIGITS = "零一二三四五六七八九"
INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\r\n]+')


@dataclass(frozen=True)
class HeadingMatch:
    number: int
    source_heading: str
    title: str
    char_start: int
    char_end: int
    line_start: int


def parse_chapter_number(raw: str) -> int:
    raw = raw.strip().translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    if raw.isdigit():
        return int(raw)

    raw = raw.replace("〇", "零").replace("两", "二")
    if raw == "十":
        return 10
    if "百" in raw:
        left, right = raw.split("百", 1)
        hundreds = CN_DIGITS.index(left) if left else 1
        return hundreds * 100 + _parse_under_100(right)
    return _parse_under_100(raw)


def _parse_under_100(raw: str) -> int:
    if not raw:
        return 0
    if "十" in raw:
        left, right = raw.split("十", 1)
        tens = CN_DIGITS.index(left) if left else 1
        ones = CN_DIGITS.index(right) if right else 0
        return tens * 10 + ones
    return CN_DIGITS.index(raw)


def chinese_chapter_number(number: int) -> str:
    if not 1 <= number <= 120:
        raise ValueError(f"chapter number out of range: {number}")
    if number < 10:
        return CN_DIGITS[number]
    if number < 20:
        return "十" + (CN_DIGITS[number % 10] if number % 10 else "")
    if number < 100:
        tens, ones = divmod(number, 10)
        return CN_DIGITS[tens] + "十" + (CN_DIGITS[ones] if ones else "")
    if number == 100:
        return "一百"
    tail = chinese_chapter_number(number - 100)
    return "一百" + tail


def canonical_heading(number: int, title: str) -> str:
    return f"第{chinese_chapter_number(number)}回 {title}"


def safe_filename(number: int, title: str) -> str:
    safe_title = INVALID_FILENAME_CHARS.sub("-", title).strip(" .-")
    return f"{number:03d}-第{chinese_chapter_number(number)}回-{safe_title}.txt"


def detect_headings(text: str) -> list[HeadingMatch]:
    matches: list[HeadingMatch] = []
    line_starts = _line_start_offsets(text)
    for match in CHAPTER_HEADING_RE.finditer(text):
        number = parse_chapter_number(match.group(1))
        matches.append(
            HeadingMatch(
                number=number,
                source_heading=match.group(0).strip(),
                title=match.group(2).strip(),
                char_start=match.start(),
                char_end=match.end(),
                line_start=_line_number_for_offset(line_starts, match.start()),
            )
        )
    return matches


def split_chapters(
    source_path: Path,
    output_dir: Path,
    manifest_path: Path,
    *,
    expected_count: int = 120,
) -> dict[str, Any]:
    source_path = Path(source_path)
    output_dir = Path(output_dir)
    manifest_path = Path(manifest_path)
    text = source_path.read_text(encoding="utf-8")
    headings = detect_headings(text)
    _validate_headings(headings, expected_count)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    line_starts = _line_start_offsets(text)
    chapters = []
    for index, heading in enumerate(headings):
        next_start = headings[index + 1].char_start if index + 1 < len(headings) else len(text)
        chapter_text = text[heading.char_start:next_start].strip() + "\n"
        chapter_path = output_dir / safe_filename(heading.number, heading.title)
        chapter_path.write_text(chapter_text, encoding="utf-8")
        chapters.append(
            {
                "number": heading.number,
                "source_heading": heading.source_heading,
                "canonical_heading": canonical_heading(heading.number, heading.title),
                "title": heading.title,
                "file_path": str(chapter_path),
                "char_start": heading.char_start,
                "char_end": next_start,
                "line_start": heading.line_start,
                "line_end": _line_number_for_offset(line_starts, max(heading.char_start, next_start - 1)),
                "char_count": len(text[heading.char_start:next_start]),
            }
        )

    manifest: dict[str, Any] = {
        "source_file": str(source_path),
        "chapter_count": len(chapters),
        "chapter_heading_pattern": CHAPTER_HEADING_RE.pattern,
        "chapters_dir": str(output_dir),
        "frontmatter": _write_extra_text(
            text[: headings[0].char_start],
            output_dir,
            "frontmatter",
            0,
            headings[0].char_start,
            line_starts,
        ),
        "backmatter": _write_extra_text(
            text[headings[-1].char_start + chapters[-1]["char_count"] :],
            output_dir,
            "backmatter",
            headings[-1].char_start + chapters[-1]["char_count"],
            len(text),
            line_starts,
        ),
        "chapters": chapters,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def _validate_headings(headings: list[HeadingMatch], expected_count: int) -> None:
    numbers = [heading.number for heading in headings]
    if len(headings) != expected_count:
        samples = [heading.source_heading for heading in headings[:5]]
        tail_samples = [heading.source_heading for heading in headings[-5:]]
        raise ValueError(
            f"expected 120 chapters, detected {len(headings)}. "
            f"first headings={samples}; last headings={tail_samples}"
        )
    expected_numbers = list(range(1, expected_count + 1))
    if numbers != expected_numbers:
        raise ValueError(
            f"chapter numbers are not contiguous 1..{expected_count}: "
            f"detected first={numbers[:10]}, last={numbers[-10:]}"
        )


def _write_extra_text(
    extra_text: str,
    output_dir: Path,
    name: str,
    char_start: int,
    char_end: int,
    line_starts: list[int],
) -> dict[str, Any] | None:
    if not extra_text.strip():
        return None
    path = output_dir / f"{name}.txt"
    path.write_text(extra_text, encoding="utf-8")
    return {
        "name": name,
        "file_path": str(path),
        "char_start": char_start,
        "char_end": char_end,
        "line_start": _line_number_for_offset(line_starts, char_start),
        "line_end": _line_number_for_offset(line_starts, max(char_start, char_end - 1)),
        "char_count": len(extra_text),
    }


def _line_start_offsets(text: str) -> list[int]:
    offsets = [0]
    for match in re.finditer(r"\n", text):
        offsets.append(match.end())
    return offsets


def _line_number_for_offset(line_starts: list[int], offset: int) -> int:
    lo = 0
    hi = len(line_starts)
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if line_starts[mid] <= offset:
            lo = mid
        else:
            hi = mid
    return lo + 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Split Hongloumeng into chapter files.")
    parser.add_argument("--source", type=Path, default=Path("book/红楼梦.txt"))
    parser.add_argument("--output-dir", type=Path, default=Path("book/chapters"))
    parser.add_argument("--manifest", type=Path, default=Path("book/chapters_manifest.json"))
    args = parser.parse_args()

    manifest = split_chapters(args.source, args.output_dir, args.manifest)
    print(
        f"Split {manifest['source_file']} into {manifest['chapter_count']} chapters "
        f"under {manifest['chapters_dir']}; manifest: {args.manifest}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

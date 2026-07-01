from pathlib import Path

from hlm_kg.chapters import split_chapters


def test_split_chapters_detects_120_contiguous_chapters(tmp_path):
    source = Path("book/红楼梦.txt")
    output_dir = tmp_path / "chapters"
    manifest_path = tmp_path / "chapters_manifest.json"

    manifest = split_chapters(source, output_dir, manifest_path)

    assert manifest["source_file"] == str(source)
    assert manifest["chapter_count"] == 120
    assert manifest["frontmatter"] is None
    assert manifest["backmatter"] is None

    chapters = manifest["chapters"]
    assert [chapter["number"] for chapter in chapters] == list(range(1, 121))
    assert chapters[0]["source_heading"].startswith("第1章 ")
    assert chapters[0]["canonical_heading"].startswith("第一回 ")
    assert chapters[-1]["source_heading"].startswith("第120章 ")
    assert chapters[-1]["canonical_heading"].startswith("第一百二十回 ")

    for chapter in chapters:
        path = Path(chapter["file_path"])
        assert path.exists()
        assert path.read_text(encoding="utf-8").startswith(chapter["source_heading"])
        assert chapter["char_count"] > 0
        assert chapter["char_start"] < chapter["char_end"]
        assert chapter["line_start"] <= chapter["line_end"]


def test_split_chapters_refuses_non_120_sources(tmp_path):
    source = tmp_path / "short.txt"
    source.write_text(
        "序言\n第1章 第一章标题\n正文\n第2章 第二章标题\n正文\n",
        encoding="utf-8",
    )

    try:
        split_chapters(source, tmp_path / "chapters", tmp_path / "manifest.json")
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("split_chapters should refuse non-120 input")

    assert "expected 120 chapters" in message
    assert "detected 2" in message

import json
from pathlib import Path

from hlm_kg.web_app import create_app_context
from scripts.build_static_chapter_cache import build_static_chapter_cache, cache_path_for_chapter


def _write_minimal_app_context_files(tmp_path: Path, review_cards: list[dict]) -> tuple[Path, Path, Path]:
    chapter_path = tmp_path / "book" / "chapters" / "001-第一回.txt"
    chapter_path.parent.mkdir(parents=True)
    chapter_path.write_text("第一回 原文", encoding="utf-8")
    manifest_path = tmp_path / "book" / "chapters_manifest.json"
    manifest_path.write_text(
        json.dumps({"chapters": [{"number": 1, "title": "第一回", "file_path": str(chapter_path)}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    data_dir = tmp_path / "data"
    static_dir = tmp_path / "static"
    data_dir.mkdir()
    static_dir.mkdir()
    (data_dir / "chapter_review_cards.json").write_text(json.dumps(review_cards, ensure_ascii=False), encoding="utf-8")
    for filename in ("knowledge_cards.json", "graph_relations.json", "topics.json", "common_entries.json", "evidence.json"):
        (data_dir / filename).write_text("[]", encoding="utf-8")
    return manifest_path, data_dir, static_dir


def _review_card(**overrides):
    card = {
        "id": "review-001",
        "chapter": 1,
        "source": {"prompt_name": "test", "prompt_version": "v1"},
        "plain_summary": "第一回梗概。",
        "plot_chain": ["甄士隐梦幻识通灵"],
        "key_events": [],
        "key_characters": [],
        "current_chapter_foreshadowing_signals": [],
        "later_association_relation_ids": [],
        "quotable_fact_ids": [],
        "retrieval_tags": [],
        "understanding_focus": [],
        "characters": [],
        "relationships": [],
        "places": [],
        "objects": [],
        "literary_texts": [],
        "modern_explanations": [],
        "later_associations": [],
        "annotations": [],
    }
    card.update(overrides)
    return card


def test_cache_path_for_chapter_uses_static_chapter_cache_directory():
    assert cache_path_for_chapter(Path("static/chapter_cache"), 7) == Path("static/chapter_cache/007.json")


def test_build_static_chapter_cache_writes_api_equivalent_chapter_payloads(tmp_path, capsys):
    review_card = _review_card(characters=[{"name": "袭人", "actions": ["劝慰宝玉"]}])
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [review_card])
    output_dir = static_dir / "chapter_cache"
    context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)

    written = build_static_chapter_cache(context=context, chapters=[1], output_dir=output_dir)

    assert written == [output_dir / "001.json"]
    payload = json.loads((output_dir / "001.json").read_text(encoding="utf-8"))
    assert payload["chapter"]["number"] == 1
    assert payload["reviewCard"]["plainSummary"] == "第一回梗概。"
    assert payload["inlineEntities"][0]["name"] == "袭人"
    assert payload["materialStatus"]["hasReviewCard"] is True
    assert "[1/1] wrote static chapter cache: 001.json" in capsys.readouterr().out

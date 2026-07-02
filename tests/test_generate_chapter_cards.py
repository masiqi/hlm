from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_chapter_cards.py"


def _import_script_module():
    assert SCRIPT_PATH.exists(), f"{SCRIPT_PATH} does not exist"
    spec = importlib.util.spec_from_file_location("generate_chapter_cards", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_manifest(tmp_path: Path) -> Path:
    chapter_path = tmp_path / "book" / "chapters" / "001-第一回-甄士隐梦幻识通灵 贾雨村风尘怀闺秀.txt"
    chapter_path.parent.mkdir(parents=True)
    chapter_path.write_text("第一回 甄士隐梦幻识通灵 贾雨村风尘怀闺秀\n原文内容", encoding="utf-8")
    manifest_path = tmp_path / "book" / "chapters_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "chapter_count": 1,
                "chapters": [
                    {
                        "number": 1,
                        "title": "甄士隐梦幻识通灵 贾雨村风尘怀闺秀",
                        "canonical_heading": "第一回 甄士隐梦幻识通灵 贾雨村风尘怀闺秀",
                        "file_path": str(chapter_path),
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return manifest_path


class FakeLightRAGClient:
    def __init__(self):
        self.queries = []

    def query_data(self, query: str, mode: str = "hybrid", **options):
        self.queries.append((query, mode, options))
        return {
            "status": "success",
            "data": {
                "entities": [{"entity_name": "甄士隐", "description": "甄士隐出现在第一回。"}],
                "relationships": [],
                "chunks": [{"content": "第一回甄士隐梦幻识通灵。"}],
                "references": [],
            },
            "metadata": {"query_mode": mode},
        }


class FakeLLMClient:
    def __init__(self):
        self.prompts = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return """
第一部分：
# 第一回 甄士隐梦幻识通灵 贾雨村风尘怀闺秀 章节复习卡

## 1. 本回一句话概括
本回主要写甄士隐梦幻识通灵与贾雨村出场。

第二部分：AppImportJSON
```json
{
  "id": "review-001",
  "chapter": 1,
  "source": {
    "prompt_name": "hongloumeng_chapter_review_card",
    "prompt_version": "2026-07-01",
    "generated_at": "2026-07-02"
  },
  "plain_summary": "第一回主要写甄士隐梦中见通灵宝玉来历，贾雨村也在本回出场，为全书真假有无和人物命运开端奠定基础。",
  "plot_chain": ["甄士隐梦中见通灵宝玉来历。", "贾雨村出场并寄居甄家。"],
  "key_events": ["甄士隐梦幻识通灵", "贾雨村出场"],
  "key_characters": [],
  "current_chapter_foreshadowing_signals": ["通灵宝玉来历提示全书真假有无的叙事框架。"],
  "later_association_relation_ids": [],
  "quotable_fact_ids": [],
  "retrieval_tags": ["#红楼梦", "#第一回", "#甄士隐", "#贾雨村"],
  "understanding_focus": ["抓住真假有无的开篇结构。"]
}
```
"""


def test_parse_chapter_selection_supports_list_and_all():
    module = _import_script_module()

    assert module.parse_chapter_selection("3,5,8", all_chapters=False) == [3, 5, 8]
    assert module.parse_chapter_selection("", all_chapters=True) == list(range(1, 121))


def test_generate_selected_chapter_writes_markdown_json_and_combined_json(tmp_path):
    module = _import_script_module()
    manifest_path = _write_manifest(tmp_path)
    output_dir = tmp_path / "generated"
    lightrag = FakeLightRAGClient()
    llm = FakeLLMClient()

    cards = module.generate_cards(
        manifest_path=manifest_path,
        output_dir=output_dir,
        chapters=[1],
        lightrag_client=lightrag,
        llm_client=llm,
        generated_at="2026-07-02",
        overwrite=True,
    )

    assert len(cards) == 1
    assert cards[0]["chapter"] == 1
    assert (output_dir / "chapter_cards_markdown" / "001.md").exists()
    assert json.loads((output_dir / "chapter_cards_import" / "001.json").read_text(encoding="utf-8"))["id"] == "review-001"
    combined = json.loads((output_dir / "chapter_review_cards.raw.json").read_text(encoding="utf-8"))
    assert [card["chapter"] for card in combined] == [1]
    assert lightrag.queries
    assert "LightRAG 全书关系线索" in llm.prompts[0]


def test_extract_app_import_json_rejects_missing_json_block():
    module = _import_script_module()

    try:
        module.extract_app_import_json("没有 JSON")
    except ValueError as exc:
        assert "AppImportJSON" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_makefile_documents_chapter_card_generation_command():
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert "generate-chapter-cards:" in makefile
    assert "python scripts/generate_chapter_cards.py" in makefile

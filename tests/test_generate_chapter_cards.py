from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
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
        return """# 第一回 甄士隐梦幻识通灵 贾雨村风尘怀闺秀 章节复习卡

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
  "understanding_focus": ["抓住真假有无的开篇结构。"],
  "characters": [],
  "relationships": [],
  "places": [],
  "objects": [],
  "literary_texts": [],
  "modern_explanations": [],
  "later_associations": [],
  "annotations": []
}
```
"""


class RetryLLMClient:
    def __init__(self):
        self.prompts = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if len(self.prompts) == 1:
            return "# 第一回 甄士隐梦幻识通灵 贾雨村风尘怀闺秀 章节复习卡\n\n## 1. 本回一句话概括\n本回主要写甄士隐梦幻识通灵。"
        return FakeLLMClient().complete(prompt)


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
    assert "系统提供的全书关系线索" in llm.prompts[0]


def test_generate_cards_combines_existing_import_json_files(tmp_path):
    module = _import_script_module()
    manifest_path = _write_manifest(tmp_path)
    output_dir = tmp_path / "generated"
    import_dir = output_dir / "chapter_cards_import"
    import_dir.mkdir(parents=True)
    (import_dir / "002.json").write_text(
        json.dumps(
            {
                "id": "review-002",
                "chapter": 2,
                "source": {"prompt_name": "hongloumeng_chapter_review_card", "prompt_version": "2026-07-01", "generated_at": "2026-07-02"},
                "plain_summary": "第二回已有内容。",
                "plot_chain": ["已有情节"],
                "key_events": ["已有事件"],
                "key_characters": [],
                "current_chapter_foreshadowing_signals": ["已有伏笔"],
                "later_association_relation_ids": [],
                "quotable_fact_ids": [],
                "retrieval_tags": ["#第二回"],
                "understanding_focus": ["已有重点"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    module.generate_cards(
        manifest_path=manifest_path,
        output_dir=output_dir,
        chapters=[1],
        lightrag_client=FakeLightRAGClient(),
        llm_client=FakeLLMClient(),
        generated_at="2026-07-02",
        overwrite=True,
    )

    combined = json.loads((output_dir / "chapter_review_cards.raw.json").read_text(encoding="utf-8"))
    assert [card["chapter"] for card in combined] == [1, 2]


def test_generate_cards_retries_when_app_import_json_is_missing(tmp_path):
    module = _import_script_module()
    manifest_path = _write_manifest(tmp_path)
    llm = RetryLLMClient()

    cards = module.generate_cards(
        manifest_path=manifest_path,
        output_dir=tmp_path / "generated",
        chapters=[1],
        lightrag_client=FakeLightRAGClient(),
        llm_client=llm,
        generated_at="2026-07-02",
        overwrite=True,
    )

    assert [card["chapter"] for card in cards] == [1]
    assert len(llm.prompts) == 2
    assert "只输出 AppImportJSON" in llm.prompts[1]


def test_extract_app_import_json_rejects_missing_json_block():
    module = _import_script_module()

    try:
        module.extract_app_import_json("没有 JSON")
    except ValueError as exc:
        assert "AppImportJSON" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_validate_generated_card_output_rejects_technical_terms_and_greeting():
    module = _import_script_module()
    card = {
        "id": "review-005",
        "chapter": 5,
        "source": {"prompt_name": "hongloumeng_chapter_review_card", "prompt_version": "2026-07-01", "generated_at": "2026-07-02"},
        "plain_summary": "根据LightRAG线索可知本回内容。",
        "plot_chain": ["宝玉入梦"],
        "key_events": ["太虚幻境"],
        "key_characters": [],
        "current_chapter_foreshadowing_signals": [],
        "later_association_relation_ids": [],
        "quotable_fact_ids": [],
        "retrieval_tags": ["#第五回"],
        "understanding_focus": ["理解太虚幻境"],
    }

    errors = module.validate_generated_card_output("好的，同学\n# 第5回 标题 章节复习卡", card)

    assert any("不得以寒暄开头" in error for error in errors)
    assert any("禁用词" in error and "LightRAG" in error for error in errors)


def test_validate_generated_card_output_accepts_clean_extended_card():
    module = _import_script_module()
    card = {
        "id": "review-027",
        "chapter": 27,
        "source": {"prompt_name": "hongloumeng_chapter_review_card", "prompt_version": "2026-07-01", "generated_at": "2026-07-02"},
        "plain_summary": "本回主要写宝钗扑蝶和黛玉葬花。",
        "plot_chain": ["宝钗扑蝶", "黛玉葬花"],
        "key_events": ["宝钗扑蝶", "黛玉葬花"],
        "key_characters": [],
        "current_chapter_foreshadowing_signals": ["葬花情节提示黛玉身世悲感。"],
        "later_association_relation_ids": [],
        "quotable_fact_ids": [],
        "retrieval_tags": ["#第二十七回"],
        "understanding_focus": ["抓住宝钗与黛玉的对照。"],
        "characters": [],
        "relationships": [],
        "places": [],
        "objects": [],
        "literary_texts": [],
        "modern_explanations": [],
        "later_associations": [],
        "annotations": [],
    }

    assert module.validate_generated_card_output("# 第27回 标题 章节复习卡\n正文", card) == []


def test_validate_generated_card_output_rejects_missing_extended_fields_and_bad_required_values():
    module = _import_script_module()
    card = {
        "id": "review-027",
        "chapter": 27,
        "source": {"prompt_name": "hongloumeng_chapter_review_card", "prompt_version": "2026-07-01", "generated_at": "2026-07-02"},
        "plain_summary": "",
        "plot_chain": "不是数组",
        "key_events": ["宝钗扑蝶"],
        "key_characters": [],
        "current_chapter_foreshadowing_signals": [],
        "later_association_relation_ids": [],
        "quotable_fact_ids": [],
        "retrieval_tags": ["#第二十七回"],
        "understanding_focus": ["抓住宝钗与黛玉的对照。"],
    }

    errors = module.validate_generated_card_output("# 第27回 标题 章节复习卡\n正文", card)

    assert any("plain_summary" in error and "不能为空" in error for error in errors)
    assert any("plot_chain" in error and "必须是数组" in error for error in errors)
    assert any("annotations" in error and "缺少必填字段" in error for error in errors)


def test_makefile_documents_chapter_card_generation_command():
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert "generate-chapter-cards:" in makefile
    assert "python scripts/generate_chapter_cards.py" in makefile


def test_build_prompt_uses_student_facing_source_names_and_forbids_technical_terms_in_markdown():
    module = _import_script_module()

    prompt = module.build_prompt(
        chapter_number=5,
        chapter_title="贾宝玉神游太虚境 警幻仙曲演红楼梦",
        source_file="book/chapters/005.txt",
        chapter_text="第五回原文",
        lightrag_evidence={"data": {"relationships": []}},
        generated_at="2026-07-02",
    )

    assert "系统提供的全书关系线索" in prompt
    assert "LightRAG 全书关系线索" not in prompt
    assert "完整 Markdown 章节复习卡和 AppImportJSON 的学生可见文字都不得出现" in prompt
    assert "不要输出寒暄、解释、免责声明或“好的同学”之类开场白" in prompt


def test_build_prompt_requests_structured_app_import_sections_for_website_and_database():
    module = _import_script_module()

    prompt = module.build_prompt(
        chapter_number=27,
        chapter_title="滴翠亭杨妃戏彩蝶 埋香冢飞燕泣残红",
        source_file="book/chapters/027.txt",
        chapter_text="第二十七回原文",
        lightrag_evidence={"data": {"entities": []}},
        generated_at="2026-07-02",
    )

    for field in (
        '"characters"',
        '"relationships"',
        '"places"',
        '"objects"',
        '"literary_texts"',
        '"modern_explanations"',
        '"later_associations"',
        '"annotations"',
    ):
        assert field in prompt


def test_build_prompt_defaults_later_associations_to_empty_array_without_existing_ids():
    module = _import_script_module()

    prompt = module.build_prompt(
        chapter_number=27,
        chapter_title="滴翠亭杨妃戏彩蝶 埋香冢飞燕泣残红",
        source_file="book/chapters/027.txt",
        chapter_text="第二十七回原文",
        lightrag_evidence={"data": {"relationships": []}},
        generated_at="2026-07-02",
    )

    assert '"later_associations": []' in prompt
    assert '"source_chapters": [74]' not in prompt


def test_repair_prompt_uses_same_structured_app_import_sections():
    module = _import_script_module()

    prompt = module.build_repair_prompt(
        chapter_number=27,
        chapter_title="滴翠亭杨妃戏彩蝶 埋香冢飞燕泣残红",
        generated_at="2026-07-02",
        previous_output="# 第27回 标题 章节复习卡",
    )

    for field in (
        '"characters"',
        '"relationships"',
        '"places"',
        '"objects"',
        '"literary_texts"',
        '"modern_explanations"',
        '"later_associations"',
        '"annotations"',
    ):
        assert field in prompt
    assert "系统提供的全书关系线索" in prompt
    assert "LightRAG 全书关系线索" not in prompt


def test_repair_prompt_defaults_later_associations_to_empty_array():
    module = _import_script_module()

    prompt = module.build_repair_prompt(
        chapter_number=27,
        chapter_title="滴翠亭杨妃戏彩蝶 埋香冢飞燕泣残红",
        generated_at="2026-07-02",
        previous_output="# 第27回 标题 章节复习卡",
    )

    assert '"later_associations": []' in prompt
    assert '"后文关联对象"' not in prompt


def test_cli_help_runs_from_repo_root_without_import_error():
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Generate Hongloumeng chapter review cards" in result.stdout

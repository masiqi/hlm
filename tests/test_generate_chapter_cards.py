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


LONG_SUMMARY = (
    "第一回主要写甄士隐在梦中看见通灵宝玉的来历，又写贾雨村寄居甄家、等待进身机会。"
    "梦幻叙事把石头、僧道和真假有无的结构先摆出来，使学生先抓住全书的开端框架。"
    "甄士隐的安稳生活与贾雨村的功名愿望形成对照，既提示人物命运将发生转折，也为后来家族盛衰、人物聚散和真假互映的阅读线索开了头。"
    "本回虽然情节不多，却集中交代石头入世、僧道点化、甄贾对照和功名欲望，适合把它当作全书阅读地图来看："
    "先明白谁在梦中看见什么，再明白这些梦幻内容怎样提示真实人生的悲欢，同时把甄士隐、贾雨村两条线分别看作退隐与进取的命运开端来理解。"
)


def _rich_card_fields():
    return {
        "characters": [
            {
                "name": "甄士隐",
                "aliases": [],
                "role": "乡宦",
                "actions": ["梦中见通灵宝玉来历", "资助贾雨村"],
                "traits": ["有出世意味", "厚道慷慨"],
                "evidence": ["甄士隐梦幻识通灵", "贾雨村寄居甄家"],
                "importance": "引出真假有无结构和人物命运开端",
            }
        ],
        "relationships": [
            {
                "source": "甄士隐",
                "type": "参与",
                "target": "甄士隐梦幻识通灵",
                "description": "甄士隐在梦中见到通灵宝玉来历，本回由此展开真假有无的开篇结构。",
                "chapter_evidence": "本回梦幻情节",
            }
        ],
        "places": [
            {"name": "甄家", "scenes": ["贾雨村寄居"], "function": "安稳日常与后续变故形成对照"}
        ],
        "objects": [
            {"name": "通灵宝玉", "context": "梦中交代来历", "meaning": "引出全书核心物件", "related_entities": ["甄士隐"]}
        ],
        "literary_texts": [
            {"title": "好了歌", "short_quote": "世人都晓神仙好", "explanation": "点出世俗执念", "function": "提示盛衰无常"}
        ],
        "modern_explanations": [
            {"quote": "梦幻识通灵", "modern_text": "在梦中认识通灵宝玉的来历。", "value": "理解开篇结构"}
        ],
        "annotations": [{"text": "甄士隐", "kind": "person", "target": "甄士隐", "note": "本回开篇人物"}],
    }


def _complete_card_with_rich_defaults(**overrides):
    card = {
        "id": "review-001",
        "chapter": 1,
        "source": {"prompt_name": "hongloumeng_chapter_review_card", "prompt_version": "2026-07-01", "generated_at": "2026-07-02"},
        "plain_summary": LONG_SUMMARY,
        "plot_chain": ["甄士隐梦中见通灵宝玉来历。", "贾雨村出场并寄居甄家。"],
        "key_events": ["甄士隐梦幻识通灵", "贾雨村出场"],
        "key_characters": [],
        "current_chapter_foreshadowing_signals": ["通灵宝玉来历提示全书真假有无的叙事框架。"],
        "later_association_relation_ids": [],
        "quotable_fact_ids": [],
        "retrieval_tags": ["#红楼梦", "#第一回", "#甄士隐", "#贾雨村"],
        "understanding_focus": ["抓住真假有无的开篇结构。"],
        "later_associations": [],
    }
    card.update(_rich_card_fields())
    card.update(overrides)
    return card


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
  "plain_summary": "第一回主要写甄士隐在梦中看见通灵宝玉的来历，又写贾雨村寄居甄家、等待进身机会。梦幻叙事把石头、僧道和真假有无的结构先摆出来，使学生先抓住全书的开端框架。甄士隐的安稳生活与贾雨村的功名愿望形成对照，既提示人物命运将发生转折，也为后来家族盛衰、人物聚散和真假互映的阅读线索开了头。本回虽然情节不多，却集中交代石头入世、僧道点化、甄贾对照和功名欲望，适合把它当作全书阅读地图来看：先明白谁在梦中看见什么，再明白这些梦幻内容怎样提示真实人生的悲欢，同时把甄士隐、贾雨村两条线分别看作退隐与进取的命运开端来理解。",
  "plot_chain": ["甄士隐梦中见通灵宝玉来历。", "贾雨村出场并寄居甄家。"],
  "key_events": ["甄士隐梦幻识通灵", "贾雨村出场"],
  "key_characters": [],
  "current_chapter_foreshadowing_signals": ["通灵宝玉来历提示全书真假有无的叙事框架。"],
  "later_association_relation_ids": [],
  "quotable_fact_ids": [],
  "retrieval_tags": ["#红楼梦", "#第一回", "#甄士隐", "#贾雨村"],
  "understanding_focus": ["抓住真假有无的开篇结构。"],
  "characters": [{"name": "甄士隐", "aliases": [], "role": "乡宦", "actions": ["梦中见通灵宝玉来历", "资助贾雨村"], "traits": ["有出世意味", "厚道慷慨"], "evidence": ["甄士隐梦幻识通灵", "贾雨村寄居甄家"], "importance": "引出真假有无结构和人物命运开端"}],
  "relationships": [{"source": "甄士隐", "type": "参与", "target": "甄士隐梦幻识通灵", "description": "甄士隐在梦中见到通灵宝玉来历，本回由此展开真假有无的开篇结构。", "chapter_evidence": "本回梦幻情节"}],
  "places": [{"name": "甄家", "scenes": ["贾雨村寄居"], "function": "安稳日常与后续变故形成对照"}],
  "objects": [{"name": "通灵宝玉", "context": "梦中交代来历", "meaning": "引出全书核心物件", "related_entities": ["甄士隐"]}],
  "literary_texts": [{"title": "好了歌", "short_quote": "世人都晓神仙好", "explanation": "点出世俗执念", "function": "提示盛衰无常"}],
  "modern_explanations": [{"quote": "梦幻识通灵", "modern_text": "在梦中认识通灵宝玉的来历。", "value": "理解开篇结构"}],
  "later_associations": [],
  "annotations": [{"text": "甄士隐", "kind": "person", "target": "甄士隐", "note": "本回开篇人物"}]
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


class EvidenceBackedAssociationLLMClient(FakeLLMClient):
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
  "plain_summary": "第一回主要写甄士隐在梦中看见通灵宝玉的来历，又写贾雨村寄居甄家、等待进身机会。梦幻叙事把石头、僧道和真假有无的结构先摆出来，使学生先抓住全书的开端框架。甄士隐的安稳生活与贾雨村的功名愿望形成对照，既提示人物命运将发生转折，也为后来家族盛衰、人物聚散和真假互映的阅读线索开了头。本回虽然情节不多，却集中交代石头入世、僧道点化、甄贾对照和功名欲望，适合把它当作全书阅读地图来看：先明白谁在梦中看见什么，再明白这些梦幻内容怎样提示真实人生的悲欢，同时把甄士隐、贾雨村两条线分别看作退隐与进取的命运开端来理解。",
  "plot_chain": ["甄士隐梦中见通灵宝玉来历。", "贾雨村出场并寄居甄家。"],
  "key_events": ["甄士隐梦幻识通灵", "贾雨村出场"],
  "key_characters": [],
  "current_chapter_foreshadowing_signals": ["通灵宝玉来历提示全书真假有无的叙事框架。"],
  "later_association_relation_ids": [],
  "quotable_fact_ids": [],
  "retrieval_tags": ["#红楼梦", "#第一回", "#甄士隐", "#贾雨村"],
  "understanding_focus": ["抓住真假有无的开篇结构。"],
  "characters": [{"name": "甄士隐", "aliases": [], "role": "乡宦", "actions": ["梦中见通灵宝玉来历", "资助贾雨村"], "traits": ["有出世意味", "厚道慷慨"], "evidence": ["甄士隐梦幻识通灵", "贾雨村寄居甄家"], "importance": "引出真假有无结构和人物命运开端"}],
  "relationships": [{"source": "甄士隐", "type": "参与", "target": "甄士隐梦幻识通灵", "description": "甄士隐在梦中见到通灵宝玉来历，本回由此展开真假有无的开篇结构。", "chapter_evidence": "本回梦幻情节"}],
  "places": [{"name": "甄家", "scenes": ["贾雨村寄居"], "function": "安稳日常与后续变故形成对照"}],
  "objects": [{"name": "通灵宝玉", "context": "梦中交代来历", "meaning": "引出全书核心物件", "related_entities": ["甄士隐"]}],
  "literary_texts": [{"title": "好了歌", "short_quote": "世人都晓神仙好", "explanation": "点出世俗执念", "function": "提示盛衰无常"}],
  "modern_explanations": [{"quote": "梦幻识通灵", "modern_text": "在梦中认识通灵宝玉的来历。", "value": "理解开篇结构"}],
  "later_associations": [
    {
      "topic": "甄士隐命运照应",
      "description": "甄士隐后续经历与本回梦幻结构互相照应。",
      "source_chapters": [2],
      "source_ids": ["rel-001-002"],
      "evidence": "关系线索显示甄士隐与第二回经历存在照应。"
    }
  ],
  "annotations": [{"text": "甄士隐", "kind": "person", "target": "甄士隐", "note": "本回开篇人物"}]
}
```
"""


class RelationshipEvidenceLightRAGClient:
    def __init__(self, *, with_later_relationship: bool):
        self.with_later_relationship = with_later_relationship
        self.queries = []

    def query_data(self, query: str, mode: str = "hybrid", **options):
        self.queries.append((query, mode, options))
        relationships = []
        if self.with_later_relationship:
            relationships.append(
                {
                    "src_id": "甄士隐梦幻识通灵",
                    "tgt_id": "甄士隐第二回经历",
                    "keywords": "后文关联",
                    "description": "甄士隐后续经历与第一回梦幻结构互相照应。",
                    "source_id": "rel-001-002",
                    "file_path": "002-第二回-贾夫人仙逝扬州城 冷子兴演说荣国府.txt",
                    "raw_only_marker": "must not leak into prompt",
                }
            )
        return {
            "status": "success",
            "data": {
                "entities": [
                    {
                        "entity_name": "甄士隐梦幻识通灵",
                        "entity_type": "event",
                        "description": "甄士隐梦中见通灵宝玉来历。",
                        "source_id": "ev-001",
                        "file_path": "001-第一回-甄士隐梦幻识通灵 贾雨村风尘怀闺秀.txt",
                        "raw_only_marker": "must not leak into prompt",
                    }
                ],
                "relationships": relationships,
                "chunks": [],
                "references": [],
            },
            "metadata": {"query_mode": mode, "raw_only_marker": "must not leak into prompt"},
        }


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


def test_generate_cards_normalizes_query_data_before_prompt_construction(tmp_path):
    module = _import_script_module()
    manifest_path = _write_manifest(tmp_path)
    output_dir = tmp_path / "generated"
    llm = FakeLLMClient()

    module.generate_cards(
        manifest_path=manifest_path,
        output_dir=output_dir,
        chapters=[1],
        lightrag_client=RelationshipEvidenceLightRAGClient(with_later_relationship=True),
        llm_client=llm,
        generated_at="2026-07-02",
        overwrite=True,
    )

    prompt = llm.prompts[0]
    assert "系统提供的全书关系线索" in prompt
    assert "甄士隐梦幻识通灵 -> 甄士隐第二回经历" in prompt
    assert "source_chapters" in prompt
    assert "raw_only_marker" not in prompt
    assert '"entity_name"' not in prompt
    assert '"data"' not in prompt


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
    card = _complete_card_with_rich_defaults(chapter=27, id="review-027")

    assert module.validate_generated_card_output("# 第27回 标题 章节复习卡\n正文", card) == []


def test_validate_generated_card_output_rejects_empty_rich_sections():
    module = _import_script_module()
    card = _complete_card_with_rich_defaults(characters=[], relationships=[], annotations=[])

    errors = module.validate_generated_card_output("# 第1回 标题 章节复习卡\n正文", card)

    assert any("characters" in error and "不能为空" in error for error in errors)
    assert any("relationships" in error and "不能为空" in error for error in errors)
    assert any("annotations" in error and "不能为空" in error for error in errors)


def test_validate_generated_card_output_rejects_summary_outside_250_to_400_chars():
    module = _import_script_module()
    card = _complete_card_with_rich_defaults(plain_summary="太短。")

    errors = module.validate_generated_card_output("# 第1回 标题 章节复习卡\n正文", card)

    assert any("plain_summary" in error and "250—400" in error for error in errors)


def test_validate_generated_card_output_allows_internal_audit_terms_but_not_display_terms():
    module = _import_script_module()
    card = _complete_card_with_rich_defaults(
        chapter=27,
        id="review-027",
        internal={
            "evidence_audit": {
                "source": "LightRAG /query/data",
                "normalized_candidate_count": 2,
            }
        },
    )

    assert module.validate_generated_card_output("# 第27回 标题 章节复习卡\n正文", card) == []

    card["characters"] = [{"name": "林黛玉", "evidence": ["LightRAG 字样不能给学生看到"]}]

    errors = module.validate_generated_card_output("# 第27回 标题 章节复习卡\n正文", card)

    assert any("characters[0].evidence[0]" in error and "LightRAG" in error for error in errors)


def test_later_associations_require_normalized_later_evidence():
    module = _import_script_module()
    card = _complete_card_with_rich_defaults(
        later_associations=[
            {
                "topic": "甄士隐命运照应",
                "description": "甄士隐后续经历与本回梦幻结构互相照应。",
                "source_chapters": [2],
                "source_ids": ["rel-001-002"],
                "evidence": "关系线索显示甄士隐与第二回经历存在照应。",
            }
        ]
    )
    current_only_pack = module.build_evidence_pack(
        RelationshipEvidenceLightRAGClient(with_later_relationship=False).query_data("第一回", mode="hybrid"),
        question="第1回 甄士隐命运照应",
    )
    later_pack = module.build_evidence_pack(
        RelationshipEvidenceLightRAGClient(with_later_relationship=True).query_data("第一回", mode="hybrid"),
        question="第1回 甄士隐命运照应",
    )

    unsupported_errors = module.validate_generated_card_output(
        "# 第1回 标题 章节复习卡\n正文",
        card,
        evidence_pack=current_only_pack,
    )
    supported_errors = module.validate_generated_card_output(
        "# 第1回 标题 章节复习卡\n正文",
        card,
        evidence_pack=later_pack,
    )

    assert any("later_associations" in error and "缺少规范化证据" in error for error in unsupported_errors)
    assert supported_errors == []


def test_later_associations_must_match_supporting_evidence():
    module = _import_script_module()
    card = _complete_card_with_rich_defaults(
        later_associations=[
            {
                "topic": "贾宝玉挨打",
                "description": "宝玉挨打与本回甄士隐梦幻结构互相照应。",
                "source_chapters": [33],
                "evidence": "第三十三回宝玉挨打。",
            }
        ]
    )
    later_pack = module.build_evidence_pack(
        RelationshipEvidenceLightRAGClient(with_later_relationship=True).query_data("第一回", mode="hybrid"),
        question="第1回 甄士隐命运照应",
        chapter_number=1,
    )

    errors = module.validate_generated_card_output(
        "# 第1回 标题 章节复习卡\n正文",
        card,
        evidence_pack=later_pack,
    )

    assert any("later_associations[0]" in error and "缺少匹配证据" in error for error in errors)


def test_later_associations_require_machine_checkable_evidence_reference():
    module = _import_script_module()
    card = _complete_card_with_rich_defaults(
        later_associations=[
            {
                "topic": "甄士隐命运照应",
                "description": "甄士隐后续经历与本回梦幻结构互相照应。",
                "source_chapters": [2],
                "evidence": "关系线索显示甄士隐与第二回经历存在照应。",
            }
        ]
    )
    later_pack = module.build_evidence_pack(
        RelationshipEvidenceLightRAGClient(with_later_relationship=True).query_data("第一回", mode="hybrid"),
        question="第1回 甄士隐命运照应",
        chapter_number=1,
    )

    errors = module.validate_generated_card_output(
        "# 第1回 标题 章节复习卡\n正文",
        card,
        evidence_pack=later_pack,
    )

    assert any("later_associations[0]" in error and "证据引用" in error for error in errors)


def test_generate_cards_rejects_later_associations_without_normalized_later_evidence(tmp_path):
    module = _import_script_module()
    manifest_path = _write_manifest(tmp_path)

    try:
        module.generate_cards(
            manifest_path=manifest_path,
            output_dir=tmp_path / "generated",
            chapters=[1],
            lightrag_client=RelationshipEvidenceLightRAGClient(with_later_relationship=False),
            llm_client=EvidenceBackedAssociationLLMClient(),
            generated_at="2026-07-02",
            overwrite=True,
        )
    except ValueError as exc:
        assert "later_associations" in str(exc)
        assert "缺少规范化证据" in str(exc)
    else:
        raise AssertionError("expected unsupported later_associations to fail quality gate")


def test_generate_cards_accepts_later_associations_with_normalized_later_evidence(tmp_path):
    module = _import_script_module()
    manifest_path = _write_manifest(tmp_path)

    cards = module.generate_cards(
        manifest_path=manifest_path,
        output_dir=tmp_path / "generated",
        chapters=[1],
        lightrag_client=RelationshipEvidenceLightRAGClient(with_later_relationship=True),
        llm_client=EvidenceBackedAssociationLLMClient(),
        generated_at="2026-07-02",
        overwrite=True,
    )

    assert cards[0]["later_associations"][0]["source_chapters"] == [2]


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


def test_build_prompt_raw_response_fallback_filters_current_chapter_association_evidence():
    module = _import_script_module()

    prompt = module.build_prompt(
        chapter_number=1,
        chapter_title="甄士隐梦幻识通灵 贾雨村风尘怀闺秀",
        source_file="book/chapters/001.txt",
        chapter_text="第一回原文",
        lightrag_evidence={
            "status": "success",
            "data": {
                "entities": [],
                "relationships": [
                    {
                        "src_id": "甄士隐梦幻识通灵",
                        "tgt_id": "真假有无",
                        "keywords": "伏笔照应",
                        "description": "本回梦幻结构照应本回真假有无叙事。",
                        "source_id": "rel-current-only",
                        "file_path": "001-第一回-甄士隐梦幻识通灵 贾雨村风尘怀闺秀.txt",
                    }
                ],
                "chunks": [],
                "references": [],
            },
            "metadata": {"query_mode": "hybrid"},
        },
        generated_at="2026-07-02",
    )

    assert "甄士隐梦幻识通灵 -> 真假有无" in prompt
    assert '"later_association_evidence": []' in prompt


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

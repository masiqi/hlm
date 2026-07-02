# Chapter Card Quality Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the chapter review card generation pipeline before producing all 120 cards, so generated Markdown and structured JSON are safe for student-facing display and useful for PostgreSQL-backed chapter/card navigation.

**Architecture:** Keep `scripts/generate_chapter_cards.py` as the generator entry point, but make the prompt and extracted JSON contract stricter. Add deterministic quality gates in the generator so malformed or student-inappropriate output fails before import. Keep Markdown as the rich human-review artifact and AppImportJSON as the machine-readable website/database import artifact.

**Tech Stack:** Python standard library, pytest, existing `hlm_kg` domain/content modules, GitHub issue #26.

## Global Constraints

- Issue anchor: https://github.com/masiqi/hlm/issues/26
- Student-facing generated content must not show `LightRAG`, `RAG`, `知识图谱`, `向量检索`, `置信度`, `模型分数`, `标准答案`, `题库`, `下一题`, `提交答案`, `批改`.
- 本回事实必须来自本回原文；后文关联、跨章伏笔、命运照应必须来自系统提供的全书关系线索或明确后续章回证据。
- 资料不足时必须写“本回暂不能确定”或“需结合后文”，不能生成确定结论。
- 生成内容不是题库，不提供标准答案、评分、批改或刷题流程。
- Do not print `.env`, API keys, database passwords, or full `DATABASE_URL`.
- Preserve existing generated artifacts unless a task explicitly regenerates them.

---

### Task 1: Prompt And AppImportJSON Contract

**Files:**
- Modify: `scripts/generate_chapter_cards.py`
- Modify: `tests/test_generate_chapter_cards.py`
- Modify: `data/prompts/definitions.json`
- Modify: `docs/chapter_review_card_pipeline.md`

**Interfaces:**
- Consumes: `build_prompt(chapter_number, chapter_title, source_file, chapter_text, lightrag_evidence, generated_at) -> str`
- Produces: a prompt requiring clean Markdown, no technical implementation terms in displayable output, and a richer `AppImportJSON` shape.

- [ ] **Step 1: Write failing tests for the prompt contract**

Add tests in `tests/test_generate_chapter_cards.py`:

```python
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
```

Add a second test that checks the JSON contract names the new structured fields:

```python
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
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_generate_chapter_cards.py::test_build_prompt_uses_student_facing_source_names_and_forbids_technical_terms_in_markdown tests/test_generate_chapter_cards.py::test_build_prompt_requests_structured_app_import_sections_for_website_and_database -q
```

Expected: FAIL because the current prompt still names `LightRAG 全书关系线索` and does not include all structured fields.

- [ ] **Step 3: Update the prompt and prompt definition**

In `scripts/generate_chapter_cards.py`:

- Replace student-visible references to `LightRAG 全书关系线索` with `系统提供的全书关系线索`.
- Keep a developer-side comment or variable name if useful, but generated Markdown/JSON instructions must use student-facing source names.
- Add an explicit output rule: output must begin with `# 第{chapter_number}回 {chapter_title} 章节复习卡`; no greeting, no explanatory wrapper.
- Expand `AppImportJSON` schema with:

```json
"characters": [
  {
    "name": "人物名",
    "aliases": ["称谓或别名"],
    "role": "身份/关系",
    "actions": ["本回主要行为"],
    "traits": ["有情节支撑的性格特点"],
    "evidence": ["具体情节或短依据"],
    "importance": "本回作用"
  }
],
"relationships": [
  {
    "source": "人物/事件/物件",
    "type": "关系类型",
    "target": "人物/事件/物件",
    "description": "具体关系说明",
    "chapter_evidence": "本回依据"
  }
],
"places": [
  {
    "name": "地点名",
    "scenes": ["出现的情节场景"],
    "function": "对人物/主题/情节的作用"
  }
],
"objects": [
  {
    "name": "物件/意象名",
    "context": "原文情境",
    "meaning": "象征或作用",
    "related_entities": ["相关人物或事件"]
  }
],
"literary_texts": [
  {
    "title": "诗词曲文/对联/判词/语言细节",
    "short_quote": "不超过80字的短摘录",
    "explanation": "现代解释",
    "function": "作用分析"
  }
],
"modern_explanations": [
  {
    "quote": "原文语句",
    "modern_text": "现代汉语解释",
    "value": "理解重点或考查价值"
  }
],
"later_associations": [
  {
    "topic": "后文关联对象",
    "description": "后文关联说明",
    "source_chapters": [74],
    "evidence": "必须来自系统提供的全书关系线索或明确后续章回证据",
    "relation_id": null
  }
],
"annotations": [
  {
    "text": "原文中可点击的词语",
    "kind": "person/event/object/place/foreshadowing/literary_text",
    "target": "对应信息卡或实体名",
    "note": "点击后展示的简要说明"
  }
]
```

Update `data/prompts/definitions.json` and `docs/chapter_review_card_pipeline.md` so the registered contract matches the expanded schema and source naming.

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
pytest tests/test_generate_chapter_cards.py -q
```

Expected: all tests in that file pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_chapter_cards.py tests/test_generate_chapter_cards.py data/prompts/definitions.json docs/chapter_review_card_pipeline.md docs/superpowers/plans/2026-07-02-chapter-card-quality-gate.md
git commit -m "feat: harden chapter card generation contract"
```

### Task 2: Deterministic Quality Gate

**Files:**
- Modify: `scripts/generate_chapter_cards.py`
- Modify: `tests/test_generate_chapter_cards.py`
- Modify: `docs/chapter_review_card_pipeline.md`

**Interfaces:**
- Produces: `validate_generated_card_output(markdown: str, card: Mapping[str, Any]) -> list[str]`
- `generate_cards(...)` must call this validator before writing Markdown/JSON outputs.

- [ ] **Step 1: Write failing tests for validator behavior**

Add tests in `tests/test_generate_chapter_cards.py`:

```python
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
```

Add a positive test:

```python
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
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_generate_chapter_cards.py::test_validate_generated_card_output_rejects_technical_terms_and_greeting tests/test_generate_chapter_cards.py::test_validate_generated_card_output_accepts_clean_extended_card -q
```

Expected: FAIL because `validate_generated_card_output` does not exist.

- [ ] **Step 3: Implement validator and generation integration**

In `scripts/generate_chapter_cards.py`:

- Add `STUDENT_FORBIDDEN_TERMS`.
- Add `DISPLAY_CARD_FIELDS` for strings/lists/dicts that are student-visible.
- Implement recursive text scanning over card values.
- Reject Markdown whose first non-whitespace character is not `#` or whose first line does not start with `# 第`.
- Reject forbidden terms in Markdown and displayable JSON fields.
- Reject missing required base fields.
- Treat extended fields as optional for backward compatibility, but if present they must be lists.
- In `generate_cards`, after extracting `card`, call `validate_generated_card_output(markdown, card)`. If errors exist, write failed Markdown to `generated/failed/NNN.md` and raise `ValueError` with a concise error summary.

- [ ] **Step 4: Run focused tests**

Run:

```bash
pytest tests/test_generate_chapter_cards.py -q
```

Expected: all tests in the file pass.

- [ ] **Step 5: Run broader generator/import tests**

Run:

```bash
pytest tests/test_generate_chapter_cards.py tests/test_import_chapter_cards.py tests/test_prompt_registry.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/generate_chapter_cards.py tests/test_generate_chapter_cards.py docs/chapter_review_card_pipeline.md
git commit -m "feat: validate chapter card generation output"
```

### Task 3: Documentation And Issue Update

**Files:**
- Modify: `docs/chapter_review_card_pipeline.md`
- Modify: `docs/superpowers/plans/2026-07-02-chapter-card-quality-gate.md`

**Interfaces:**
- Produces: documented next operating sequence for sample generation, all-120 generation, and PostgreSQL import.

- [ ] **Step 1: Update docs**

Document:

- Markdown is the rich human-review artifact.
- AppImportJSON is the structured website/database import artifact.
- The website should consume JSON/PostgreSQL fields, not parse Markdown for core interactions.
- Run 10 sample chapters first, inspect quality, then run `--all`.
- After generation, import into the application data/PostgreSQL pipeline.

- [ ] **Step 2: Run documentation-related tests**

Run:

```bash
pytest tests/test_prompt_registry.py tests/test_generate_chapter_cards.py -q
```

Expected: selected tests pass.

- [ ] **Step 3: Update GitHub issue #26**

Add a comment to #26 summarizing:

- Branch used.
- Prompt contract hardened.
- Quality gate added.
- Next step is regenerate 10 samples, then all 120.

Command:

```bash
gh issue comment 26 --repo masiqi/hlm --body "<Chinese summary>"
```

- [ ] **Step 4: Commit docs if changed**

```bash
git add docs/chapter_review_card_pipeline.md docs/superpowers/plans/2026-07-02-chapter-card-quality-gate.md
git commit -m "docs: document chapter card generation gate"
```

### Task 4: Final Verification And Review

**Files:**
- No planned edits unless review findings require fixes.

**Interfaces:**
- Produces: fresh verification evidence and review feedback before final response.

- [ ] **Step 1: Run full test suite**

Run:

```bash
pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run validation samples**

Run:

```bash
python -m hlm_kg.validation_samples
```

Expected: no issues reported.

- [ ] **Step 3: Request final code review**

Dispatch code reviewer with:

- Scope: changes since the branch base for #26.
- Requirements: global constraints from this plan and issue #26 acceptance criteria.
- Focus: prompt safety, quality gate correctness, backward compatibility, and whether the generated fields are enough for website/PostgreSQL import.

- [ ] **Step 4: Fix Critical/Important findings**

If review returns Critical or Important findings:

- Add/adjust tests first.
- Implement fix.
- Rerun focused tests.
- Rerun final verification if behavior changed.

- [ ] **Step 5: Final status**

Report:

- Commits created.
- Tests run and results.
- Whether #26 is fully done or still needs sample/all-120 generation.
- Exact next command to generate 10 samples, without printing secrets.

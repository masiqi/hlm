# PostgreSQL Rich Reading UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the V1 website with the latest PostgreSQL-first product decision so students see rich chapter-card material, clickable original-text entities, and entity popovers with related clues and chapter jumps.

**Architecture:** PostgreSQL is the authoritative runtime store when `DATABASE_URL` is configured and `.env` or process env selects it. Generated Markdown remains the full audit/study artifact, while AppImportJSON must contain enough structured material for the website: 250-400 word summary, people, relationships, places, objects, language details, later associations, and annotations. The chapter API returns a page-ready evidence bundle so the frontend can render rich sections and open a contextual entity popover without exposing internal technical terms.

**Tech Stack:** Python 3.13 stdlib HTTP server, PostgreSQL via `psycopg`, JSONB `chapter_cards.raw_card`, vanilla JavaScript/CSS frontend, pytest.

## Global Constraints

- Do not modify `main` directly; implementation branch is `feat/pg-rich-reading-ui`.
- Student-facing UI/content must not expose: `LightRAG`, `RAG`, `知识图谱`, `向量检索`, `置信度`, `模型分数`, `标准答案`, `题库`, `下一题`, `提交答案`, `批改`.
- Runtime answers and chapter materials must be based on original text, generated chapter cards, or retrieved relationship evidence; do not fill missing content with model guesses.
- PostgreSQL is the runtime source of truth for the web app once configured; JSON files remain staging/audit/fallback artifacts.
- Missing chapter-card material must show “暂无可靠资料/章节资料暂未生成”，not synthesized filler.
- Full Markdown chapter cards should preserve detailed study content; AppImportJSON must preserve the structured subset needed by the website.

---

### Task 1: PostgreSQL Runtime Selection

**Files:**
- Modify: `hlm_kg/web_app.py`
- Modify: `tests/test_web_app.py`
- Modify: `Makefile`

**Interfaces:**
- Consumes: `load_dotenv()`, `load_database_url()`, and existing `PostgresContentStore(database_url, fallback_store)`.
- Produces: `create_app_context(...)` that treats `.env` and process env consistently, and `make web` that can serve the PostgreSQL-backed site without command-prefix env hacks.

- [ ] **Step 1: Write failing tests**

Add tests proving:

```python
def test_create_app_context_enables_postgres_from_dotenv_flag(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    Path(".env").write_text(
        "DATABASE_URL=postgresql://user:p*ss@example.local:5432/hlm\n"
        "HLM_CONTENT_STORE=postgres\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("hlm_kg.web_app.PostgresContentStore", lambda database_url, fallback_store: ("postgres", database_url, fallback_store))

    context = create_app_context(
        manifest_path=ROOT / "book/chapters_manifest.json",
        data_dir=ROOT / "data/app",
        static_dir=ROOT / "static",
    )

    assert context.store[0] == "postgres"
    assert context.store[1] == "postgresql://user:p*ss@example.local:5432/hlm"
```

and:

```python
def test_makefile_web_uses_python_module_without_inline_secret_env():
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert "python -m hlm_kg.web_app" in makefile
    assert "DATABASE_URL=" not in makefile
```

- [ ] **Step 2: Run focused tests and confirm failure**

Run:

```bash
pytest tests/test_web_app.py::test_create_app_context_enables_postgres_from_dotenv_flag -q
```

Expected: fails because `create_app_context` currently checks only `os.environ.get("HLM_CONTENT_STORE")`.

- [ ] **Step 3: Implement env merge**

In `create_app_context`, load `.env` once and use it for both PostgreSQL and retrieval config:

```python
dotenv = load_dotenv()
postgres_setting = os.environ.get("HLM_CONTENT_STORE", dotenv.get("HLM_CONTENT_STORE"))
postgres_enabled = use_postgres_store or parse_bool(postgres_setting)
if postgres_enabled:
    database_url = load_database_url() or load_database_url(dotenv)
```

Keep process env higher priority than `.env`.

- [ ] **Step 4: Run focused tests**

Run:

```bash
pytest tests/test_web_app.py::test_create_app_context_enables_postgres_from_dotenv_flag tests/test_web_app.py::test_create_app_context_reads_postgres_database_url_from_dotenv -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add hlm_kg/web_app.py tests/test_web_app.py Makefile
git commit -m "fix: enable postgres web store from dotenv"
```

### Task 2: Chapter Card Richness Quality Gate

**Files:**
- Modify: `scripts/generate_chapter_cards.py`
- Modify: `tests/test_generate_chapter_cards.py`

**Interfaces:**
- Consumes: `validate_generated_card_output(markdown, card, evidence_pack=...)`.
- Produces: validation errors when newly generated cards are too shallow for the website.

- [ ] **Step 1: Write failing tests**

Add tests:

```python
def test_validate_generated_card_output_rejects_empty_rich_sections():
    module = _import_script_module()
    card = _complete_card_with_rich_defaults(
        plain_summary="本回主要写宝玉与探春等人在园中围绕家务与人情展开的情节。"
    )
    card["characters"] = []
    card["relationships"] = []
    card["annotations"] = []

    errors = module.validate_generated_card_output("# 第56回 标题 章节复习卡\n正文", card)

    assert any("characters" in error and "不能为空" in error for error in errors)
    assert any("relationships" in error and "不能为空" in error for error in errors)
    assert any("annotations" in error and "不能为空" in error for error in errors)
```

and:

```python
def test_validate_generated_card_output_rejects_summary_outside_250_to_400_chars():
    module = _import_script_module()
    card = _complete_card_with_rich_defaults(plain_summary="太短。")

    errors = module.validate_generated_card_output("# 第27回 标题 章节复习卡\n正文", card)

    assert any("plain_summary" in error and "250—400" in error for error in errors)
```

- [ ] **Step 2: Run focused tests and confirm failure**

Run:

```bash
pytest tests/test_generate_chapter_cards.py::test_validate_generated_card_output_rejects_empty_rich_sections tests/test_generate_chapter_cards.py::test_validate_generated_card_output_rejects_summary_outside_250_to_400_chars -q
```

Expected: fail because current validation accepts empty rich lists and short summaries.

- [ ] **Step 3: Implement validation**

Add required rich sections:

```python
REQUIRED_NON_EMPTY_RICH_FIELDS = ("characters", "relationships", "annotations")
SUMMARY_MIN_CHARS = 250
SUMMARY_MAX_CHARS = 400
```

In validation:

```python
summary_length = len(str(card.get("plain_summary") or "").strip())
if summary_length and not SUMMARY_MIN_CHARS <= summary_length <= SUMMARY_MAX_CHARS:
    errors.append("AppImportJSON 字段 plain_summary 必须为 250—400 字。")
for field in REQUIRED_NON_EMPTY_RICH_FIELDS:
    if isinstance(card.get(field), list) and not card[field]:
        errors.append(f"AppImportJSON 字段 {field} 不能为空，网站需要它展示人物、关系或原文链接。")
```

Do not require `later_associations`; it remains evidence-gated and may be empty.

- [ ] **Step 4: Update fake cards**

Update existing fake LLM/test cards so valid fixtures include:

```json
"characters": [{"name": "甄士隐", "aliases": [], "role": "乡宦", "actions": ["梦中见通灵宝玉来历"], "traits": ["有出世意味"], "evidence": ["甄士隐梦幻识通灵"], "importance": "引出真假有无结构"}],
"relationships": [{"source": "甄士隐", "type": "参与", "target": "甄士隐梦幻识通灵", "description": "甄士隐在梦中见到通灵宝玉来历。", "chapter_evidence": "本回梦幻情节"}],
"annotations": [{"text": "甄士隐", "kind": "person", "target": "甄士隐", "note": "本回开篇人物"}]
```

Use 250-400 Chinese-character summaries in valid fixtures.

- [ ] **Step 5: Run focused tests**

Run:

```bash
pytest tests/test_generate_chapter_cards.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/generate_chapter_cards.py tests/test_generate_chapter_cards.py
git commit -m "test: require rich chapter card sections"
```

### Task 3: Chapter API Rich Entity Payload

**Files:**
- Modify: `hlm_kg/web_app.py`
- Modify: `tests/test_web_app.py`

**Interfaces:**
- Consumes: `ChapterReviewCard.characters`, `.relationships`, `.places`, `.objects`, `.literary_texts`, `.modern_explanations`, `.later_associations`, and `ChapterAnnotation`.
- Produces: `/api/chapters/{number}` payload with `inlineEntities`, each item having `id`, `name`, `type`, `summary`, `details`, `relations`, `traceItems`, and `chapterJumps`.

- [ ] **Step 1: Write failing API test**

Add a minimal review card with `characters`, `relationships`, `objects`, `later_associations`, and annotations where target is a name. Assert:

```python
assert payload["inlineEntities"][0]["name"] == "袭人"
assert payload["inlineEntities"][0]["summary"]
assert payload["inlineEntities"][0]["relations"]
assert payload["inlineEntities"][0]["chapterJumps"]
assert payload["annotations"][0]["entityId"] == payload["inlineEntities"][0]["id"]
```

- [ ] **Step 2: Run focused test and confirm failure**

Run:

```bash
pytest tests/test_web_app.py::test_api_chapter_returns_inline_entity_payload_from_review_card -q
```

Expected: fail because `inlineEntities` does not exist.

- [ ] **Step 3: Implement chapter inline entity builder**

Add helper functions in `web_app.py`:

```python
def _inline_entities_for_review_card(review_card: ChapterReviewCard) -> list[dict[str, Any]]:
    ...
```

Rules:
- Build one entity per `characters[*].name`, `places[*].name`, `objects[*].name`, `literary_texts[*].title`, and later association `topic`.
- Stable id format: `chapter-{chapter:03d}-entity-{slug}`.
- Match annotations by `target`, `text`, or generated stable id.
- Include relations whose `source` or `target` equals entity name.
- Include chapter jumps from `later_associations[*].source_chapters` and from relationship `source_chapters` when present.
- Never include internal audit fields.

- [ ] **Step 4: Attach resolved annotation ids**

In the chapter API:

```python
inline_entities = _inline_entities_for_review_card(review_card) if review_card else []
annotations = _chapter_annotations_payload(...)
```

When DB annotations do not exist but `reviewCard.annotations` exists, synthesize offsets from `originalText` using the annotation text and map to inline entity ids. This lets current generated cards work before DB annotation rows are inserted.

- [ ] **Step 5: Run focused tests**

Run:

```bash
pytest tests/test_web_app.py::test_api_chapter_returns_inline_entity_payload_from_review_card tests/test_web_app.py::test_api_chapter_returns_extended_review_card_fields -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add hlm_kg/web_app.py tests/test_web_app.py
git commit -m "feat: expose inline chapter entities"
```

### Task 4: Rich Chapter Page And Entity Popover

**Files:**
- Modify: `static/app.js`
- Modify: `static/styles.css`
- Modify: `tests/test_web_app.py`

**Interfaces:**
- Consumes: `/api/chapters/{number}` payload with `reviewCard`, `inlineEntities`, `annotations`.
- Produces: a student-facing page that shows rich sections and opens a floating entity popover when clicking original-text annotations or entity chips.

- [ ] **Step 1: Write static regression tests**

Add tests asserting `static/app.js` contains:

```python
assert "renderEntityPopover" in js
assert "data-inline-entity-id" in js
assert "renderRichSection" in js
assert "characters" in js
assert "relationships" in js
assert "laterAssociations" in js
```

and `static/styles.css` contains:

```python
assert ".entity-popover" in css
assert ".chapter-section-grid" in css
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
pytest tests/test_web_app.py::test_static_chapter_page_renders_rich_sections_and_entity_popover -q
```

Expected: fail.

- [ ] **Step 3: Implement frontend state and popover**

Add:

```javascript
let currentChapterPayload = null;
function findInlineEntity(entityId) { ... }
function renderEntityPopover(entity) { ... }
function openEntityPopover(entityId) { ... }
function closeEntityPopover() { ... }
```

Popover content must include:
- name and type
- summary/details
- relations
- later clues
- chapter jump buttons

- [ ] **Step 4: Render rich chapter sections**

In `loadChapter`, render:
- 本回梗概
- 情节链
- 主要人物 cards from `reviewCard.characters`
- 人物/事件/物件关系 from `reviewCard.relationships`
- 地点与物件
- 诗词语言
- 后文关联
- 原文

Use “暂无可靠资料” for empty sections.

- [ ] **Step 5: Connect clicks**

Original-text annotation buttons should use `data-inline-entity-id`; entity chips/cards should also open the same popover. Chapter jump buttons call `loadChapter(Number(...))`.

- [ ] **Step 6: Run focused tests**

Run:

```bash
pytest tests/test_web_app.py::test_static_chapter_page_renders_rich_sections_and_entity_popover tests/test_web_app.py::test_static_chapter_view_uses_offset_annotations_not_name_replacement tests/test_web_app.py::test_static_styles_include_trace_and_annotation_states -q
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add static/app.js static/styles.css tests/test_web_app.py
git commit -m "feat: render rich chapter entity popovers"
```

### Task 5: Verification And Issue Update

**Files:**
- Modify: `docs/issue_alignment_2026-07-02.md` if current issue alignment needs a short addendum.

**Interfaces:**
- Consumes: all prior tasks.
- Produces: test evidence and GitHub issue comments for #26 and #28.

- [ ] **Step 1: Run full tests**

Run:

```bash
pytest -q
python -m hlm_kg.validation_samples
```

Expected: all pass and no validation sample problems.

- [ ] **Step 2: Start local web app in PG mode**

Run a safe command that does not print secrets:

```bash
python -m hlm_kg.web_app
```

With `.env` `HLM_CONTENT_STORE=postgres`, the server should use PostgreSQL. Verify:

```bash
python -c "import json, urllib.request; data=json.load(urllib.request.urlopen('http://127.0.0.1:8765/api/chapters/27')); print(data['materialStatus'], len(data.get('inlineEntities', [])))"
```

- [ ] **Step 3: Update GitHub issues**

Comment on #26:
- Markdown richness is preserved.
- AppImportJSON quality gate now rejects shallow cards.
- Existing 27/56 samples are known too shallow and must be regenerated.

Comment on #28:
- Chapter API/frontend now support rich sections and entity popover.
- Full usefulness depends on #26 generating rich annotations/entities.

- [ ] **Step 4: Final status**

Report branch, commits, tests, local URL, and remaining data-generation work.

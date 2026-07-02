# LightRAG Evidence Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the post-index V1 evidence pipeline so the product can combine original text, generated chapter review cards, and LightRAG `/query/data` evidence for fast, evidence-bound 《红楼梦》 reading support.

**Architecture:** Keep LightRAG as a retrieval data source, not a final answer generator. Add a small standard-library client, normalize LightRAG query data into product evidence candidates, parse chapter provenance from file paths, then feed the existing ask and UI layers through evidence packs. Chapter review card generation is treated as a parallel content pipeline: code can ingest samples first and full 120-chapter output later.

**Tech Stack:** Python 3.13, standard library HTTP/JSON, dataclasses, pytest, static HTML/CSS/JS, GitHub Issues.

## Global Constraints

- Never modify `main` directly; work from issue-scoped branches.
- Student-facing UI must not show `LightRAG`, `RAG`, `知识图谱`, `向量检索`, `置信度`, `模型分数`, `标准答案`, `题库`, `下一题`, `提交答案`, or `批改`.
- Do not use LightRAG `/query` as the final product answer source.
- Use `/query/data` for evidence retrieval and preserve `file_path`, `source_id`, `chunk_id`, and `reference_id` whenever present.
- Final answers must be based on original text, generated chapter review cards, or LightRAG evidence; evidence-insufficient questions must be refused.
- Chapter review cards must include chapter-level summary content for fast reading; later associations must come from LightRAG or explicit later-chapter evidence.
- Calibration samples in `questions/` are internal only and must not become a student-facing question bank.
- V1 target is a web product, not an app, not a full ebook reader, and not a grading or practice system.

---

## Issue Sequence

1. #24 接入 LightRAG `/query/data` 证据召回适配层.
2. #25 解析章回来源并归一化 LightRAG 证据.
3. #26 批量生成并导入 120 回章节复习卡.
4. #27 实现证据约束问答编排与严格拒答.
5. #28 升级章节页和知识面板展示三源证据.
6. #29 建立三源合一验证样例与质量门禁.

## File Structure

- Create `hlm_kg/chapter_sources.py`: parse `001-第一回-...txt` source paths into chapter provenance.
- Create `hlm_kg/lightrag_client.py`: LightRAG `/query/data`, label search, and entity existence client with environment configuration.
- Create `hlm_kg/evidence_adapter.py`: normalize LightRAG query data into internal evidence candidates.
- Modify `hlm_kg/evidence.py`: add candidate ranking helpers after normalization.
- Modify `hlm_kg/ask_engine.py`: later consume evidence candidates instead of seed-only branches.
- Modify `hlm_kg/content_store.py`: later load generated chapter card records.
- Create `scripts/import_chapter_cards.py`: later import generated Markdown/JSON chapter review cards.
- Modify `static/app.js`, `static/index.html`, and `static/styles.css`: later render evidence packs and chapter-card quick-reading sections.
- Add tests under `tests/` for each module; CI must use mocked LightRAG responses.

## Task 1: Chapter Source Parsing

**Files:**
- Create: `hlm_kg/chapter_sources.py`
- Test: `tests/test_chapter_sources.py`

**Interfaces:**
- Produces: `ChapterSource`, `parse_chapter_source(file_path: str) -> ChapterSource | None`, `parse_chapter_sources(value: str | None) -> list[ChapterSource]`.
- Consumes: LightRAG `file_path` strings, including `<SEP>`-joined paths.

- [ ] **Step 1: Write failing tests**

Create `tests/test_chapter_sources.py` with tests for:

```python
from hlm_kg.chapter_sources import parse_chapter_source, parse_chapter_sources


def test_parse_standard_chapter_file_path():
    source = parse_chapter_source("003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt")

    assert source is not None
    assert source.chapter_number == 3
    assert source.chapter_label == "第三回"
    assert source.chapter_title == "托内兄如海荐西宾 接外孙贾母惜孤女"
    assert source.source_file == "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt"


def test_parse_path_with_directory():
    source = parse_chapter_source("book/chapters/120-第一百二十回-甄士隐详说太虚情 贾雨村归结红楼梦.txt")

    assert source is not None
    assert source.chapter_number == 120
    assert source.chapter_label == "第一百二十回"
    assert source.chapter_title == "甄士隐详说太虚情 贾雨村归结红楼梦"


def test_parse_multiple_sep_sources_deduplicates():
    sources = parse_chapter_sources(
        "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt<SEP>"
        "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt<SEP>"
        "027-第二十七回-滴翠亭杨妃戏彩蝶 埋香冢飞燕泣残红.txt"
    )

    assert [source.chapter_number for source in sources] == [3, 27]


def test_non_chapter_source_returns_none():
    assert parse_chapter_source("not-a-chapter.md") is None
```

- [ ] **Step 2: Run failing tests**

Run: `pytest tests/test_chapter_sources.py -q`

Expected: fail because `hlm_kg.chapter_sources` does not exist.

- [ ] **Step 3: Implement parser**

Implement dataclass parser with a strict regex for `NNN-中文回目-标题.txt` and `<SEP>` splitting.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_chapter_sources.py -q`

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add hlm_kg/chapter_sources.py tests/test_chapter_sources.py
git commit -m "feat: parse chapter source paths"
```

## Task 2: LightRAG Client

**Files:**
- Create: `hlm_kg/lightrag_client.py`
- Test: `tests/test_lightrag_client.py`

**Interfaces:**
- Produces: `LightRAGClient`, `LightRAGConfig`, `LightRAGError`.
- `LightRAGClient.query_data(query: str, mode: str = "hybrid", **options: object) -> dict`
- `LightRAGClient.search_labels(q: str, limit: int = 10) -> list[str]`
- `LightRAGClient.entity_exists(name: str) -> bool`
- `LightRAGConfig.from_env(env: Mapping[str, str]) -> LightRAGConfig | None`

- [ ] **Step 1: Write failing tests**

Tests must use monkeypatched opener functions; CI must not call `10.1.0.246`.

- [ ] **Step 2: Implement standard-library client**

Use `urllib.request`, JSON request/response handling, optional `X-API-Key`, and deterministic error messages.

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_lightrag_client.py -q`

- [ ] **Step 4: Commit**

```bash
git add hlm_kg/lightrag_client.py tests/test_lightrag_client.py
git commit -m "feat: add lightrag query data client"
```

## Task 3: Evidence Candidate Normalization

**Files:**
- Create: `hlm_kg/evidence_adapter.py`
- Test: `tests/test_evidence_adapter.py`

**Interfaces:**
- Produces: `EvidenceCandidate`, `normalize_query_data_response(response: Mapping[str, object], question: str = "") -> list[EvidenceCandidate]`.
- Consumes: `ChapterSource` from Task 1.

- [ ] **Step 1: Write failing tests**

Cover hybrid entity/relationship responses, naive chunk/reference responses, `<SEP>` file paths, and basic keyword scoring.

- [ ] **Step 2: Implement normalizer**

Normalize candidate type, title, description, source IDs, file paths, parsed chapter sources, raw payload, and a simple score.

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_evidence_adapter.py -q`

- [ ] **Step 4: Commit**

```bash
git add hlm_kg/evidence_adapter.py tests/test_evidence_adapter.py
git commit -m "feat: normalize lightrag evidence"
```

## Task 4: Chapter Review Card Pipeline Spec and Prompt Registry

**Files:**
- Modify: `data/prompts/definitions.json`
- Create: `docs/chapter_review_card_pipeline.md`
- Test: `tests/test_prompt_registry.py`

**Interfaces:**
- Produces documented prompt expectations for 120-chapter generation.
- Confirms prompt includes chapter content summary sections and LightRAG-backed later association rules.

- [ ] **Step 1: Add tests for prompt metadata**

Validate prompt definition mentions chapter summary, plot chain, LightRAG-backed later associations, and student-facing quick reading.

- [ ] **Step 2: Update prompt definition/docs**

Save the current prompt contract and first-batch generation order: 3, 5, 8, 27, 31, 33, 56, 63, 74, 97.

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_prompt_registry.py -q`

- [ ] **Step 4: Commit**

```bash
git add data/prompts/definitions.json docs/chapter_review_card_pipeline.md tests/test_prompt_registry.py
git commit -m "docs: define chapter review card pipeline"
```

## Task 5: Ask Engine Integration

**Files:**
- Modify: `hlm_kg/ask_engine.py`
- Modify: `hlm_kg/web_app.py`
- Test: `tests/test_ask_engine.py`, `tests/test_web_app.py`

**Interfaces:**
- Consumes: `LightRAGClient`, `EvidenceCandidate`.
- Produces: answer payloads with evidence candidates and chapter links.

- [ ] **Step 1: Write failing tests for “宝黛初会发生在哪一回”**

Use fake LightRAG response from `/query/data hybrid` with `file_path` for chapter 3.

- [ ] **Step 2: Implement adapter-backed path**

Keep seed fallback if LightRAG is not configured.

- [ ] **Step 3: Run focused tests**

Run: `pytest tests/test_ask_engine.py tests/test_web_app.py -q`

- [ ] **Step 4: Commit**

```bash
git add hlm_kg/ask_engine.py hlm_kg/web_app.py tests/test_ask_engine.py tests/test_web_app.py
git commit -m "feat: answer from normalized evidence"
```

## Task 6: UI Evidence Display

**Files:**
- Modify: `static/index.html`
- Modify: `static/app.js`
- Modify: `static/styles.css`
- Test: `tests/test_student_language.py`, `tests/test_web_app.py`

**Interfaces:**
- Consumes API evidence pack.
- Produces student-facing evidence display without forbidden technical terms.

- [ ] **Step 1: Add failing student-language/UI tests**

Ensure evidence sections use 原文依据、章节资料、关系线索、相关章回.

- [ ] **Step 2: Render evidence pack and quick chapter material**

Keep mobile knowledge panel usable.

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_student_language.py tests/test_web_app.py -q`

- [ ] **Step 4: Commit**

```bash
git add static/index.html static/app.js static/styles.css tests/test_student_language.py tests/test_web_app.py
git commit -m "feat: show evidence in reading assistant ui"
```

## Task 7: Validation Samples

**Files:**
- Modify: `data/app/validation_samples.json`
- Modify: `hlm_kg/validation_samples.py`
- Test: `tests/test_validation_samples.py`

**Interfaces:**
- Produces internal validation samples covering six capability categories.

- [ ] **Step 1: Add validation samples**

Cover 人物关系、章回情节、判词命运、主题意象、事件因果、拒答.

- [ ] **Step 2: Update validation command**

Ensure CI uses fixtures and never requires live LightRAG.

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_validation_samples.py -q`

- [ ] **Step 4: Commit**

```bash
git add data/app/validation_samples.json hlm_kg/validation_samples.py tests/test_validation_samples.py
git commit -m "test: expand evidence validation samples"
```

## Execution Notes

- First implementation pass should complete Tasks 1-4 on branch `feat/lightrag-evidence-pipeline`.
- Tasks 5-7 may be separate PRs if review size grows.
- Chapter review card content generation can run in parallel as issue #26. The code must tolerate missing cards.

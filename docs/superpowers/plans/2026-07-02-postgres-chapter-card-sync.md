# PostgreSQL Chapter Card Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate PostgreSQL with the expanded chapter-card contract, then support single-chapter regeneration and scoped Markdown/JSON/PostgreSQL synchronization.

**Architecture:** Keep generated Markdown and per-chapter JSON as staging and audit artifacts. PostgreSQL becomes the runtime store after explicit sync/import. Preserve the expanded `ChapterReviewCard` fields across JSON store, PostgreSQL store, APIs, and UI without parsing Markdown at runtime.

**Tech Stack:** Python 3.13, pytest, psycopg, PostgreSQL JSONB, existing static web app, GitHub Issues #31 and #32.

## Global Constraints

- Development issues: #31 first, then #32. Related quality issue: #29.
- Do not commit `.env`, database URLs, API keys, database passwords, or generated secrets.
- Do not print `DATABASE_URL` or secret-bearing configuration in logs, errors, issue comments, PR text, or docs.
- Student-facing responses and UI text must not expose: `LightRAG`, `RAG`, `知识图谱`, `向量检索`, `置信度`, `模型分数`, `标准答案`, `题库`, `下一题`, `提交答案`, `批改`.
- Runtime UI must read structured JSON/PostgreSQL fields, not parse Markdown.
- Generated JSON remains a review/import artifact even when PostgreSQL is the runtime store.
- Use LightRAG `/query/data` as evidence input; do not use LightRAG `/query` as the trusted final answer source.
- Tests must not require live LightRAG or a live PostgreSQL server unless documented as manual smoke tests.

---

### Task 1: Integrate PostgreSQL Without Regressing Chapter Card Fields

**Files:**
- Create/merge: `db/migrations/001_postgres_trace_graph.sql`
- Create/merge: `hlm_kg/postgres_config.py`
- Create/merge: `hlm_kg/postgres_store.py`
- Create/merge: `scripts/migrate_postgres.py`
- Create/merge: `scripts/import_postgres_seed.py`
- Modify: `hlm_kg/domain.py`
- Modify: `hlm_kg/content_store.py`
- Modify: `hlm_kg/web_app.py`
- Modify: `requirements.txt`
- Modify: `Makefile`
- Test: `tests/test_postgres_migration.py`
- Test: `tests/test_postgres_store.py`
- Test: `tests/test_import_postgres_seed.py`
- Test: `tests/test_web_app.py`

**Interfaces:**
- Consumes: expanded `ChapterReviewCard` fields from the current branch.
- Produces: optional PostgreSQL content store selected by `HLM_CONTENT_STORE=postgres` or explicit `use_postgres_store=True`.
- Produces: `/api/chapters/:number` with `annotations`.
- Produces: `/api/cards/:id` with `traceItems`.

- [ ] **Step 1: Write failing tests for expanded fields in PostgreSQL mode**

Add tests proving `PostgresContentStore.maybe_review_card_for_chapter()` reconstructs `characters`, `relationships`, `places`, `objects`, `literary_texts`, `modern_explanations`, `later_associations`, and `annotations` from `chapter_cards.raw_card`.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run:

```bash
pytest tests/test_postgres_store.py tests/test_web_app.py -q
```

Expected before implementation: failures showing PostgreSQL mode does not preserve expanded fields or PostgreSQL files are missing.

- [ ] **Step 3: Merge PostgreSQL files from `feat/postgres-trace-graph`**

Bring in schema, config, store, migration, seed import, docs, and Makefile targets. Preserve the current branch versions of:

- `ChapterReviewCard`
- `ContentStore.from_paths()`
- `scripts/import_chapter_cards.py`
- `scripts/generate_chapter_cards.py`

- [ ] **Step 4: Implement expanded-field reconstruction**

Update `PostgresContentStore.maybe_review_card_for_chapter()` so `raw_card` is the complete source of expanded fields. Split columns can remain the fallback for summary, plot chain, event IDs, and prompt metadata.

- [ ] **Step 5: Verify Task 1**

Run:

```bash
pytest tests/test_postgres_migration.py tests/test_postgres_store.py tests/test_import_postgres_seed.py tests/test_web_app.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit Task 1**

```bash
git add db hlm_kg scripts tests Makefile requirements.txt docs/postgres_trace_graph.md
git commit -m "feat: integrate postgres content store with chapter cards"
```

---

### Task 2: Add Single-Chapter PostgreSQL Upsert

**Files:**
- Create or modify: `scripts/sync_chapter_card_postgres.py`
- Modify: `scripts/import_postgres_seed.py`
- Modify: `docs/postgres_trace_graph.md`
- Modify: `Makefile`
- Test: `tests/test_sync_chapter_card_postgres.py`
- Test: `tests/test_import_postgres_seed.py`

**Interfaces:**
- Consumes: one checked AppImportJSON object from `generated/chapter_cards_import/NNN.json`.
- Produces: a scoped upsert into `chapter_cards` for the selected chapter.
- Produces: no-op or scoped update behavior for annotations when annotation conversion is not yet evidence-backed.

- [ ] **Step 1: Write failing tests for scoped upsert**

Tests must prove:

- one chapter-card row is converted to the same shape as full seed import;
- the command refuses mismatched `--chapter` and JSON `chapter`;
- missing `DATABASE_URL` returns code `2` without printing the secret;
- expanded fields remain in `raw_card`;
- no unrelated chapter records are built or truncated.

- [ ] **Step 2: Confirm RED**

Run:

```bash
pytest tests/test_sync_chapter_card_postgres.py -q
```

Expected: fails because the sync command/function does not exist.

- [ ] **Step 3: Implement sync command**

Implement an explicit command such as:

```bash
python scripts/sync_chapter_card_postgres.py --chapter 27 --input generated/chapter_cards_import/027.json
```

The command must:

- load `.env` safely through existing helpers;
- validate the selected JSON through the chapter-card import contract;
- upsert only the selected `chapter_cards` row;
- use one database transaction;
- avoid printing the database URL or password.

- [ ] **Step 4: Document command**

Update docs and Makefile with a target such as:

```bash
make sync-chapter-card-postgres CHAPTER=27 INPUT=generated/chapter_cards_import/027.json
```

- [ ] **Step 5: Verify Task 2**

Run:

```bash
pytest tests/test_sync_chapter_card_postgres.py tests/test_import_postgres_seed.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit Task 2**

```bash
git add scripts tests docs Makefile
git commit -m "feat: sync single chapter card to postgres"
```

---

### Task 3: Add Evidence-Pack Audit For Chapter Generation

**Files:**
- Modify: `scripts/generate_chapter_cards.py`
- Modify: `docs/chapter_review_card_pipeline.md`
- Test: `tests/test_generate_chapter_cards.py`

**Interfaces:**
- Consumes: LightRAG `/query/data` raw response.
- Produces: normalized evidence pack for prompt input and optional audit metadata.
- Produces: validation that unsupported `later_associations` remain empty.

- [ ] **Step 1: Write failing tests**

Tests must prove:

- generation normalizes `/query/data` responses before prompt construction;
- prompt uses student-safe names such as “全书关系线索”;
- later associations require supporting evidence in the normalized pack or remain empty;
- generated audit data does not include forbidden student-facing terms in rendered fields.

- [ ] **Step 2: Confirm RED**

Run:

```bash
pytest tests/test_generate_chapter_cards.py -q
```

- [ ] **Step 3: Implement evidence pack construction**

Reuse `normalize_query_data_response()` where possible. Keep raw evidence internal; do not expose implementation terms in Markdown or student-facing JSON fields.

- [ ] **Step 4: Verify Task 3**

Run:

```bash
pytest tests/test_generate_chapter_cards.py tests/test_import_chapter_cards.py -q
```

- [ ] **Step 5: Commit Task 3**

```bash
git add scripts docs tests
git commit -m "feat: audit chapter card evidence packs"
```

---

### Task 4: Final Validation And Issue Updates

**Files:**
- Modify: `.superpowers/sdd/progress.md`
- Modify as needed: docs touched above

**Interfaces:**
- Consumes: results from Tasks 1-3.
- Produces: GitHub issue comments for #31, #32, and #29.

- [ ] **Step 1: Run full verification**

Run:

```bash
pytest -q
python -m hlm_kg.validation_samples
```

- [ ] **Step 2: Check git status**

Run:

```bash
git status --short --branch
```

- [ ] **Step 3: Update issues**

Comment on #31, #32, and #29 with implementation commits, test results, and remaining risks. Do not include secrets or `.env` contents.

- [ ] **Step 4: Commit final docs if needed**

```bash
git add docs .superpowers/sdd/progress.md
git commit -m "docs: record postgres chapter card sync workflow"
```

## Self-Review

- This plan starts from #31 because PostgreSQL integration is a dependency of #32.
- It keeps generated JSON as an artifact rather than replacing it with PostgreSQL.
- It preserves the current expanded chapter-card contract.
- It does not require live LightRAG or PostgreSQL in CI.
- It avoids direct generator-to-database writes until a checked single-chapter artifact exists.

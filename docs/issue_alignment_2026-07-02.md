# 2026-07-02 Issue Alignment

## Purpose

This note aligns the open GitHub issues with the latest product direction:

- PostgreSQL is the primary runtime data store for the V1 reading experience.
- Chapter cards must be generated from the current chapter original text, the versioned prompt, and LightRAG `/query/data` evidence from the full-book graph.
- A single chapter must be regenerable without rebuilding all 120 chapters, and the update path must keep Markdown, per-chapter JSON, combined JSON, and PostgreSQL consistent.
- Student-facing content must not expose internal implementation terms or unsupported LLM-only facts.

No secrets, `.env` values, database URLs, API keys, or passwords belong in this document, issues, PRs, or logs.

## Current Code State

Branch `feat/chapter-card-generator` contains the chapter-card generation and quality-gate work:

- `scripts/generate_chapter_cards.py` reads the chapter text, calls LightRAG `/query/data` through `LightRAGClient.query_data(..., mode="hybrid", only_need_context=True)`, builds the chapter-card prompt, writes Markdown and per-chapter JSON under `generated/`, and writes combined raw JSON.
- `scripts/import_chapter_cards.py` validates and normalizes AppImportJSON into checked combined JSON.
- `ChapterReviewCard`, `ContentStore`, and `/api/chapters/:number` already carry expanded fields:
  - `characters`
  - `relationships`
  - `places`
  - `objects`
  - `literary_texts`
  - `modern_explanations`
  - `later_associations`
  - `annotations`
- The deterministic gate rejects internal student-facing terms and requires expanded fields before writing generated outputs.

Branch `feat/postgres-trace-graph` in `/private/tmp/hlm-postgres-trace-graph` contains PostgreSQL work that is not merged into the chapter-card branch:

- `db/migrations/001_postgres_trace_graph.sql`
- `hlm_kg/postgres_config.py`
- `hlm_kg/postgres_store.py`
- `scripts/migrate_postgres.py`
- `scripts/import_postgres_seed.py`
- `docs/postgres_trace_graph.md`

That branch adds schema, migration, seed import, optional PostgreSQL-backed web store, API annotations, and trace items. However, it was built before the expanded chapter-card schema landed, so its PostgreSQL store reconstructs `ChapterReviewCard` without the expanded fields unless they are read back from `raw_card`.

## Issue Alignment

| Issue | Status | Alignment Decision |
|---|---|---|
| #24 接入 LightRAG `/query/data` 证据召回适配层 | Implemented in the merged evidence pipeline. | Close as completed. Later PostgreSQL and single-chapter sync work should not be tracked here. |
| #25 解析章回来源并归一化 LightRAG 证据 | Implemented in the merged evidence pipeline. | Close as completed. Reuse the adapter in future chapter-card evidence packs. |
| #26 批量生成并导入 120 回章节复习卡 | Partly implemented; original issue text is stale. | Keep open and update. It must cover the current generation contract, output paths, evidence provenance, sample-to-full generation order, and single-chapter file outputs. |
| #27 实现证据约束问答编排与严格拒答 | Minimal strict-answer behavior exists, but full evidence orchestration is not done. | Keep open and update. It should consume PostgreSQL, expanded chapter-card fields, and normalized LightRAG evidence packs before generating/refusing answers. |
| #28 升级章节页和知识面板展示三源证据 | Partly implemented in JSON mode; PostgreSQL trace/annotation UX is not merged. | Keep open and update. It must consume structured annotations, expanded chapter-card fields, and trace items instead of relying on Markdown parsing. |
| #29 建立三源合一验证样例与质量门禁 | Basic validation samples and CI exist. | Keep open and update. It must add PostgreSQL, single-chapter sync, evidence provenance, and no-secrets/no-internal-language checks. |
| #31 用 PostgreSQL 支撑信息卡全书线索与原文标注跳转 | Implemented on a separate branch but not integrated with current chapter-card work. | Keep open. First merge or integrate the branch, then patch it to preserve expanded chapter-card fields and support the final runtime model. |

## Chapter Card Generation Contract

The generation workflow must use all three inputs:

1. Current chapter original text from `book/chapters/*.txt`.
2. Versioned prompt contract from `data/prompts/definitions.json` and `scripts/generate_chapter_cards.py`.
3. Full-book LightRAG evidence from `/query/data`, not LightRAG `/query`.

The generated Markdown is a rich review artifact for human checking and content audit. It is intentionally larger and more complete than JSON.

The generated JSON is a structured application/import artifact. Even after PostgreSQL becomes the runtime store, JSON should remain because it provides:

- deterministic generation output,
- human-review and diffable audit trail,
- seed/import input for PostgreSQL,
- test fixtures for CI,
- a recovery path when a single chapter needs to be regenerated and reviewed before database sync.

The website should not parse Markdown for runtime behavior. It should read structured JSON or PostgreSQL fields.

## Single-Chapter Update Requirement

A future command must support a single chapter update such as:

```bash
python scripts/generate_chapter_cards.py --chapters 27 --overwrite
```

The required behavior is:

- update `generated/chapter_cards_markdown/027.md`;
- update `generated/chapter_cards_import/027.json`;
- merge all per-chapter JSON files into `generated/chapter_review_cards.raw.json`;
- validate and write `generated/chapter_review_cards.checked.json`;
- optionally sync the selected chapter to PostgreSQL in one transaction;
- avoid deleting or rewriting unrelated chapter outputs except the combined JSON files;
- fail before writing runtime data if the generated output violates the quality gate;
- never print secrets or database URLs.

The PostgreSQL sync should be idempotent and scoped:

- upsert the selected chapter row and chapter-card row;
- store the full checked card in `chapter_cards.raw_card`;
- preserve expanded fields when the API reads a chapter card from PostgreSQL;
- update chapter annotations for the selected chapter without truncating other chapters;
- update trace items that can be derived for the selected chapter or entity set without removing unrelated traces;
- refuse to write unsupported later associations that lack evidence provenance.

## Evidence Provenance Gap

Current generation passes raw LightRAG JSON into the prompt and uses deterministic output shape checks. That is useful but not enough to prove every later association came from evidence.

The next implementation should introduce a normalized chapter-card evidence pack:

- use `normalize_query_data_response()` on `/query/data` responses;
- keep `kind`, `title`, `description`, `file_path`, `source_id`, `chunk_id`, `reference_id`, and parsed chapter sources where available;
- pass this evidence pack to the prompt in student-safe language;
- write evidence metadata into the per-chapter JSON under internal provenance fields or a sidecar audit object;
- validate that `later_associations` are empty unless the evidence pack contains a supporting later chapter or relation.

This does not require changing LightRAG extraction. The product code only consumes the evidence API.

## Recommended Development Order

1. Close completed issues #24 and #25.
2. Update #26, #27, #28, #29, and #31 with this alignment.
3. Create a new issue for single-chapter regeneration and Markdown/JSON/PostgreSQL synchronization.
4. Integrate `feat/postgres-trace-graph` with `feat/chapter-card-generator`.
5. Add tests first for expanded fields in PostgreSQL, single-chapter sync, and evidence provenance.
6. Implement scoped upsert/sync.
7. Run `pytest -q` and `python -m hlm_kg.validation_samples`.

## Open Decisions

- Whether PostgreSQL sync should be an opt-in generator flag such as `--sync-postgres`, or a separate command. Recommended: separate command first, because it keeps content generation failures and database write failures easier to isolate.
- Whether generated JSON should be automatically promoted to `data/app/chapter_review_cards.json`. Recommended: no automatic promotion until sample review passes; generated JSON should remain the staging/audit artifact.
- Whether LightRAG retrieval for chapter cards should use only `hybrid` or a fallback sequence. Recommended: start with `hybrid`; add `mix`/`naive` fallback in the single-chapter sync issue only if tests show missing chapter evidence.

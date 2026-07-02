## Background

After PostgreSQL and the expanded chapter-card contract were introduced, chapter-card generation can no longer be treated as a bulk-only Markdown/JSON job.

We need a scoped workflow that can regenerate one chapter and keep all structured artifacts aligned:

- complete Markdown review artifact,
- per-chapter AppImportJSON,
- combined raw/checked JSON,
- PostgreSQL runtime data when enabled.

The workflow must still obey the product evidence rule: generated content must be based on the chapter original text, the versioned prompt, and LightRAG `/query/data` evidence. It must not use LightRAG `/query` as the final answer source or let the LLM invent unsupported later associations.

## Goals

- Support regenerating a selected chapter without regenerating all 120 chapters.
- Keep generated Markdown, per-chapter JSON, combined JSON, and PostgreSQL in sync.
- Preserve JSON as a review/import artifact even when PostgreSQL is the runtime store.
- Add a scoped PostgreSQL upsert path for one chapter card.
- Ensure PostgreSQL reads preserve expanded chapter-card fields:
  - `characters`
  - `relationships`
  - `places`
  - `objects`
  - `literary_texts`
  - `modern_explanations`
  - `later_associations`
  - `annotations`
- Keep database writes idempotent and transactional.
- Never print or commit `.env`, `DATABASE_URL`, API keys, database passwords, or generated secrets.

## Non-goals

- Do not rebuild the LightRAG index.
- Do not add a content management UI.
- Do not make the generator directly parse Markdown for runtime behavior.
- Do not automatically promote unreviewed generated content into student-facing data without passing the deterministic quality gate.
- Do not implement student quiz, answer scoring, or standard-answer workflows.

## Recommended Approach

1. Keep `scripts/generate_chapter_cards.py` as the generator for Markdown and JSON staging artifacts.
2. Add or reuse an import command that validates the selected per-chapter JSON and merges combined JSON.
3. Add a PostgreSQL sync command or function for a selected checked chapter card.
4. Use `chapter_cards.raw_card` as the complete short-term source of truth for expanded fields, while existing split columns remain useful for common reads.
5. Update `PostgresContentStore.maybe_review_card_for_chapter()` to restore expanded fields from `raw_card`.
6. Convert or preserve structured annotations so `/api/chapters/:number` can expose clickable original-text targets without parsing Markdown.
7. Document the workflow as:

```bash
python scripts/generate_chapter_cards.py --chapters 27 --overwrite
python scripts/import_chapter_cards.py generated/chapter_review_cards.raw.json generated/chapter_review_cards.checked.json data/app
python scripts/sync_chapter_card_postgres.py --chapter 27 --input generated/chapter_cards_import/027.json
```

Exact command names can change during implementation, but the behavior must remain scoped to the selected chapter.

## Acceptance Criteria

- [ ] A selected chapter can be regenerated with `--chapters N --overwrite`.
- [ ] Regeneration updates `generated/chapter_cards_markdown/NNN.md`.
- [ ] Regeneration updates `generated/chapter_cards_import/NNN.json`.
- [ ] Regeneration refreshes `generated/chapter_review_cards.raw.json` and `generated/chapter_review_cards.checked.json` without deleting unrelated per-chapter files.
- [ ] Quality gate failure writes only diagnostic failed output and does not update checked JSON or PostgreSQL.
- [ ] The PostgreSQL sync path upserts only the selected chapter-card data and does not truncate unrelated chapters.
- [ ] PostgreSQL mode returns the same expanded `reviewCard` fields as JSON mode for a checked card.
- [ ] `later_associations` remain empty unless the normalized `/query/data` evidence pack contains supporting later-chapter or relation evidence.
- [ ] PostgreSQL annotations are empty or evidence-backed; invalid offsets do not crash the chapter API.
- [ ] Tests do not require live LightRAG or a live PostgreSQL server.
- [ ] No logs, errors, issue comments, docs, or diffs contain secrets.

## Dependencies

- #26 for chapter-card generation and JSON validation.
- #29 for quality gates and validation coverage.
- #31 for PostgreSQL schema/store integration.

## Implementation Branch

`feat/chapter-card-single-sync`

## References

- `docs/issue_alignment_2026-07-02.md`
- `docs/chapter_review_card_pipeline.md`
- `scripts/generate_chapter_cards.py`
- `scripts/import_chapter_cards.py`
- `hlm_kg/content_store.py`
- `hlm_kg/postgres_store.py` after PostgreSQL branch integration

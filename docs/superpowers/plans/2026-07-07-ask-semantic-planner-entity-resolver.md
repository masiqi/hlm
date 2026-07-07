# Ask Semantic Planner Entity Resolver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement issue #39's first production slice: canonical entity resolution for Ask QA, followed by structured question planning and judged evidence integration.

**Architecture:** Keep the current AskEngine behavior working while extracting subject identity into a dedicated `EntityResolver`. The first slice uses local JSON/cache data and deterministic evidence contracts; later slices can add an LLM planner/judge behind the same interfaces.

**Tech Stack:** Python dataclasses, existing `ContentStore` / `PostgresContentStore`, pytest, existing `EvidenceCandidate` and `AskAnswer` domain objects.

## Global Constraints

- Do not commit code unless the user explicitly asks.
- Do not require rerunning LightRAG for the first slice.
- Do not add per-question or per-person hard-coded answer branches.
- Preserve evidence-backed answers and `NO_EVIDENCE` refusal behavior.
- Keep changes compatible with JSON store and PostgreSQL store fallback mode.

---

### Task 1: Entity Resolver Core

**Files:**
- Create: `hlm_kg/entity_resolver.py`
- Test: `tests/test_entity_resolver.py`

**Interfaces:**
- Produces: `CandidateEntity`, `ResolvedEntity`, `EntityResolver.resolve_mention(mention, context_text="") -> ResolvedEntity`
- Consumes: store objects exposing `knowledge_cards` and optionally `entity_graph_payloads_for_names`

- [ ] Write failing tests for canonical and ambiguous aliases:
  - `林黛玉` and `黛玉` resolve to canonical `林黛玉` when `黛玉` appears as a non-person card but `林黛玉` is the person card.
  - `通灵宝玉` resolves as object/expression-like entity, not `贾宝玉`.
  - `宝玉` resolves to `贾宝玉` when context contains person cues like `几岁` / `年纪`; otherwise it reports ambiguity if multiple candidates exist.
- [ ] Run focused tests and verify failure because the module does not exist.
- [ ] Implement dataclasses and resolver indexing from existing store cards.
- [ ] Run focused tests and verify pass.

### Task 2: Question Planner Facade

**Files:**
- Create: `hlm_kg/question_planner.py`
- Test: `tests/test_question_planner.py`

**Interfaces:**
- Produces: `QuestionPlan` with `subjects`, `intent`, `target_property`, `constraints`, `answer_shape`, `required_evidence`.
- Consumes: `EntityResolver`.

- [ ] Write failing tests for:
  - `林黛玉是怎么死的？` -> subject `林黛玉`, target property `death_cause_or_process`, short direct answer shape.
  - `黛玉是怎么死的？` -> same canonical subject.
  - `通灵宝玉是什么？` -> subject `通灵宝玉`, target property `identity_or_definition`, not person `贾宝玉`.
- [ ] Implement a deterministic fallback planner that uses resolver output and a small intent taxonomy.
- [ ] Keep marker lists internal to planner fallback only; AskEngine should consume `QuestionPlan`, not raw string lists.
- [ ] Run focused tests and verify pass.

### Task 3: AskEngine Integration

**Files:**
- Modify: `hlm_kg/ask_engine.py`
- Test: `tests/test_ask_engine.py`, `tests/test_web_app.py`

**Interfaces:**
- Consumes: `QuestionPlanner.plan(question) -> QuestionPlan`
- Produces: existing `AskAnswer`

- [ ] Write failing tests showing `黛玉是怎么死的？` follows the same evidence path as `林黛玉是怎么死的？`.
- [ ] Write failing tests showing `通灵宝玉是什么？` does not use `贾宝玉` evidence.
- [ ] Replace `_question_subject_cards` / `_card_name_aliases` subject extraction with resolver-backed subject terms while preserving existing output shape.
- [ ] Keep age and death focused evidence extraction as fallback evidence judges for this slice.
- [ ] Run focused AskEngine and API tests.

### Task 4: Alias Cache Script

**Files:**
- Create: `scripts/build_entity_aliases.py`
- Modify: `hlm_kg/content_store.py` only if a store accessor is needed.
- Test: `tests/test_build_entity_aliases.py`

**Interfaces:**
- Produces: `data/app/entity_aliases.json` schema with canonical name, type, aliases, ambiguity candidates, and sources.

- [ ] Write failing tests with a minimal data directory.
- [ ] Implement script from local JSON inputs only.
- [ ] Do not require live LightRAG.
- [ ] Run focused script tests.

### Task 5: Verification

**Files:**
- No new production files unless earlier tasks reveal a scoped need.

- [ ] Run focused tests:
  - `pytest tests/test_entity_resolver.py tests/test_question_planner.py tests/test_ask_engine.py -q`
  - `pytest tests/test_web_app.py::test_api_ask_extracts_death_answer_without_returning_relationship_essay -q`
- [ ] Run `git diff --check`.
- [ ] Run full `pytest -q` before final completion claim.
- [ ] Report whether LightRAG regeneration is needed. Default expected result: not needed for first slice.

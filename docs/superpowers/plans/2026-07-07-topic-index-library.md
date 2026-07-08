# Topic Index Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, evidence-backed topic index from existing chapter review cards so `看专题` contains concrete topics instead of five thin seed categories.

**Architecture:** Add pure aggregation logic in `hlm_kg/topic_index.py`, expose it through `scripts/build_topic_index.py`, and keep the existing `Topic`, `Evidence`, `KnowledgeCard`, and `GraphRelation` JSON contracts. The builder removes its own prior generated records by stable `topic-auto` prefixes, preserves manually curated seed records, then appends deterministic generated records.

**Tech Stack:** Python standard library, JSON runtime data under `data/app`, existing `ContentStore`, pytest, Makefile.

## Global Constraints

- Student-facing generated data must use `专题库`, not `题库`.
- Generated facts must be derived from `chapter_review_cards.json` fields and carry chapter provenance.
- Do not use LLM output directly for topic aggregation in this slice.
- Preserve the five topic categories: `人物关系`, `关键事件`, `判词命运`, `意象伏笔`, `可引用事实`.
- Do not expose forbidden student-facing terms: `LightRAG`, `RAG`, `知识图谱`, `向量检索`, `置信度`, `模型分数`, `标准答案`, `题库`, `刷题`, `下一题`, `提交答案`, `批改`.
- Keep `/api/topics` and `/api/topics/<id>` compatible with existing frontend code.

---

### Task 1: Pure Topic Aggregation Module

**Files:**
- Create: `hlm_kg/topic_index.py`
- Create: `tests/test_topic_index.py`

**Interfaces:**
- Consumes: `build_topic_index(review_cards, topics, evidence, knowledge_cards, graph_relations) -> TopicIndexResult`
- Produces: `TopicIndexResult.topics`, `.evidence`, `.knowledge_cards`, `.graph_relations`, `.summary`

- [ ] **Step 1: Write failing tests**

Add focused tests in `tests/test_topic_index.py`:

```python
from hlm_kg.topic_index import build_topic_index


def _review_card(**overrides):
    card = {
        "id": "review-027",
        "chapter": 27,
        "source": {"prompt_name": "hongloumeng_chapter_review_card", "prompt_version": "2026-07-01"},
        "plain_summary": "第二十七回写黛玉葬花与宝钗扑蝶。",
        "plot_chain": ["宝钗扑蝶", "黛玉葬花"],
        "key_events": ["黛玉葬花并吟《葬花吟》"],
        "key_characters": [],
        "current_chapter_foreshadowing_signals": ["落花意象暗示人物命运"],
        "later_association_relation_ids": [],
        "quotable_fact_ids": [],
        "retrieval_tags": [],
        "understanding_focus": ["把黛玉葬花理解为人物心理、诗意表达和命运线索的交汇点。"],
        "characters": [
            {"name": "林黛玉", "actions": ["葬花并吟诗"], "traits": ["敏感"], "importance": "本回情感核心"},
            {"name": "薛宝钗", "actions": ["扑蝶"], "traits": ["机敏"], "importance": "与黛玉形成对照"},
        ],
        "relationships": [
            {
                "source": "林黛玉",
                "type": "情感映照",
                "target": "落花",
                "description": "黛玉借落花寄托身世飘零之感。",
                "chapter_evidence": "黛玉葬花并吟《葬花吟》。",
            }
        ],
        "places": [],
        "objects": [{"name": "落花", "meaning": "身世飘零的意象"}],
        "literary_texts": [{"title": "葬花吟", "quote": "花谢花飞花满天", "explanation": "表现黛玉身世悲感"}],
        "modern_explanations": [],
        "later_associations": [{"topic": "黛玉命运", "description": "葬花与后文命运悲感相关", "source_chapters": [97, 98]}],
        "annotations": [],
    }
    card.update(overrides)
    return card


def test_build_topic_index_generates_concrete_topics_with_resolvable_references():
    result = build_topic_index(
        review_cards=[_review_card()],
        topics=[],
        evidence=[],
        knowledge_cards=[],
        graph_relations=[],
    )

    topic_ids = {topic["id"] for topic in result.topics}
    evidence_ids = {item["id"] for item in result.evidence}
    card_ids = {item["id"] for item in result.knowledge_cards}
    relation_ids = {item["id"] for item in result.graph_relations}

    assert any(topic["category"] == "人物关系" and topic["title"] == "林黛玉" for topic in result.topics)
    assert any(topic["category"] == "关键事件" and "黛玉葬花" in topic["title"] for topic in result.topics)
    assert any(topic["category"] == "判词命运" and "葬花吟" in topic["title"] for topic in result.topics)
    assert any(topic["category"] == "意象伏笔" and "落花" in topic["title"] for topic in result.topics)
    assert any(topic["category"] == "可引用事实" for topic in result.topics)

    for topic in result.topics:
        if topic["id"].startswith("topic-auto-"):
            assert topic["evidence_ids"] or topic["card_ids"] or topic["relation_ids"]
            assert set(topic["evidence_ids"]) <= evidence_ids
            assert set(topic["quotable_fact_ids"]) <= evidence_ids
            assert set(topic["card_ids"]) <= card_ids
            assert set(topic["relation_ids"]) <= relation_ids

    assert topic_ids


def test_build_topic_index_preserves_seed_records_and_is_idempotent():
    seed_topic = {
        "id": "topic-image-foreshadowing",
        "title": "意象伏笔",
        "category": "意象伏笔",
        "description": "围绕物件、花木、诗文和跨章照应组织。",
        "card_ids": [],
        "relation_ids": [],
        "typical_question_patterns": [],
        "quotable_fact_ids": [],
        "evidence_ids": [],
    }
    first = build_topic_index([_review_card()], [seed_topic], [], [], [])
    second = build_topic_index(
        [_review_card()],
        first.topics,
        first.evidence,
        first.knowledge_cards,
        first.graph_relations,
    )

    assert first.topics == second.topics
    assert first.evidence == second.evidence
    assert first.knowledge_cards == second.knowledge_cards
    assert first.graph_relations == second.graph_relations
    assert any(topic["id"] == "topic-image-foreshadowing" for topic in second.topics)


def test_build_topic_index_rejects_forbidden_student_terms():
    result = build_topic_index(
        review_cards=[_review_card(key_events=["这是一个题库入口"])],
        topics=[],
        evidence=[],
        knowledge_cards=[],
        graph_relations=[],
    )

    combined = str(result.topics) + str(result.evidence) + str(result.knowledge_cards) + str(result.graph_relations)
    assert "题库" not in combined
    assert result.summary["skipped_candidates"] >= 1
```

- [ ] **Step 2: Run tests to verify red**

Run: `pytest tests/test_topic_index.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'hlm_kg.topic_index'`.

- [ ] **Step 3: Implement minimal module**

Create `hlm_kg/topic_index.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


FORBIDDEN_STUDENT_TERMS = {"LightRAG", "RAG", "知识图谱", "向量检索", "置信度", "模型分数", "标准答案", "题库", "刷题", "下一题", "提交答案", "批改"}
GENERATED_PREFIXES = ("topic-auto-", "ev-topic-auto-", "card-topic-auto-", "rel-topic-auto-")


@dataclass(frozen=True)
class TopicIndexResult:
    topics: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    knowledge_cards: list[dict[str, Any]]
    graph_relations: list[dict[str, Any]]
    summary: dict[str, Any]


def build_topic_index(
    review_cards: list[dict[str, Any]],
    topics: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    knowledge_cards: list[dict[str, Any]],
    graph_relations: list[dict[str, Any]],
) -> TopicIndexResult:
    # Implementation fills generated records from chapter-card fields, removes old generated records,
    # preserves seed records, and returns deterministically sorted JSON-ready dictionaries.
```

Fill the module with helpers for slugging, forbidden-term filtering, generated-record cleanup, evidence creation, card creation, relation creation, and category-specific extraction.

- [ ] **Step 4: Run tests to verify green**

Run: `pytest tests/test_topic_index.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add hlm_kg/topic_index.py tests/test_topic_index.py
git commit -m "feat: add deterministic topic index builder"
```

### Task 2: CLI and Makefile Integration

**Files:**
- Create: `scripts/build_topic_index.py`
- Modify: `Makefile`
- Test: `tests/test_topic_index.py`

**Interfaces:**
- Consumes: `build_topic_index(...)`
- Produces: CLI command with dry-run default and `--write`

- [ ] **Step 1: Add failing CLI tests**

Append tests in `tests/test_topic_index.py` that create a temporary `data_dir`, invoke `scripts.build_topic_index.main`, and assert dry-run does not write while write mode does.

- [ ] **Step 2: Run focused tests to verify red**

Run: `pytest tests/test_topic_index.py -q`

Expected: FAIL with missing `scripts.build_topic_index`.

- [ ] **Step 3: Implement CLI**

Create `scripts/build_topic_index.py` with `parse_args`, JSON load/write helpers, `main(argv=None)`, and summary printing. Default is dry-run; `--write` writes `topics.json`, `evidence.json`, `knowledge_cards.json`, and `graph_relations.json`.

- [ ] **Step 4: Add Makefile target**

Add `build-topic-index` to `.PHONY`, `help`, and command targets:

```makefile
build-topic-index:
	python scripts/build_topic_index.py --data-dir data/app --review-cards data/app/chapter_review_cards.json --write
```

- [ ] **Step 5: Run focused tests to verify green**

Run: `pytest tests/test_topic_index.py tests/test_github_actions.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/build_topic_index.py Makefile tests/test_topic_index.py
git commit -m "feat: add topic index build command"
```

### Task 3: Generate Runtime Topic Data and Verify Web Contract

**Files:**
- Modify: `data/app/topics.json`
- Modify: `data/app/evidence.json`
- Modify: `data/app/knowledge_cards.json`
- Modify: `data/app/graph_relations.json`
- Modify: `tests/test_content_store.py`
- Modify: `tests/test_web_app.py`

**Interfaces:**
- Consumes: CLI from Task 2.
- Produces: expanded runtime topic library consumed by existing `ContentStore`.

- [ ] **Step 1: Add failing integration expectations**

Update `tests/test_content_store.py` so seed topic coverage expects concrete generated topics and reference integrity:

```python
def test_content_store_exposes_generated_topic_library():
    store = ContentStore.from_paths(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
    )

    generated_topics = [topic for topic in store.topics if topic.id.startswith("topic-auto-")]

    assert len(generated_topics) >= 50
    assert any(topic.category == "判词命运" for topic in generated_topics)
    assert any(topic.title == "林黛玉" for topic in generated_topics)
    assert any("葬花" in topic.title for topic in generated_topics)
```

Update `tests/test_web_app.py` with an API detail smoke test for a generated topic:

```python
def test_api_generated_topic_detail_returns_evidence_backed_content():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )
    topic_id = next(topic.id for topic in context.store.topics if topic.id.startswith("topic-auto-") and topic.evidence_ids)

    status, payload = handle_api_request(context, "GET", f"/api/topics/{topic_id}")

    assert status == 200
    assert payload["topic"]["id"] == topic_id
    assert payload["evidence"]
    assert payload["evidence"][0]["chapter"]
```

- [ ] **Step 2: Run tests to verify red**

Run: `pytest tests/test_content_store.py::test_content_store_exposes_generated_topic_library tests/test_web_app.py::test_api_generated_topic_detail_returns_evidence_backed_content -q`

Expected: FAIL before generated data exists.

- [ ] **Step 3: Generate topic data**

Run:

```bash
python scripts/build_topic_index.py --data-dir data/app --review-cards data/app/chapter_review_cards.json --write
```

Expected: command prints a summary with generated topics by category.

- [ ] **Step 4: Run focused integration tests**

Run: `pytest tests/test_topic_index.py tests/test_content_store.py tests/test_web_app.py tests/test_student_language.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add data/app/topics.json data/app/evidence.json data/app/knowledge_cards.json data/app/graph_relations.json tests/test_content_store.py tests/test_web_app.py
git commit -m "feat: generate evidence backed topic library"
```

### Task 4: Final Verification

**Files:**
- No source changes unless verification reveals a defect.

**Interfaces:**
- Consumes: all prior tasks.
- Produces: issue update and final user-facing status.

- [ ] **Step 1: Run full suite**

Run: `pytest`

Expected: PASS.

- [ ] **Step 2: Run web smoke**

Run:

```bash
python -m hlm_kg.web_app
```

Open the printed URL and verify:

- `看专题` lists many concrete topics.
- A generated topic detail contains evidence.
- A topic evidence button navigates to the related chapter.

- [ ] **Step 3: Update issue**

Comment on issue `#38` with branch, commits, commands run, and any remaining risks.

- [ ] **Step 4: Check git status**

Run: `git status --short --branch`

Expected: branch `feat/topic-index-library` with no unrelated dirty files.

# Hongloumeng Reading Assistant Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the V1 web product for 三源合一阅读支持: 原文, 处理后材料, and 全书图谱 working together through 证据约束问答, 章节证据页, 专题, 知识卡, and 知识面板.

**Architecture:** Keep the first implementation light: Python standard-library HTTP server exposes JSON endpoints and serves static HTML/CSS/JS. Domain logic stays in focused Python modules under `hlm_kg/`, while seed content lives under `data/app/`; the browser consumes only student-facing language and never exposes LightRAG/RAG/知识图谱 implementation terms. This plan intentionally uses deterministic seed data and a graph adapter seam first, so the product can run before the real full-book graph API is wired in.

**Tech Stack:** Python 3.13, standard library `http.server`, `dataclasses`, JSON files, static HTML/CSS/JavaScript, pytest.

---

## Scope Notes

- This plan implements a runnable V1 tracer bullet, not a full production platform.
- Do not add login, user history, scoring, confidence percentages, question-bank flows, generated exercises, or ebook-reader features.
- Do not implement LightRAG graph extraction. The product consumes graph data through a local adapter contract that can later call the LightRAG API.
- Use the language in `CONTEXT.md`. Student-facing UI must use 原文依据, 章节资料, 关系线索, 后文关联, 相关章回. It must not show LightRAG, RAG, 知识图谱, 向量检索, 置信度, 模型分数, 标准答案, 题库, 下一题, 提交答案, or 批改.
- Respect `docs/adr/0001-generate-chapter-review-cards-after-full-book-graph-extraction.md`: 章节复习卡 may include 后文关联 only when backed by full-book graph data.

## File Structure

Create or modify these files:

- Create `hlm_kg/domain.py`: dataclasses and validation helpers for Chapter, ProcessedMaterialSource, ChapterReviewCard, Evidence, KnowledgeCard, GraphRelation, Topic, AskAnswer, AnswerClaim, Refusal, and ContinuationLink.
- Create `hlm_kg/content_store.py`: read-only repository for manifest, chapter text, seed app data, evidence lookup, reference integrity checks, and student-facing DTO assembly.
- Create `hlm_kg/evidence.py`: claim-type evidence sufficiency rules, derived-evidence resolution, source priority, and basic source conflict detection. Mixed-question partial/refusal decisions stay in `hlm_kg/ask_engine.py`.
- Create `hlm_kg/ask_engine.py`: deterministic V1 AskAnswer composer over loaded evidence and graph/knowledge-card matches. No live LLM call in this plan.
- Create `hlm_kg/web_app.py`: standard-library HTTP server, JSON routes, static file serving, CLI entry point.
- Create `static/index.html`: single-page app shell with Home, Ask, Chapter Evidence Page, Topic Browser.
- Create `static/styles.css`: responsive layout, desktop knowledge panel, mobile drawer.
- Create `static/app.js`: client-side router, endpoint calls, rendering, student-facing language guard.
- Create `data/app/chapter_review_cards.json`: minimal seed 章节复习卡 records for representative chapters.
- Create `data/app/knowledge_cards.json`: minimal seed 知识卡 records.
- Create `data/app/graph_relations.json`: minimal seed 图谱关系 / 关系线索 records.
- Create `data/app/topics.json`: five seed 专题 records.
- Create `data/app/common_entries.json`: 常见理解入口 seed config.
- Create `data/app/validation_samples.json`: internal 校准样例-derived validation fixtures.
- Create `tests/test_domain_contracts.py`: schema and validation behavior.
- Create `tests/test_content_store.py`: repository loading and chapter lookup behavior.
- Create `tests/test_evidence.py`: evidence sufficiency, claim-type-specific support rules, derived evidence, and conflict behavior.
- Create `tests/test_ask_engine.py`: deterministic ask behavior and no unsupported claims.
- Create `tests/test_web_app.py`: route-level JSON behavior and static app smoke tests.
- Create `tests/test_student_language.py`: student-facing forbidden language checks in static files and JSON responses.
- Modify `Makefile`: add `web` target and keep existing targets.
- Modify `README.md`: add V1 web app run command.

Recommended seed knowledge objects:

- 第三回 / 林黛玉进贾府: chapter evidence path.
- 第二十七回 / 黛玉葬花 / 《葬花吟》: original-text grounded image and poem path.
- 第五十六回 / 探春理家: event and character-trait path.
- 第八回 / 金锁 / 金玉良缘: object and fate relation path.
- 第三十一回 / 金麒麟 / 后文关联: graph-backed later association path.

---

## Chunk 1: Domain Contracts

### Task 1: Add Domain Contracts

**Files:**
- Create: `hlm_kg/domain.py`
- Test: `tests/test_domain_contracts.py`

- [ ] **Step 1: Write failing tests for required domain contracts**

Add `tests/test_domain_contracts.py`:

```python
import pytest

from hlm_kg.domain import (
    AnswerClaim,
    AnswerSection,
    AskAnswer,
    ChapterReviewCard,
    Evidence,
    KnowledgeCard,
    ProcessedMaterialSource,
    PromptDefinition,
    Refusal,
    Topic,
    validate_answer,
)


def _explicit_evidence(evidence_id: str = "ev-explicit") -> Evidence:
    return Evidence(
        id=evidence_id,
        source_type="original_text",
        chapter=27,
        location="第二十七回",
        quote=None,
        evidence_text="第 27 回黛玉葬花并吟《葬花吟》。",
        entity_ids=["person-lindaiyu"],
        relation_id=None,
        confidence="explicit",
        provenance="book/chapters",
        derived_from_ids=[],
    )


def test_answered_answer_requires_evidence_ids_on_claims():
    answer = AskAnswer(
        id="ask-1",
        question="探春理家体现什么？",
        status="answered",
        short_conclusion=[
            AnswerClaim(
                text="探春理家体现其兴利除弊的管理才干。",
                evidence_ids=[],
                claim_type="event_causality",
            )
        ],
        evidence=[],
        explanation=[],
        quotable_facts=None,
        continuation_links=[],
        refusal=None,
    )

    with pytest.raises(ValueError, match="evidence_ids"):
        validate_answer(answer)


def test_refused_answer_requires_refusal_reason():
    answer = AskAnswer(
        id="ask-2",
        question="请写一篇作文",
        status="refused",
        short_conclusion=[],
        evidence=[],
        explanation=[],
        quotable_facts=None,
        continuation_links=[],
        refusal=None,
    )

    with pytest.raises(ValueError, match="refusal"):
        validate_answer(answer)


def test_weak_evidence_cannot_support_determinate_claim():
    weak = Evidence(
        id="ev-weak",
        source_type="processed_material",
        chapter=27,
        location="章节复习卡",
        quote=None,
        evidence_text="疑似与后文有关。",
        entity_ids=["obj-daiyu"],
        relation_id=None,
        confidence="weak",
        provenance="seed",
        derived_from_ids=[],
    )

    assert weak.can_support_claim is False


def test_explicit_evidence_can_support_claim():
    evidence = Evidence(
        id="ev-27-daiyu",
        source_type="original_text",
        chapter=27,
        location="第二十七回",
        quote="花谢花飞花满天，红消香断有谁怜？",
        evidence_text="第 27 回黛玉葬花并吟《葬花吟》。",
        entity_ids=["person-lindaiyu"],
        relation_id=None,
        confidence="explicit",
        provenance="book/chapters",
        derived_from_ids=[],
    )

    assert evidence.can_support_claim is True


def test_derived_evidence_requires_explicit_dependency_in_answer():
    derived = Evidence(
        id="ev-derived",
        source_type="graph_relation",
        chapter=None,
        location="全书关系线索",
        quote=None,
        evidence_text="葬花与后文黛玉命运构成关系线索。",
        entity_ids=["person-lindaiyu"],
        relation_id="rel-daiyu-burying-flowers-fate",
        confidence="derived",
        provenance="curated",
        derived_from_ids=["ev-explicit"],
    )
    answer = AskAnswer(
        id="ask-3",
        question="黛玉葬花有什么后文关联？",
        status="answered",
        short_conclusion=[
            AnswerClaim(
                text="葬花可作为理解黛玉命运悲感的关系线索。",
                evidence_ids=["ev-derived"],
                claim_type="image_foreshadowing",
            )
        ],
        evidence=[derived],
        explanation=[],
        quotable_facts=None,
        continuation_links=[],
        refusal=None,
    )

    with pytest.raises(ValueError, match="unsupported evidence_ids"):
        validate_answer(answer)


def test_chapter_review_card_records_prompt_source():
    card = ChapterReviewCard(
        id="review-027",
        chapter=27,
        source=ProcessedMaterialSource(
            prompt_name="hongloumeng_chapter_review_card",
            prompt_version="2026-07-01",
            generated_at=None,
        ),
        plain_summary="本回主要写黛玉葬花。",
        plot_chain=["黛玉葬花"],
        key_events=["event-daiyu-burying-flowers"],
        key_characters=["card-lindaiyu"],
        current_chapter_foreshadowing_signals=[],
        later_association_relation_ids=["rel-daiyu-burying-flowers-fate"],
        quotable_fact_ids=["ev-027-daiyu-burying-flowers"],
        retrieval_tags=["第27回"],
        understanding_focus=["意象"],
    )

    assert card.source.prompt_name == "hongloumeng_chapter_review_card"


def test_ask_answer_quotable_facts_are_an_answer_section():
    explicit = _explicit_evidence()
    answer = AskAnswer(
        id="ask-4",
        question="黛玉葬花体现了什么？",
        status="answered",
        short_conclusion=[
            AnswerClaim(
                text="黛玉葬花体现其身世悲感。",
                evidence_ids=["ev-explicit"],
                claim_type="image_foreshadowing",
            )
        ],
        evidence=[explicit],
        explanation=[],
        quotable_facts=AnswerSection(
            title="可引用事实",
            claims=[
                AnswerClaim(
                    text="第 27 回黛玉葬花并吟《葬花吟》。",
                    evidence_ids=["ev-explicit"],
                    claim_type="quotable_fact",
                )
            ],
        ),
        continuation_links=[],
        refusal=None,
    )

    validate_answer(answer)


def test_partial_answer_requires_unsupported_subclaim_refusal():
    explicit = _explicit_evidence()
    answer = AskAnswer(
        id="ask-5",
        question="黛玉葬花体现什么？再说明没有资料的后文细节。",
        status="partial",
        short_conclusion=[
            AnswerClaim(
                text="第 27 回黛玉葬花并吟《葬花吟》。",
                evidence_ids=["ev-explicit"],
                claim_type="quotable_fact",
            )
        ],
        evidence=[explicit],
        explanation=[],
        quotable_facts=None,
        continuation_links=[],
        refusal=None,
    )

    with pytest.raises(ValueError, match="partial"):
        validate_answer(answer)


def test_valid_partial_answer_names_unsupported_subclaim():
    explicit = _explicit_evidence()
    answer = AskAnswer(
        id="ask-6",
        question="黛玉葬花体现什么？再说明没有资料的后文细节。",
        status="partial",
        short_conclusion=[
            AnswerClaim(
                text="第 27 回黛玉葬花并吟《葬花吟》。",
                evidence_ids=["ev-explicit"],
                claim_type="quotable_fact",
            )
        ],
        evidence=[explicit],
        explanation=[],
        quotable_facts=None,
        continuation_links=[],
        refusal=Refusal(
            reason="UNSUPPORTED_SUBCLAIM",
            message="问题中有一部分当前资料不足，未生成确定结论。",
        ),
    )

    validate_answer(answer)


def test_prompt_definition_records_structured_rules():
    prompt = PromptDefinition(
        name="answer_with_evidence",
        version="2026-07-01",
        purpose="基于证据组织问答结果",
        input_schema="AskInput",
        output_schema="AskAnswer",
        evidence_rules=["回答前必须先检索或读取证据"],
        refusal_rules=["证据不足时拒答"],
    )

    assert prompt.output_schema == "AskAnswer"


def test_knowledge_card_type_and_topic_category_are_closed_vocabularies():
    with pytest.raises(ValueError, match="card type"):
        KnowledgeCard(
            id="card-invalid",
            name="无效卡片",
            type="freeform",
            brief="无效",
            text_understanding=[],
            understanding_angles=[],
            graph_relation_ids=[],
            evidence_ids=[],
            related_card_ids=[],
        )

    with pytest.raises(ValueError, match="topic category"):
        Topic(
            id="topic-invalid",
            title="无效专题",
            category="自由发挥",
            description="无效",
            card_ids=[],
            relation_ids=[],
            typical_question_patterns=[],
            quotable_fact_ids=[],
            evidence_ids=[],
        )
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/test_domain_contracts.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'hlm_kg.domain'`.

- [ ] **Step 3: Implement minimal domain contracts**

Create `hlm_kg/domain.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


EvidenceSourceType = Literal["original_text", "processed_material", "knowledge_card", "graph_relation"]
EvidenceConfidence = Literal["explicit", "derived", "weak"]
GraphRelationProvenance = Literal["lightrag", "curated"]
KnowledgeCardType = Literal["person", "event", "judgement", "image", "object", "place", "expression"]
TopicCategory = Literal["人物关系", "关键事件", "判词命运", "意象伏笔", "可引用事实"]
AnswerStatus = Literal["answered", "partial", "refused"]
ClaimType = Literal[
    "identity_relation",
    "plot_summary",
    "judgement_destiny",
    "image_foreshadowing",
    "event_causality",
    "quotable_fact",
]
RefusalReason = Literal[
    "NO_EVIDENCE",
    "AMBIGUOUS_ENTITY",
    "GRAPH_UNAVAILABLE",
    "SOURCE_CONFLICT",
    "OUT_OF_SCOPE",
    "UNSUPPORTED_SUBCLAIM",
]


@dataclass(frozen=True)
class Chapter:
    id: str
    number: int
    title: str
    original_text_path: str
    review_card_id: str | None = None
    primary_entity_ids: list[str] = field(default_factory=list)
    primary_event_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProcessedMaterialSource:
    prompt_name: str
    prompt_version: str
    generated_at: str | None = None


@dataclass(frozen=True)
class Evidence:
    id: str
    source_type: EvidenceSourceType
    chapter: int | None
    location: str | None
    quote: str | None
    evidence_text: str
    entity_ids: list[str]
    relation_id: str | None
    confidence: EvidenceConfidence
    provenance: str
    derived_from_ids: list[str] = field(default_factory=list)

    @property
    def can_support_claim(self) -> bool:
        return self.confidence == "explicit"


@dataclass(frozen=True)
class ChapterReviewCard:
    id: str
    chapter: int
    source: ProcessedMaterialSource
    plain_summary: str
    plot_chain: list[str]
    key_events: list[str]
    key_characters: list[str]
    current_chapter_foreshadowing_signals: list[str]
    later_association_relation_ids: list[str]
    quotable_fact_ids: list[str]
    retrieval_tags: list[str]
    understanding_focus: list[str]


@dataclass(frozen=True)
class GraphRelation:
    id: str
    subject_id: str
    predicate: str
    object_id: str
    chapters: list[int]
    evidence_ids: list[str]
    provenance: GraphRelationProvenance
    description: str


@dataclass(frozen=True)
class KnowledgeCard:
    id: str
    name: str
    type: KnowledgeCardType
    brief: str
    text_understanding: list[str]
    understanding_angles: list[str]
    graph_relation_ids: list[str]
    evidence_ids: list[str]
    related_card_ids: list[str]

    def __post_init__(self) -> None:
        allowed = {"person", "event", "judgement", "image", "object", "place", "expression"}
        if self.type not in allowed:
            raise ValueError(f"invalid card type: {self.type}")


@dataclass(frozen=True)
class Topic:
    id: str
    title: str
    category: TopicCategory
    description: str
    card_ids: list[str]
    relation_ids: list[str]
    typical_question_patterns: list[str]
    quotable_fact_ids: list[str]
    evidence_ids: list[str]

    def __post_init__(self) -> None:
        allowed = {"人物关系", "关键事件", "判词命运", "意象伏笔", "可引用事实"}
        if self.category not in allowed:
            raise ValueError(f"invalid topic category: {self.category}")


@dataclass(frozen=True)
class AnswerClaim:
    text: str
    evidence_ids: list[str]
    claim_type: ClaimType


@dataclass(frozen=True)
class AnswerSection:
    title: str
    claims: list[AnswerClaim]


@dataclass(frozen=True)
class Refusal:
    reason: RefusalReason
    message: str


@dataclass(frozen=True)
class ContinuationLink:
    label: str
    target_type: Literal["chapter", "card", "topic", "relation"]
    target_id: str


@dataclass(frozen=True)
class AskAnswer:
    id: str
    question: str
    status: AnswerStatus
    short_conclusion: list[AnswerClaim]
    evidence: list[Evidence]
    explanation: list[AnswerSection]
    quotable_facts: AnswerSection | None
    continuation_links: list[ContinuationLink]
    refusal: Refusal | None


@dataclass(frozen=True)
class PromptDefinition:
    name: str
    version: str
    purpose: str
    input_schema: str
    output_schema: str
    evidence_rules: list[str]
    refusal_rules: list[str]


def validate_answer(answer: AskAnswer) -> None:
    if answer.status == "refused":
        if answer.refusal is None:
            raise ValueError("refused answers require refusal")
        if answer.short_conclusion or answer.explanation or answer.quotable_facts is not None:
            raise ValueError("refused answers must not contain claims")
        return
    if answer.status == "partial":
        if answer.refusal is None or answer.refusal.reason != "UNSUPPORTED_SUBCLAIM":
            raise ValueError("partial answers require UNSUPPORTED_SUBCLAIM refusal")

    claims = list(answer.short_conclusion)
    for section in answer.explanation:
        claims.extend(section.claims)
    if answer.quotable_facts is not None:
        claims.extend(answer.quotable_facts.claims)
    for claim in claims:
        if not claim.evidence_ids:
            raise ValueError(f"claim requires evidence_ids: {claim.text}")
    if answer.status == "partial" and not claims:
        raise ValueError("partial answers require at least one supported claim")

    supportable_ids = _supportable_evidence_ids(answer.evidence)
    for claim in claims:
        missing = [evidence_id for evidence_id in claim.evidence_ids if evidence_id not in supportable_ids]
        if missing:
            raise ValueError(f"claim references unsupported evidence_ids: {missing}")


def _supportable_evidence_ids(evidence_items: list[Evidence]) -> set[str]:
    explicit_ids = {evidence.id for evidence in evidence_items if evidence.can_support_claim}
    supportable_ids = set(explicit_ids)
    for evidence in evidence_items:
        if evidence.confidence != "derived":
            continue
        if any(source_id in explicit_ids for source_id in evidence.derived_from_ids):
            supportable_ids.add(evidence.id)
    return supportable_ids
```

- [ ] **Step 4: Run contract tests**

Run: `pytest tests/test_domain_contracts.py -q`

Expected: PASS.

- [ ] **Step 5: Run existing tests**

Run: `pytest -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add hlm_kg/domain.py tests/test_domain_contracts.py
git commit -m "feat: add reading assistant domain contracts"
```

## Chunk 2: Seed Content Store

### Task 2: Add Seed Content Files

**Files:**
- Create: `data/app/chapter_review_cards.json`
- Create: `data/app/knowledge_cards.json`
- Create: `data/app/graph_relations.json`
- Create: `data/app/topics.json`
- Create: `data/app/common_entries.json`
- Test: `tests/test_content_store.py`

Note: this task intentionally creates seed files that contain `evidence_ids`, but does not create `data/app/evidence.json` yet. Task 3 adds evidence loading and the cross-file integrity test once evidence objects exist.

- [ ] **Step 1: Write failing tests for seed content loading**

Create `tests/test_content_store.py` with this initial test:

```python
from pathlib import Path

from hlm_kg.content_store import ContentStore


def test_content_store_loads_seed_chapter_review_card():
    store = ContentStore.from_paths(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
    )

    card = store.review_card_for_chapter(27)

    assert card.chapter == 27
    assert card.source.prompt_name == "hongloumeng_chapter_review_card"
    assert card.source.prompt_version == "2026-07-01"
    assert "黛玉葬花" in card.plain_summary
    assert card.later_association_relation_ids


def test_content_store_reads_original_chapter_text():
    store = ContentStore.from_paths(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
    )

    chapter = store.chapter(27)
    text = store.chapter_text(27)

    assert chapter.number == 27
    assert chapter.title
    assert "第二十七回" in text or "第27章" in text


def test_content_store_exposes_seed_knowledge_cards_relations_topics_and_entries():
    store = ContentStore.from_paths(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
    )

    assert any(card.id == "card-lindaiyu" for card in store.knowledge_cards)
    assert any(relation.id == "rel-daiyu-burying-flowers-fate" for relation in store.graph_relations)
    assert {topic.category for topic in store.topics} == {
        "人物关系",
        "关键事件",
        "判词命运",
        "意象伏笔",
        "可引用事实",
    }
    assert any(entry["id"] == "entry-daiyu-burying-flowers" for entry in store.common_entries)
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/test_content_store.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'hlm_kg.content_store'`.

- [ ] **Step 3: Add seed content JSON**

Create `data/app/chapter_review_cards.json`:

```json
[
  {
    "id": "review-027",
    "chapter": 27,
    "source": {
      "prompt_name": "hongloumeng_chapter_review_card",
      "prompt_version": "2026-07-01",
      "generated_at": null
    },
    "plain_summary": "本回主要写宝钗扑蝶、黛玉葬花等情节；黛玉葬花并吟《葬花吟》，集中呈现其身世悲感与洁身自持。",
    "plot_chain": ["宝钗扑蝶", "黛玉葬花", "黛玉吟《葬花吟》"],
    "key_events": ["event-daiyu-burying-flowers"],
    "key_characters": ["card-lindaiyu", "card-xuebaochai"],
    "current_chapter_foreshadowing_signals": ["落花与葬花行为构成黛玉命运悲感的本回信号。"],
    "later_association_relation_ids": ["rel-daiyu-burying-flowers-fate"],
    "quotable_fact_ids": ["ev-027-daiyu-burying-flowers"],
    "retrieval_tags": ["第27回", "黛玉葬花", "葬花吟", "意象伏笔"],
    "understanding_focus": ["人物情感", "意象", "命运伏笔"]
  },
  {
    "id": "review-056",
    "chapter": 56,
    "source": {
      "prompt_name": "hongloumeng_chapter_review_card",
      "prompt_version": "2026-07-01",
      "generated_at": null
    },
    "plain_summary": "本回主要写探春理家，探春通过兴利除弊整顿事务，表现其管理才干和忧患意识。",
    "plot_chain": ["探春代管家务", "整顿大观园事务", "兴利除弊"],
    "key_events": ["event-tanchun-manages-household"],
    "key_characters": ["card-jiatanchun"],
    "current_chapter_foreshadowing_signals": [],
    "later_association_relation_ids": [],
    "quotable_fact_ids": ["ev-056-tanchun-manages-household"],
    "retrieval_tags": ["第56回", "探春理家", "兴利除弊", "人物性格"],
    "understanding_focus": ["人物性格", "家族治理", "事件作用"]
  }
]
```

Create `data/app/knowledge_cards.json`:

```json
[
  {
    "id": "card-lindaiyu",
    "name": "林黛玉",
    "type": "person",
    "brief": "《红楼梦》主要人物，常与才情、敏感、自尊、身世悲感等理解角度相关。",
    "text_understanding": ["第 27 回黛玉葬花并吟《葬花吟》。"],
    "understanding_angles": ["可从身世悲感、洁身自持、落花意象理解黛玉。"],
    "graph_relation_ids": ["rel-daiyu-burying-flowers-fate"],
    "evidence_ids": ["ev-027-daiyu-burying-flowers"],
    "related_card_ids": []
  },
  {
    "id": "card-xuebaochai",
    "name": "薛宝钗",
    "type": "person",
    "brief": "《红楼梦》主要人物，第 27 回涉及宝钗扑蝶。",
    "text_understanding": ["第 27 回宝钗扑蝶。"],
    "understanding_angles": ["可与黛玉葬花并读，观察同回不同人物的情节表现。"],
    "graph_relation_ids": [],
    "evidence_ids": ["ev-027-baochai-butterfly"],
    "related_card_ids": ["card-lindaiyu"]
  },
  {
    "id": "card-jiatanchun",
    "name": "贾探春",
    "type": "person",
    "brief": "贾府三姑娘，探春理家常用于理解其管理才干和兴利除弊意识。",
    "text_understanding": ["第 56 回探春理家，体现她对家族事务的判断和整顿能力。"],
    "understanding_angles": ["可从管理才干、忧患意识、刚决性格理解探春。"],
    "graph_relation_ids": ["rel-tanchun-manages-trait"],
    "evidence_ids": ["ev-056-tanchun-manages-household"],
    "related_card_ids": []
  }
]
```

Create `data/app/graph_relations.json`:

```json
[
  {
    "id": "rel-daiyu-burying-flowers-fate",
    "subject_id": "card-lindaiyu",
    "predicate": "later_association",
    "object_id": "event-daiyu-fate",
    "chapters": [27, 97, 98],
    "evidence_ids": ["ev-027-daiyu-burying-flowers"],
    "provenance": "curated",
    "description": "人工校订关系线索：第 27 回黛玉葬花与《葬花吟》可作为理解黛玉命运悲感的关系线索。"
  },
  {
    "id": "rel-tanchun-manages-trait",
    "subject_id": "card-jiatanchun",
    "predicate": "supports_trait",
    "object_id": "trait-xingli-chubi",
    "chapters": [56],
    "evidence_ids": ["ev-056-tanchun-manages-household"],
    "provenance": "curated",
    "description": "人工校订关系线索：第 56 回探春理家可支撑其兴利除弊、具有管理才干的理解。"
  }
]
```

Create `data/app/topics.json`:

```json
[
  {
    "id": "topic-character-relations",
    "title": "人物关系",
    "category": "人物关系",
    "description": "围绕身份、别称、称谓、亲属、主仆、婚恋和对照关系组织。",
    "card_ids": ["card-lindaiyu", "card-jiatanchun"],
    "relation_ids": [],
    "typical_question_patterns": ["说明人物关系及章回依据"],
    "quotable_fact_ids": [],
    "evidence_ids": []
  },
  {
    "id": "topic-key-events",
    "title": "关键事件",
    "category": "关键事件",
    "description": "围绕事件起因、经过、结果、牵涉人物和章回出处组织。",
    "card_ids": ["card-jiatanchun"],
    "relation_ids": ["rel-tanchun-manages-trait"],
    "typical_question_patterns": ["概括事件并说明人物表现"],
    "quotable_fact_ids": ["ev-056-tanchun-manages-household"],
    "evidence_ids": ["ev-056-tanchun-manages-household"]
  },
  {
    "id": "topic-judgement-destiny",
    "title": "判词命运",
    "category": "判词命运",
    "description": "围绕判词、曲词、花签、灯谜与人物命运组织。",
    "card_ids": [],
    "relation_ids": [],
    "typical_question_patterns": ["说明判词对应人物及命运暗示"],
    "quotable_fact_ids": [],
    "evidence_ids": []
  },
  {
    "id": "topic-image-foreshadowing",
    "title": "意象伏笔",
    "category": "意象伏笔",
    "description": "围绕物件、花木、诗文和跨章照应组织。",
    "card_ids": ["card-lindaiyu"],
    "relation_ids": ["rel-daiyu-burying-flowers-fate"],
    "typical_question_patterns": ["说明意象和后文关联"],
    "quotable_fact_ids": ["ev-027-daiyu-burying-flowers"],
    "evidence_ids": ["ev-027-daiyu-burying-flowers"]
  },
  {
    "id": "topic-quotable-facts",
    "title": "可引用事实",
    "category": "可引用事实",
    "description": "整理短、具体、可定位的事实材料。",
    "card_ids": ["card-lindaiyu", "card-jiatanchun"],
    "relation_ids": ["rel-daiyu-burying-flowers-fate"],
    "typical_question_patterns": ["查找可用于作答的事实依据"],
    "quotable_fact_ids": ["ev-027-daiyu-burying-flowers", "ev-056-tanchun-manages-household"],
    "evidence_ids": ["ev-027-daiyu-burying-flowers", "ev-056-tanchun-manages-household"]
  }
]
```

Create `data/app/common_entries.json`:

```json
[
  {
    "id": "entry-daiyu-burying-flowers",
    "label": "黛玉葬花体现了什么？",
    "target_type": "ask",
    "target": "黛玉葬花体现了什么？"
  },
  {
    "id": "entry-tanchun-manages-household",
    "label": "探春理家体现了什么性格？",
    "target_type": "ask",
    "target": "探春理家体现了什么性格？"
  }
]
```

- [ ] **Step 4: Implement content store loader**

Create `hlm_kg/content_store.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hlm_kg.domain import Chapter, ChapterReviewCard, GraphRelation, KnowledgeCard, ProcessedMaterialSource, Topic


class ContentStore:
    def __init__(
        self,
        *,
        chapters: dict[int, Chapter],
        review_cards: dict[int, ChapterReviewCard],
        knowledge_cards: dict[str, KnowledgeCard],
        graph_relations: dict[str, GraphRelation],
        topics: dict[str, Topic],
        common_entries: list[dict[str, Any]],
    ) -> None:
        self._chapters = chapters
        self._review_cards = review_cards
        self._knowledge_cards = knowledge_cards
        self._graph_relations = graph_relations
        self._topics = topics
        self.common_entries = common_entries

    @classmethod
    def from_paths(cls, manifest_path: Path, data_dir: Path) -> "ContentStore":
        manifest = _read_json(manifest_path)
        chapters = {
            int(item["number"]): Chapter(
                id=f"chapter-{int(item['number']):03d}",
                number=int(item["number"]),
                title=str(item["title"]),
                original_text_path=str(item["file_path"]),
                review_card_id=f"review-{int(item['number']):03d}",
            )
            for item in manifest["chapters"]
        }

        review_cards = {
            int(item["chapter"]): ChapterReviewCard(
                id=str(item["id"]),
                chapter=int(item["chapter"]),
                source=ProcessedMaterialSource(
                    prompt_name=str(item["source"]["prompt_name"]),
                    prompt_version=str(item["source"]["prompt_version"]),
                    generated_at=item["source"].get("generated_at"),
                ),
                plain_summary=str(item["plain_summary"]),
                plot_chain=list(item.get("plot_chain", [])),
                key_events=list(item.get("key_events", [])),
                key_characters=list(item.get("key_characters", [])),
                current_chapter_foreshadowing_signals=list(item.get("current_chapter_foreshadowing_signals", [])),
                later_association_relation_ids=list(item.get("later_association_relation_ids", [])),
                quotable_fact_ids=list(item.get("quotable_fact_ids", [])),
                retrieval_tags=list(item.get("retrieval_tags", [])),
                understanding_focus=list(item.get("understanding_focus", [])),
            )
            for item in _read_json(data_dir / "chapter_review_cards.json")
        }
        knowledge_cards = {
            str(item["id"]): KnowledgeCard(
                id=str(item["id"]),
                name=str(item["name"]),
                type=str(item["type"]),
                brief=str(item["brief"]),
                text_understanding=list(item.get("text_understanding", [])),
                understanding_angles=list(item.get("understanding_angles", [])),
                graph_relation_ids=list(item.get("graph_relation_ids", [])),
                evidence_ids=list(item.get("evidence_ids", [])),
                related_card_ids=list(item.get("related_card_ids", [])),
            )
            for item in _read_json(data_dir / "knowledge_cards.json")
        }
        graph_relations = {
            str(item["id"]): GraphRelation(
                id=str(item["id"]),
                subject_id=str(item["subject_id"]),
                predicate=str(item["predicate"]),
                object_id=str(item["object_id"]),
                chapters=[int(chapter) for chapter in item.get("chapters", [])],
                evidence_ids=list(item.get("evidence_ids", [])),
                provenance=item.get("provenance", "curated"),
                description=str(item["description"]),
            )
            for item in _read_json(data_dir / "graph_relations.json")
        }
        topics = {
            str(item["id"]): Topic(
                id=str(item["id"]),
                title=str(item["title"]),
                category=str(item["category"]),
                description=str(item["description"]),
                card_ids=list(item.get("card_ids", [])),
                relation_ids=list(item.get("relation_ids", [])),
                typical_question_patterns=list(item.get("typical_question_patterns", [])),
                quotable_fact_ids=list(item.get("quotable_fact_ids", [])),
                evidence_ids=list(item.get("evidence_ids", [])),
            )
            for item in _read_json(data_dir / "topics.json")
        }
        common_entries = list(_read_json(data_dir / "common_entries.json"))
        return cls(
            chapters=chapters,
            review_cards=review_cards,
            knowledge_cards=knowledge_cards,
            graph_relations=graph_relations,
            topics=topics,
            common_entries=common_entries,
        )

    def chapter(self, number: int) -> Chapter:
        return self._chapters[number]

    def chapter_text(self, number: int) -> str:
        return Path(self.chapter(number).original_text_path).read_text(encoding="utf-8")

    def review_card_for_chapter(self, number: int) -> ChapterReviewCard:
        return self._review_cards[number]

    @property
    def topics(self) -> list[Topic]:
        return list(self._topics.values())

    @property
    def knowledge_cards(self) -> list[KnowledgeCard]:
        return list(self._knowledge_cards.values())

    @property
    def graph_relations(self) -> list[GraphRelation]:
        return list(self._graph_relations.values())


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
```

- [ ] **Step 5: Run content store tests**

Run: `pytest tests/test_content_store.py -q`

Expected: PASS.

- [ ] **Step 6: Run existing tests**

Run: `pytest -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add data/app tests/test_content_store.py hlm_kg/content_store.py
git commit -m "feat: add reading assistant seed content"
```

## Chunk 3: Evidence Core

### Task 3: Add Evidence Sufficiency Rules

**Files:**
- Create: `hlm_kg/evidence.py`
- Modify: `hlm_kg/content_store.py`
- Test: `tests/test_evidence.py`

- [ ] **Step 1: Write failing tests for evidence rules**

Create `tests/test_evidence.py`:

```python
from hlm_kg.domain import AnswerClaim, Evidence
from hlm_kg.evidence import EvidenceDecision, detect_source_conflict, decide_claim_support, source_priority


def evidence(
    evidence_id: str,
    source_type: str = "original_text",
    chapter: int | None = 27,
    confidence: str = "explicit",
    relation_id: str | None = None,
    derived_from_ids: list[str] | None = None,
    text: str = "第 27 回黛玉葬花并吟《葬花吟》。",
) -> Evidence:
    return Evidence(
        id=evidence_id,
        source_type=source_type,
        chapter=chapter,
        location=f"第 {chapter} 回" if chapter else "全书关系线索",
        quote=None,
        evidence_text=text,
        entity_ids=["card-lindaiyu"],
        relation_id=relation_id,
        confidence=confidence,
        provenance="curated",
        derived_from_ids=derived_from_ids or [],
    )


def test_source_priority_puts_original_text_first():
    assert source_priority("original_text") < source_priority("graph_relation")
    assert source_priority("graph_relation") < source_priority("processed_material")


def test_identity_relation_can_use_one_explicit_source():
    claim = AnswerClaim(
        text="潇湘妃子指林黛玉。",
        evidence_ids=["ev-1"],
        claim_type="identity_relation",
    )

    decision = decide_claim_support(
        claim,
        {"ev-1": evidence("ev-1", source_type="graph_relation", relation_id="rel-alias-lindaiyu")},
    )

    assert decision == EvidenceDecision.SUPPORTED


def test_identity_relation_rejects_processed_material_without_original_or_chaptered_relation():
    claim = AnswerClaim(
        text="潇湘妃子指林黛玉。",
        evidence_ids=["ev-1"],
        claim_type="identity_relation",
    )

    decision = decide_claim_support(claim, {"ev-1": evidence("ev-1", source_type="processed_material")})

    assert decision == EvidenceDecision.UNSUPPORTED


def test_plot_summary_requires_locatable_chapter_material():
    claim = AnswerClaim(
        text="第 27 回写宝钗扑蝶和黛玉葬花。",
        evidence_ids=["ev-1"],
        claim_type="plot_summary",
    )

    decision = decide_claim_support(claim, {"ev-1": evidence("ev-1", source_type="processed_material")})

    assert decision == EvidenceDecision.SUPPORTED


def test_judgement_destiny_rejects_relation_without_original_text():
    claim = AnswerClaim(
        text="葬花可作为理解黛玉命运悲感的关系线索。",
        evidence_ids=["ev-relation"],
        claim_type="judgement_destiny",
    )

    decision = decide_claim_support(
        claim,
        {"ev-relation": evidence("ev-relation", source_type="graph_relation", chapter=None, relation_id="rel-daiyu-fate")},
    )

    assert decision == EvidenceDecision.UNSUPPORTED


def test_judgement_destiny_requires_original_text_and_mapping_relation():
    claim = AnswerClaim(
        text="判词命运解释必须同时有原文和人物映射关系。",
        evidence_ids=["ev-text", "ev-relation"],
        claim_type="judgement_destiny",
    )

    decision = decide_claim_support(
        claim,
        {
            "ev-text": evidence("ev-text", source_type="original_text", chapter=5),
            "ev-relation": evidence("ev-relation", source_type="graph_relation", relation_id="rel-judgement-person"),
        },
    )

    assert decision == EvidenceDecision.SUPPORTED


def test_judgement_destiny_rejects_chapterless_mapping_relation():
    claim = AnswerClaim(
        text="判词命运解释必须有可定位的人物映射关系。",
        evidence_ids=["ev-text", "ev-relation"],
        claim_type="judgement_destiny",
    )

    decision = decide_claim_support(
        claim,
        {
            "ev-text": evidence("ev-text", source_type="original_text", chapter=5),
            "ev-relation": evidence(
                "ev-relation",
                source_type="graph_relation",
                chapter=None,
                relation_id="rel-judgement-person",
            ),
        },
    )

    assert decision == EvidenceDecision.UNSUPPORTED


def test_image_foreshadowing_rejects_single_original_text_evidence():
    claim = AnswerClaim(
        text="葬花和后文黛玉命运有关。",
        evidence_ids=["ev-27"],
        claim_type="image_foreshadowing",
    )

    decision = decide_claim_support(claim, {"ev-27": evidence("ev-27", source_type="original_text")})

    assert decision == EvidenceDecision.UNSUPPORTED


def test_image_foreshadowing_accepts_graph_relation():
    claim = AnswerClaim(
        text="葬花和后文黛玉命运有关。",
        evidence_ids=["ev-relation"],
        claim_type="image_foreshadowing",
    )

    decision = decide_claim_support(
        claim,
        {"ev-relation": evidence("ev-relation", source_type="graph_relation", relation_id="rel-daiyu-fate")},
    )

    assert decision == EvidenceDecision.SUPPORTED


def test_image_foreshadowing_rejects_chapterless_graph_relation():
    claim = AnswerClaim(
        text="葬花和后文黛玉命运有关。",
        evidence_ids=["ev-relation"],
        claim_type="image_foreshadowing",
    )

    decision = decide_claim_support(
        claim,
        {
            "ev-relation": evidence(
                "ev-relation",
                source_type="graph_relation",
                chapter=None,
                relation_id="rel-daiyu-fate",
            )
        },
    )

    assert decision == EvidenceDecision.UNSUPPORTED


def test_image_foreshadowing_accepts_two_distinct_chapter_sources():
    claim = AnswerClaim(
        text="葬花和后文黛玉命运有关。",
        evidence_ids=["ev-27", "ev-98"],
        claim_type="image_foreshadowing",
    )

    decision = decide_claim_support(
        claim,
        {
            "ev-27": evidence("ev-27", source_type="original_text", chapter=27),
            "ev-98": evidence("ev-98", source_type="original_text", chapter=98),
        },
    )

    assert decision == EvidenceDecision.SUPPORTED


def test_event_causality_requires_two_locatable_sources():
    claim = AnswerClaim(
        text="探春整顿事务体现其兴利除弊。",
        evidence_ids=["ev-card"],
        claim_type="event_causality",
    )

    decision = decide_claim_support(claim, {"ev-card": evidence("ev-card", source_type="processed_material")})

    assert decision == EvidenceDecision.UNSUPPORTED


def test_event_causality_rejects_single_graph_relation():
    claim = AnswerClaim(
        text="探春整顿事务体现其兴利除弊。",
        evidence_ids=["ev-relation"],
        claim_type="event_causality",
    )

    decision = decide_claim_support(
        claim,
        {"ev-relation": evidence("ev-relation", source_type="graph_relation", relation_id="rel-tanchun-manages")},
    )

    assert decision == EvidenceDecision.UNSUPPORTED


def test_event_causality_accepts_two_locatable_sources():
    claim = AnswerClaim(
        text="探春整顿事务体现其兴利除弊。",
        evidence_ids=["ev-card", "ev-relation"],
        claim_type="event_causality",
    )

    decision = decide_claim_support(
        claim,
        {
            "ev-card": evidence("ev-card", source_type="processed_material", chapter=56),
            "ev-relation": evidence("ev-relation", source_type="graph_relation", chapter=56, relation_id="rel-tanchun-manages"),
        },
    )

    assert decision == EvidenceDecision.SUPPORTED


def test_quotable_fact_requires_one_explicit_source():
    claim = AnswerClaim(
        text="第 27 回黛玉葬花并吟《葬花吟》。",
        evidence_ids=["ev-27"],
        claim_type="quotable_fact",
    )

    decision = decide_claim_support(claim, {"ev-27": evidence("ev-27", source_type="original_text")})

    assert decision == EvidenceDecision.SUPPORTED


def test_derived_evidence_requires_referenced_explicit_evidence():
    claim = AnswerClaim(
        text="葬花和后文黛玉命运有关。",
        evidence_ids=["ev-derived"],
        claim_type="image_foreshadowing",
    )
    explicit = evidence("ev-27", source_type="original_text", chapter=27)
    derived = evidence(
        "ev-derived",
        source_type="graph_relation",
        chapter=27,
        confidence="derived",
        relation_id="rel-daiyu-fate",
        derived_from_ids=["ev-27"],
    )

    assert decide_claim_support(claim, {"ev-derived": derived}) == EvidenceDecision.UNSUPPORTED
    assert decide_claim_support(claim, {"ev-27": explicit, "ev-derived": derived}) == EvidenceDecision.SUPPORTED


def test_derived_evidence_rejects_knowledge_card_only_dependency():
    claim = AnswerClaim(
        text="葬花和后文黛玉命运有关。",
        evidence_ids=["ev-derived"],
        claim_type="image_foreshadowing",
    )
    explicit_card = evidence("ev-card", source_type="knowledge_card", chapter=27)
    derived = evidence(
        "ev-derived",
        source_type="graph_relation",
        chapter=27,
        confidence="derived",
        relation_id="rel-daiyu-fate",
        derived_from_ids=["ev-card"],
    )

    assert decide_claim_support(claim, {"ev-card": explicit_card, "ev-derived": derived}) == EvidenceDecision.UNSUPPORTED


def test_detect_source_conflict_flags_different_explicit_text_for_same_relation():
    first = evidence("ev-a", relation_id="rel-daiyu-fate", text="葬花指向命运悲感。")
    second = evidence("ev-b", relation_id="rel-daiyu-fate", text="葬花完全没有后文关联。")

    assert detect_source_conflict([first, second]) is True
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/test_evidence.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'hlm_kg.evidence'`.

- [ ] **Step 3: Implement evidence rules**

Create `hlm_kg/evidence.py`:

```python
from __future__ import annotations

from enum import Enum

from hlm_kg.domain import AnswerClaim, Evidence, EvidenceSourceType


class EvidenceDecision(str, Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"


SOURCE_PRIORITIES: dict[EvidenceSourceType, int] = {
    "original_text": 0,
    "graph_relation": 1,
    "processed_material": 2,
    "knowledge_card": 2,
}


def source_priority(source_type: EvidenceSourceType) -> int:
    return SOURCE_PRIORITIES[source_type]


def decide_claim_support(claim: AnswerClaim, evidence_by_id: dict[str, Evidence]) -> EvidenceDecision:
    if not claim.evidence_ids:
        return EvidenceDecision.UNSUPPORTED
    selected = [_resolve_supportable(evidence_id, evidence_by_id) for evidence_id in claim.evidence_ids]
    if any(item is None for item in selected):
        return EvidenceDecision.UNSUPPORTED
    evidence_items = [item for item in selected if item is not None]
    if any(not item.evidence_text.strip() for item in evidence_items):
        return EvidenceDecision.UNSUPPORTED

    if claim.claim_type == "identity_relation":
        has_original_text = any(item.source_type == "original_text" and item.chapter is not None for item in evidence_items)
        return _supported(has_original_text or _has_chaptered_graph_relation(evidence_items))
    if claim.claim_type == "plot_summary":
        return _supported(any(item.chapter is not None and item.source_type in {"original_text", "processed_material"} for item in evidence_items))
    if claim.claim_type == "judgement_destiny":
        has_original_text = any(item.source_type == "original_text" and item.chapter is not None for item in evidence_items)
        return _supported(has_original_text and _has_chaptered_graph_relation(evidence_items))
    if claim.claim_type == "image_foreshadowing":
        return _supported(_has_graph_relation(evidence_items) or _distinct_chapters(evidence_items) >= 2)
    if claim.claim_type == "event_causality":
        locatable_count = sum(1 for item in evidence_items if item.chapter is not None)
        return _supported(locatable_count >= 2)
    if claim.claim_type == "quotable_fact":
        return _supported(any(item.confidence == "explicit" for item in evidence_items))
    return EvidenceDecision.UNSUPPORTED


def _resolve_supportable(evidence_id: str, evidence_by_id: dict[str, Evidence]) -> Evidence | None:
    evidence = evidence_by_id.get(evidence_id)
    if evidence is None or evidence.confidence == "weak":
        return None
    if evidence.confidence == "explicit":
        return evidence
    if evidence.confidence == "derived":
        has_explicit_source = any(
            (source := evidence_by_id.get(source_id)) is not None
            and source.confidence == "explicit"
            and source.source_type in {"original_text", "processed_material", "graph_relation"}
            for source_id in evidence.derived_from_ids
        )
        if has_explicit_source:
            return evidence
    return None


def _has_graph_relation(evidence_items: list[Evidence]) -> bool:
    return any(item.source_type == "graph_relation" and item.relation_id and item.chapter is not None for item in evidence_items)


def _has_chaptered_graph_relation(evidence_items: list[Evidence]) -> bool:
    return any(item.source_type == "graph_relation" and item.relation_id and item.chapter is not None for item in evidence_items)


def _distinct_chapters(evidence_items: list[Evidence]) -> int:
    return len({item.chapter for item in evidence_items if item.chapter is not None})


def _supported(value: bool) -> EvidenceDecision:
    return EvidenceDecision.SUPPORTED if value else EvidenceDecision.UNSUPPORTED


def detect_source_conflict(evidence_items: list[Evidence]) -> bool:
    explicit_by_relation: dict[str, set[str]] = {}
    for item in evidence_items:
        if item.confidence != "explicit" or item.relation_id is None:
            continue
        explicit_by_relation.setdefault(item.relation_id, set()).add(item.evidence_text)
    return any(len(texts) > 1 for texts in explicit_by_relation.values())


def supported_claims(claims: list[AnswerClaim], evidence: list[Evidence]) -> list[AnswerClaim]:
    evidence_by_id = {item.id: item for item in evidence}
    return [
        claim
        for claim in claims
        if decide_claim_support(claim, evidence_by_id) is EvidenceDecision.SUPPORTED
    ]
```

- [ ] **Step 4: Add seed evidence to content store**

Modify `hlm_kg/content_store.py` to read `data/app/evidence.json` and expose `evidence`.

Create `data/app/evidence.json`:

```json
[
  {
    "id": "ev-027-daiyu-burying-flowers",
    "source_type": "original_text",
    "chapter": 27,
    "location": "第二十七回",
    "quote": "花谢花飞花满天，红消香断有谁怜？",
    "evidence_text": "第 27 回黛玉葬花并吟《葬花吟》，可用于理解其身世悲感与洁身自持。",
    "entity_ids": ["card-lindaiyu"],
    "relation_id": "rel-daiyu-burying-flowers-fate",
    "confidence": "explicit",
    "provenance": "book/chapters",
    "derived_from_ids": []
  },
  {
    "id": "ev-rel-daiyu-burying-flowers-fate",
    "source_type": "graph_relation",
    "chapter": 27,
    "location": "关系线索：第二十七回，关联第九十七至九十八回",
    "quote": null,
    "evidence_text": "黛玉葬花与后文黛玉命运悲感之间的关系，来自人工校订关系线索。",
    "entity_ids": ["card-lindaiyu"],
    "relation_id": "rel-daiyu-burying-flowers-fate",
    "confidence": "derived",
    "provenance": "curated",
    "derived_from_ids": ["ev-027-daiyu-burying-flowers"]
  },
  {
    "id": "ev-027-baochai-butterfly",
    "source_type": "original_text",
    "chapter": 27,
    "location": "第二十七回",
    "quote": null,
    "evidence_text": "第 27 回涉及宝钗扑蝶，可与黛玉葬花同回并读。",
    "entity_ids": ["card-xuebaochai"],
    "relation_id": null,
    "confidence": "explicit",
    "provenance": "book/chapters",
    "derived_from_ids": []
  },
  {
    "id": "ev-056-tanchun-manages-household",
    "source_type": "processed_material",
    "chapter": 56,
    "location": "第五十六回章节复习卡",
    "quote": null,
    "evidence_text": "第 56 回探春理家，通过整顿大观园事务体现其兴利除弊的管理才干。",
    "entity_ids": ["card-jiatanchun"],
    "relation_id": null,
    "confidence": "explicit",
    "provenance": "data/app/chapter_review_cards.json",
    "derived_from_ids": []
  },
  {
    "id": "ev-rel-tanchun-manages-trait",
    "source_type": "graph_relation",
    "chapter": 56,
    "location": "关系线索：第五十六回",
    "quote": null,
    "evidence_text": "第 56 回探春理家与兴利除弊、管理才干之间的关系，来自人工校订关系线索。",
    "entity_ids": ["card-jiatanchun"],
    "relation_id": "rel-tanchun-manages-trait",
    "confidence": "derived",
    "provenance": "curated",
    "derived_from_ids": ["ev-056-tanchun-manages-household"]
  }
]
```

Implementation note: keep the store constructor signature focused. Add `evidence_by_id()` and `evidence(evidence_id: str)` methods rather than spreading evidence lookup into unrelated modules.

Modify `hlm_kg/content_store.py`:

```python
from hlm_kg.domain import Chapter, ChapterReviewCard, Evidence, GraphRelation, KnowledgeCard, ProcessedMaterialSource, Topic


class ContentStore:
    def __init__(
        self,
        *,
        chapters: dict[int, Chapter],
        review_cards: dict[int, ChapterReviewCard],
        knowledge_cards: dict[str, KnowledgeCard],
        graph_relations: dict[str, GraphRelation],
        topics: dict[str, Topic],
        common_entries: list[dict[str, Any]],
        evidence: dict[str, Evidence],
    ) -> None:
        self._chapters = chapters
        self._review_cards = review_cards
        self._knowledge_cards = knowledge_cards
        self._graph_relations = graph_relations
        self._topics = topics
        self.common_entries = common_entries
        self._evidence = evidence
```

Inside `from_paths()`, read evidence before returning:

```python
        evidence = {
            str(item["id"]): Evidence(
                id=str(item["id"]),
                source_type=item["source_type"],
                chapter=item.get("chapter"),
                location=item.get("location"),
                quote=item.get("quote"),
                evidence_text=str(item["evidence_text"]),
                entity_ids=list(item.get("entity_ids", [])),
                relation_id=item.get("relation_id"),
                confidence=item["confidence"],
                provenance=str(item["provenance"]),
                derived_from_ids=list(item.get("derived_from_ids", [])),
            )
            for item in _read_json(data_dir / "evidence.json")
        }
```

Pass `evidence=evidence` to `cls(...)`, then add lookup methods:

```python
    def evidence_by_id(self) -> dict[str, Evidence]:
        return dict(self._evidence)

    def evidence(self, evidence_id: str) -> Evidence:
        return self._evidence[evidence_id]
```

Append these tests to `tests/test_content_store.py` after `data/app/evidence.json` is added:

```python
def test_content_store_loads_evidence_lookup():
    store = ContentStore.from_paths(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
    )

    evidence = store.evidence("ev-027-daiyu-burying-flowers")

    assert evidence.source_type == "original_text"
    assert store.evidence_by_id()[evidence.id] == evidence


def test_seed_reference_integrity():
    store = ContentStore.from_paths(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
    )
    card_ids = {card.id for card in store.knowledge_cards}
    relation_ids = {relation.id for relation in store.graph_relations}
    evidence_ids = set(store.evidence_by_id())

    for card in store.knowledge_cards:
        assert set(card.graph_relation_ids) <= relation_ids
        assert set(card.evidence_ids) <= evidence_ids
        assert set(card.related_card_ids) <= card_ids

    for relation in store.graph_relations:
        assert set(relation.evidence_ids) <= evidence_ids

    for topic in store.topics:
        assert set(topic.card_ids) <= card_ids
        assert set(topic.relation_ids) <= relation_ids
        assert set(topic.evidence_ids) <= evidence_ids
        assert set(topic.quotable_fact_ids) <= evidence_ids

    for chapter_number in [27, 56]:
        review_card = store.review_card_for_chapter(chapter_number)
        assert set(review_card.key_characters) <= card_ids
        assert set(review_card.later_association_relation_ids) <= relation_ids
        assert set(review_card.quotable_fact_ids) <= evidence_ids
```

- [ ] **Step 5: Run evidence tests**

Run: `pytest tests/test_evidence.py tests/test_content_store.py -q`

Expected: PASS.

- [ ] **Step 6: Run all tests**

Run: `pytest -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add hlm_kg/evidence.py hlm_kg/content_store.py data/app/evidence.json tests/test_evidence.py tests/test_content_store.py
git commit -m "feat: add evidence sufficiency rules"
```

---

## Chunk 4: Ask Engine and Web Product Paths

### Task 4: Add Deterministic Ask Engine

**Files:**
- Create: `hlm_kg/ask_engine.py`
- Modify: `hlm_kg/content_store.py`
- Test: `tests/test_ask_engine.py`

- [ ] **Step 1: Write failing Ask Engine tests**

Create `tests/test_ask_engine.py`:

```python
from pathlib import Path

from hlm_kg.ask_engine import AskEngine
from hlm_kg.content_store import ContentStore
from hlm_kg.domain import validate_answer


def make_engine() -> AskEngine:
    store = ContentStore.from_paths(Path("book/chapters_manifest.json"), Path("data/app"))
    return AskEngine(store)


def test_ask_engine_answers_supported_daiyu_question():
    answer = make_engine().ask("黛玉葬花体现了什么？")

    validate_answer(answer)
    assert answer.status == "answered"
    assert answer.short_conclusion
    assert any(evidence.chapter == 27 for evidence in answer.evidence)
    assert any(evidence.source_type == "graph_relation" for evidence in answer.evidence)
    assert answer.quotable_facts is not None
    assert any("第 27 回" in claim.text for claim in answer.quotable_facts.claims)


def test_ask_engine_returns_refusal_for_out_of_scope_question():
    answer = make_engine().ask("请帮我写一篇作文")

    validate_answer(answer)
    assert answer.status == "refused"
    assert answer.refusal is not None
    assert answer.refusal.reason == "OUT_OF_SCOPE"


def test_ask_engine_answers_supported_tanchun_question():
    answer = make_engine().ask("探春理家体现了什么性格？")

    validate_answer(answer)
    assert answer.status == "answered"
    assert any(evidence.chapter == 56 for evidence in answer.evidence)
    assert answer.quotable_facts is not None


def test_ask_engine_returns_partial_for_mixed_supported_and_unsupported_question():
    answer = make_engine().ask("黛玉葬花体现了什么？再说明一个没有资料的后文细节")

    validate_answer(answer)
    assert answer.status == "partial"
    assert answer.refusal is not None
    assert answer.refusal.reason == "UNSUPPORTED_SUBCLAIM"
    assert "没有资料的后文细节" in answer.refusal.message
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/test_ask_engine.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'hlm_kg.ask_engine'`.

- [ ] **Step 3: Implement deterministic Ask Engine**

Create `hlm_kg/ask_engine.py`:

```python
from __future__ import annotations

from uuid import uuid4

from hlm_kg.content_store import ContentStore
from hlm_kg.domain import (
    AnswerClaim,
    AnswerSection,
    AskAnswer,
    ContinuationLink,
    Evidence,
    Refusal,
)
from hlm_kg.evidence import supported_claims


OUT_OF_SCOPE_TERMS = ("作文", "现实", "八卦", "数学", "英语")


class AskEngine:
    def __init__(self, store: ContentStore) -> None:
        self.store = store

    def ask(self, question: str) -> AskAnswer:
        if any(term in question for term in OUT_OF_SCOPE_TERMS):
            return self._refuse(question, "OUT_OF_SCOPE", "当前产品只支持《红楼梦》阅读理解相关问题。")

        if "没有资料" in question:
            supported = self._daiyu_answer(question)
            return AskAnswer(
                id=supported.id,
                question=question,
                status="partial",
                short_conclusion=supported.short_conclusion,
                evidence=supported.evidence,
                explanation=supported.explanation,
                quotable_facts=supported.quotable_facts,
                continuation_links=supported.continuation_links,
                refusal=Refusal(
                    reason="UNSUPPORTED_SUBCLAIM",
                    message="“没有资料的后文细节”当前资料不足，未生成确定结论。",
                ),
            )

        if "黛玉" in question or "葬花" in question or "葬花吟" in question:
            return self._daiyu_answer(question)
        if "探春" in question or "理家" in question:
            return self._tanchun_answer(question)

        return self._refuse(question, "NO_EVIDENCE", "当前资料中没有找到足够依据回答这个问题。")

    def _daiyu_answer(self, question: str) -> AskAnswer:
        evidence = [
            self.store.evidence("ev-027-daiyu-burying-flowers"),
            self.store.evidence("ev-rel-daiyu-burying-flowers-fate"),
        ]
        conclusion = AnswerClaim(
            text="黛玉葬花可用于理解她的身世悲感；后文关联需要结合全书关系线索来看。",
            evidence_ids=["ev-rel-daiyu-burying-flowers-fate"],
            claim_type="image_foreshadowing",
        )
        quotable = AnswerClaim(
            text="第 27 回黛玉葬花并吟《葬花吟》，可用于说明她的身世悲感与洁身自持。",
            evidence_ids=["ev-027-daiyu-burying-flowers"],
            claim_type="quotable_fact",
        )
        return self._answer(question, evidence, conclusion, quotable, ContinuationLink("查看第二十七回", "chapter", "27"))

    def _tanchun_answer(self, question: str) -> AskAnswer:
        evidence = [
            self.store.evidence("ev-056-tanchun-manages-household"),
            self.store.evidence("ev-rel-tanchun-manages-trait"),
        ]
        conclusion = AnswerClaim(
            text="探春理家体现她兴利除弊的管理才干和忧患意识。",
            evidence_ids=["ev-056-tanchun-manages-household", "ev-rel-tanchun-manages-trait"],
            claim_type="event_causality",
        )
        quotable = AnswerClaim(
            text="第 56 回探春理家，通过整顿大观园事务体现其兴利除弊的管理才干。",
            evidence_ids=["ev-056-tanchun-manages-household"],
            claim_type="quotable_fact",
        )
        return self._answer(question, evidence, conclusion, quotable, ContinuationLink("查看第五十六回", "chapter", "56"))

    def _answer(
        self,
        question: str,
        evidence: list[Evidence],
        conclusion: AnswerClaim,
        quotable: AnswerClaim,
        link: ContinuationLink,
    ) -> AskAnswer:
        explanation_claim = AnswerClaim(
            text="原文章回材料负责定位事实，关系线索负责说明可支持的理解方向。",
            evidence_ids=conclusion.evidence_ids,
            claim_type=conclusion.claim_type,
        )
        supported = supported_claims([conclusion, quotable, explanation_claim], evidence)
        if len(supported) != 3:
            return self._refuse(question, "NO_EVIDENCE", "当前资料中没有找到足够依据回答这个问题。")
        return AskAnswer(
            id=f"ask-{uuid4()}",
            question=question,
            status="answered",
            short_conclusion=[conclusion],
            evidence=evidence,
            explanation=[AnswerSection(title="为什么", claims=[explanation_claim])],
            quotable_facts=AnswerSection(title="可引用事实", claims=[quotable]),
            continuation_links=[link],
            refusal=None,
        )

    def _refuse(self, question: str, reason: str, message: str) -> AskAnswer:
        return AskAnswer(
            id=f"ask-{uuid4()}",
            question=question,
            status="refused",
            short_conclusion=[],
            evidence=[],
            explanation=[],
            quotable_facts=None,
            continuation_links=[],
            refusal=Refusal(reason=reason, message=message),  # type: ignore[arg-type]
        )
```

- [ ] **Step 4: Run Ask Engine tests**

Run: `pytest tests/test_ask_engine.py -q`

Expected: PASS.

- [ ] **Step 5: Run all tests**

Run: `pytest -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add hlm_kg/ask_engine.py tests/test_ask_engine.py
git commit -m "feat: add evidence constrained ask engine"
```

### Task 5: Add JSON Web Routes

**Files:**
- Create: `hlm_kg/web_app.py`
- Test: `tests/test_web_app.py`
- Modify: `Makefile`

- [ ] **Step 1: Write failing route tests**

Create `tests/test_web_app.py`:

```python
from pathlib import Path

from hlm_kg.web_app import create_app_context, handle_api_request


def test_api_chapter_returns_chapter_evidence_page_payload():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )

    status, payload = handle_api_request(context, "GET", "/api/chapters/27")

    assert status == 200
    assert payload["chapter"]["number"] == 27
    assert "originalText" in payload
    assert "reviewCard" in payload
    assert "knowledgeCards" in payload
    assert "LightRAG" not in str(payload)


def test_api_ask_returns_structured_answer():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )

    status, payload = handle_api_request(context, "POST", "/api/ask", {"question": "黛玉葬花体现了什么？"})

    assert status == 200
    assert payload["status"] == "answered"
    assert payload["evidence"]
    assert "quotableFacts" in payload
    assert payload["quotableFacts"]["title"] == "可引用事实"
    assert payload["quotableFacts"]["claims"]


def test_api_topics_returns_five_categories():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )

    status, payload = handle_api_request(context, "GET", "/api/topics")

    assert status == 200
    assert {topic["category"] for topic in payload["topics"]} == {
        "人物关系",
        "关键事件",
        "判词命运",
        "意象伏笔",
        "可引用事实",
    }
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/test_web_app.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'hlm_kg.web_app'`.

- [ ] **Step 3: Implement JSON serializers and route handler**

Create `hlm_kg/web_app.py` with a pure function seam first:

```python
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from hlm_kg.ask_engine import AskEngine
from hlm_kg.content_store import ContentStore


@dataclass(frozen=True)
class AppContext:
    store: ContentStore
    ask_engine: AskEngine
    static_dir: Path


def create_app_context(manifest_path: Path, data_dir: Path, static_dir: Path) -> AppContext:
    store = ContentStore.from_paths(manifest_path, data_dir)
    return AppContext(store=store, ask_engine=AskEngine(store), static_dir=static_dir)


def handle_api_request(
    context: AppContext,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    parsed_path = urlparse(path).path
    if method == "GET" and parsed_path == "/api/home":
        return 200, {"commonEntries": context.store.common_entries}
    if method == "GET" and parsed_path.startswith("/api/chapters/"):
        number = int(parsed_path.rsplit("/", 1)[1])
        chapter = context.store.chapter(number)
        review_card = context.store.review_card_for_chapter(number)
        knowledge_cards = [context.store.knowledge_card(card_id) for card_id in review_card.key_characters]
        return 200, {
            "chapter": _camel(asdict(chapter)),
            "originalText": context.store.chapter_text(number),
            "reviewCard": _camel(asdict(review_card)),
            "knowledgeCards": [_camel(asdict(card)) for card in knowledge_cards],
        }
    if method == "GET" and parsed_path == "/api/topics":
        return 200, {"topics": [_camel(asdict(topic)) for topic in context.store.topics]}
    if method == "GET" and parsed_path.startswith("/api/cards/"):
        card_id = parsed_path.rsplit("/", 1)[1]
        card = context.store.knowledge_card(card_id)
        return 200, {"card": _camel(asdict(card))}
    if method == "POST" and parsed_path == "/api/ask":
        question = str((body or {}).get("question", ""))
        answer = context.ask_engine.ask(question)
        return 200, _camel(asdict(answer))
    return 404, {"error": "not found"}


def _camel(value: Any) -> Any:
    if isinstance(value, list):
        return [_camel(item) for item in value]
    if isinstance(value, dict):
        return {_camel_key(key): _camel(item) for key, item in value.items()}
    return value


def _camel_key(key: str) -> str:
    head, *tail = key.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail)


def make_handler(context: AppContext) -> type[SimpleHTTPRequestHandler]:
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(context.static_dir), **kwargs)

        def do_GET(self) -> None:
            if self.path.startswith("/api/"):
                self._handle_api("GET")
                return
            if self.path == "/":
                self.path = "/index.html"
            super().do_GET()

        def do_POST(self) -> None:
            if self.path.startswith("/api/"):
                self._handle_api("POST")
                return
            self.send_error(404)

        def _handle_api(self, method: str) -> None:
            body = None
            if method == "POST":
                length = int(self.headers.get("Content-Length", "0"))
                raw_body = self.rfile.read(length).decode("utf-8") if length else "{}"
                body = json.loads(raw_body or "{}")
            status, payload = handle_api_request(context, method, self.path, body)
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def main() -> None:
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )
    server = ThreadingHTTPServer(("127.0.0.1", 8765), make_handler(context))
    print("Serving at http://127.0.0.1:8765")
    server.serve_forever()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Add missing ContentStore card lookup**

Modify `hlm_kg/content_store.py`:

```python
    def knowledge_card(self, card_id: str) -> KnowledgeCard:
        return self._knowledge_cards[card_id]
```

- [ ] **Step 5: Add Makefile web target**

Modify `Makefile`:

```make
.PHONY: help env split-chapters analyze-questions dry-run build-kg lightrag-up lightrag-down test web

help:
	@echo "make web - run the V1 reading assistant web app"

web:
	python -m hlm_kg.web_app
```

If the existing `help` target already prints several lines, add only the `make web` line to that target instead of replacing existing help text.

- [ ] **Step 6: Run route tests**

Run: `pytest tests/test_web_app.py -q`

Expected: PASS.

- [ ] **Step 7: Run all tests**

Run: `pytest -q`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add hlm_kg/web_app.py hlm_kg/content_store.py tests/test_web_app.py Makefile
git commit -m "feat: add reading assistant web routes"
```

### Task 6: Add Static Frontend Shell

**Files:**
- Create: `static/index.html`
- Create: `static/styles.css`
- Create: `static/app.js`
- Test: `tests/test_student_language.py`
- Modify: `README.md`

- [ ] **Step 1: Write failing static UI language tests**

Create `tests/test_student_language.py`:

```python
from pathlib import Path


FORBIDDEN_STUDENT_TERMS = [
    "LightRAG",
    "RAG",
    "知识图谱",
    "向量检索",
    "置信度",
    "模型分数",
    "标准答案",
    "题库",
    "下一题",
    "提交答案",
    "批改",
]


def test_static_student_ui_does_not_expose_forbidden_terms():
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [Path("static/index.html"), Path("static/app.js"), Path("static/styles.css")]
    )

    for term in FORBIDDEN_STUDENT_TERMS:
        assert term not in combined


def test_static_ui_contains_three_entry_points():
    html = Path("static/index.html").read_text(encoding="utf-8")

    assert "问一问" in html
    assert "读章节" in html
    assert "看专题" in html
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/test_student_language.py -q`

Expected: FAIL because static files do not exist.

- [ ] **Step 3: Create static HTML**

Create `static/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>红楼梦阅读助手</title>
    <link rel="stylesheet" href="/styles.css" />
  </head>
  <body>
    <header class="topbar">
      <h1>红楼梦阅读助手</h1>
      <nav aria-label="主导航">
        <button data-view="ask">问一问</button>
        <button data-view="chapters">读章节</button>
        <button data-view="topics">看专题</button>
      </nav>
    </header>
    <main>
      <section id="home" class="view active">
        <form id="ask-form" class="ask-box">
          <label for="question">输入你对《红楼梦》的疑问</label>
          <div class="ask-row">
            <input id="question" name="question" autocomplete="off" />
            <button type="submit">查找依据</button>
          </div>
        </form>
        <section>
          <h2>常见理解入口</h2>
          <div id="common-entries" class="entry-grid"></div>
        </section>
      </section>
      <section id="ask" class="view">
        <h2>问一问</h2>
        <div id="answer"></div>
      </section>
      <section id="chapters" class="view">
        <h2>读章节</h2>
        <div class="chapter-layout">
          <article id="chapter-content"></article>
          <aside id="knowledge-panel" class="knowledge-panel"></aside>
        </div>
      </section>
      <section id="topics" class="view">
        <h2>看专题</h2>
        <div id="topic-list" class="topic-grid"></div>
        <aside id="topic-knowledge-panel" class="knowledge-panel"></aside>
      </section>
    </main>
    <script src="/app.js"></script>
  </body>
</html>
```

- [ ] **Step 4: Create static CSS**

Create `static/styles.css` with responsive constraints:

```css
body {
  margin: 0;
  color: #1f2933;
  background: #f7f5ef;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 16px 24px;
  border-bottom: 1px solid #d8d2c4;
  background: #fffaf0;
}

.topbar h1 {
  margin: 0;
  font-size: 20px;
}

button {
  min-height: 40px;
  border: 1px solid #9d8f72;
  border-radius: 6px;
  background: #fff;
  color: #1f2933;
  cursor: pointer;
}

main {
  max-width: 1180px;
  margin: 0 auto;
  padding: 24px;
}

.view {
  display: none;
}

.view.active {
  display: block;
}

.ask-row {
  display: grid;
  grid-template-columns: 1fr 120px;
  gap: 8px;
}

.ask-row input {
  min-height: 40px;
  border: 1px solid #b8ad98;
  border-radius: 6px;
  padding: 0 12px;
}

.entry-grid,
.topic-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.chapter-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 24px;
}

.knowledge-panel {
  position: sticky;
  top: 16px;
  align-self: start;
  border-left: 3px solid #8a6f3e;
  padding-left: 16px;
}

.source {
  border-left: 3px solid #5f7f71;
  padding-left: 10px;
  color: #425466;
}

@media (max-width: 760px) {
  .topbar {
    display: block;
  }

  .topbar nav {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    margin-top: 12px;
  }

  .ask-row {
    grid-template-columns: 1fr;
  }

  .chapter-layout {
    display: block;
  }

  .knowledge-panel {
    position: static;
    margin-top: 20px;
    border: 1px solid #d8d2c4;
    border-radius: 8px;
    padding: 16px;
    background: #fffaf0;
  }
}
```

- [ ] **Step 5: Create static JavaScript**

Create `static/app.js` with fetch calls and renderers. Keep renderers small:

```javascript
const views = document.querySelectorAll(".view");

function showView(id) {
  views.forEach((view) => view.classList.toggle("active", view.id === id));
}

async function getJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`请求失败：${response.status}`);
  return response.json();
}

function renderAnswer(answer) {
  const container = document.querySelector("#answer");
  if (answer.status === "refused") {
    container.innerHTML = `<h3>当前资料不足</h3><p>${answer.refusal.message}</p>`;
    showView("ask");
    return;
  }
  const claims = answer.shortConclusion.map((claim) => `<li>${claim.text}</li>`).join("");
  const sources = answer.evidence
    .map((evidence) => `<li class="source">第 ${evidence.chapter} 回：${evidence.evidenceText}</li>`)
    .join("");
  const facts = (answer.quotableFacts?.claims || []).map((claim) => `<li>${claim.text}</li>`).join("");
  const partialNote =
    answer.status === "partial" && answer.refusal ? `<h3>未回答部分</h3><p>${answer.refusal.message}</p>` : "";
  container.innerHTML = `
    <h3>${answer.status === "partial" ? "部分回答" : "短结论"}</h3>
    <ul>${claims}</ul>
    ${partialNote}
    <h3>依据</h3>
    <ul>${sources}</ul>
    <h3>可引用事实</h3>
    <ul>${facts}</ul>
  `;
  showView("ask");
}

async function ask(question) {
  const answer = await getJson("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  renderAnswer(answer);
}

async function loadHome() {
  const data = await getJson("/api/home");
  document.querySelector("#common-entries").innerHTML = data.commonEntries
    .map((entry) => `<button data-question="${entry.target}">${entry.label}</button>`)
    .join("");
}

async function loadChapter(number = 27) {
  const data = await getJson(`/api/chapters/${number}`);
  const focusCards = data.knowledgeCards
    .map((card) => `<li><strong>${card.name}</strong>：${card.brief}</li>`)
    .join("");
  const focusAngles = data.reviewCard.understandingFocus.map((item) => `<li>${item}</li>`).join("");
  document.querySelector("#chapter-content").innerHTML = `
    <h3>第 ${data.chapter.number} 回：${data.chapter.title}</h3>
    <section><h4>本回梗概</h4><p>${data.reviewCard.plainSummary}</p></section>
    <section><h4>关键情节</h4><ul>${data.reviewCard.plotChain.map((item) => `<li>${item}</li>`).join("")}</ul></section>
    <section><h4>原文</h4><pre>${data.originalText}</pre></section>
  `;
  document.querySelector("#knowledge-panel").innerHTML = `
    <h3>本回重点</h3>
    <h4>主要人物</h4>
    <ul>${focusCards || "<li>暂无可靠资料</li>"}</ul>
    <h4>理解角度</h4>
    <ul>${focusAngles || "<li>暂无可靠资料</li>"}</ul>
  `;
}

async function loadTopics() {
  const data = await getJson("/api/topics");
  document.querySelector("#topic-list").innerHTML = data.topics
    .map((topic) => `<article><h3>${topic.title}</h3><p>${topic.description}</p></article>`)
    .join("");
}

document.addEventListener("click", (event) => {
  const target = event.target;
  if (target.matches("[data-view]")) {
    showView(target.dataset.view);
    if (target.dataset.view === "chapters") loadChapter();
    if (target.dataset.view === "topics") loadTopics();
  }
  if (target.matches("[data-question]")) {
    ask(target.dataset.question);
  }
});

document.querySelector("#ask-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const question = new FormData(event.currentTarget).get("question");
  ask(String(question || ""));
});

loadHome();
```

- [ ] **Step 6: Update README**

Add:

```markdown
Run the V1 reading assistant web app:

```bash
make web
```

Then open `http://127.0.0.1:8765`.
```

Also implement `hlm_kg.web_app.main()` to default to port `8765`.

- [ ] **Step 7: Run static tests**

Run: `pytest tests/test_student_language.py -q`

Expected: PASS.

- [ ] **Step 8: Run web route and static tests**

Run: `pytest tests/test_web_app.py tests/test_student_language.py -q`

Expected: PASS.

- [ ] **Step 9: Run all tests**

Run: `pytest -q`

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add static README.md hlm_kg/web_app.py tests/test_student_language.py
git commit -m "feat: add reading assistant web UI"
```

---

## Chunk 5: Topics, Knowledge Panel, Validation, and Guardrails

### Task 7: Add Knowledge Card Detail Path

**Files:**
- Modify: `static/app.js`
- Modify: `hlm_kg/web_app.py`
- Test: `tests/test_web_app.py`
- Test: `tests/test_student_language.py`

- [ ] **Step 1: Add failing test for card endpoint detail**

Append to `tests/test_web_app.py`:

```python
def test_api_card_returns_student_facing_knowledge_panel_payload():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )

    status, payload = handle_api_request(context, "GET", "/api/cards/card-lindaiyu")

    assert status == 200
    assert payload["card"]["name"] == "林黛玉"
    assert "textUnderstanding" in payload["card"]
    assert "understandingAngles" in payload["card"]
    assert "graphRelationIds" in payload["card"]
    assert payload["evidence"]
    assert payload["relations"]
    assert "LightRAG" not in str(payload)
```

- [ ] **Step 2: Run the card test**

Run: `pytest tests/test_web_app.py::test_api_card_returns_student_facing_knowledge_panel_payload -q`

Expected: FAIL if `/api/cards/*` is incomplete.

- [ ] **Step 3: Implement card route payload**

Modify the `/api/cards/<id>` branch in `hlm_kg/web_app.py`:

```python
    if method == "GET" and parsed_path.startswith("/api/cards/"):
        card_id = parsed_path.rsplit("/", 1)[1]
        card = context.store.knowledge_card(card_id)
        evidence = [context.store.evidence(evidence_id) for evidence_id in card.evidence_ids]
        relation_by_id = {relation.id: relation for relation in context.store.graph_relations}
        relations = [relation_by_id[relation_id] for relation_id in card.graph_relation_ids]
        return 200, {
            "card": _camel(asdict(card)),
            "evidence": [_camel(asdict(item)) for item in evidence],
            "relations": [_camel(asdict(item)) for item in relations],
        }
```

- [ ] **Step 4: Render clickable knowledge cards in chapter view**

Replace the `loadChapter()` review-card rendering in `static/app.js` so `keyCharacters` become buttons:

```javascript
function renderKnowledgeButtons(cards) {
  return cards
    .map((card) => `<button data-card-id="${card.id}">${card.name}</button>`)
    .join("");
}

async function loadKnowledgeCard(cardId, targetSelector = "#knowledge-panel") {
  const data = await getJson(`/api/cards/${cardId}`);
  const textUnderstanding = data.card.textUnderstanding.map((item) => `<li>${item}</li>`).join("");
  const understandingAngles = data.card.understandingAngles.map((item) => `<li>${item}</li>`).join("");
  const relationClues = data.relations.map((item) => `<li>${item.description}</li>`).join("");
  const sources = data.evidence.map((item) => `<li class="source">第 ${item.chapter} 回：${item.evidenceText}</li>`).join("");
  document.querySelector(targetSelector).innerHTML = `
    <h3>${data.card.name}</h3>
    <h4>文本理解</h4>
    <ul>${textUnderstanding || "<li>暂无可靠资料</li>"}</ul>
    <h4>理解角度</h4>
    <ul>${understandingAngles || "<li>暂无可靠资料</li>"}</ul>
    <h4>关系线索</h4>
    <ul>${relationClues || "<li>暂无可靠资料</li>"}</ul>
    <h4>相关章回</h4>
    <ul>${sources || "<li>暂无可靠资料</li>"}</ul>
  `;
}
```

In `loadChapter()`, add:

```javascript
    <section><h4>本回主要人物</h4><div>${renderKnowledgeButtons(data.knowledgeCards)}</div></section>
```

Add this click branch:

```javascript
  if (target.matches("[data-card-id]")) {
    const panel = target.closest("#topics") ? "#topic-knowledge-panel" : "#knowledge-panel";
    loadKnowledgeCard(target.dataset.cardId, panel);
  }
```

- [ ] **Step 5: Run web and language tests**

Run: `pytest tests/test_web_app.py tests/test_student_language.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add hlm_kg/web_app.py static/app.js tests/test_web_app.py
git commit -m "feat: add knowledge card panel path"
```

### Task 8: Add Topic Browser Detail Path

**Files:**
- Modify: `hlm_kg/web_app.py`
- Modify: `static/index.html`
- Modify: `static/app.js`
- Test: `tests/test_web_app.py`

- [ ] **Step 1: Write failing test for topic detail**

Append to `tests/test_web_app.py`:

```python
def test_api_topic_detail_links_cards_relations_and_quotable_facts():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )

    status, payload = handle_api_request(context, "GET", "/api/topics/topic-image-foreshadowing")

    assert status == 200
    assert payload["topic"]["category"] == "意象伏笔"
    assert payload["topic"]["typicalQuestionPatterns"]
    assert payload["cards"]
    assert payload["relations"]
    assert payload["evidence"]


def test_static_topic_view_has_visible_knowledge_panel_target():
    js = Path("static/app.js").read_text(encoding="utf-8")
    html = Path("static/index.html").read_text(encoding="utf-8")

    assert "topic-knowledge-panel" in html
    assert "loadKnowledgeCard(target.dataset.cardId, panel)" in js
    assert "#topic-knowledge-panel" in js
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
pytest \
  tests/test_web_app.py::test_api_topic_detail_links_cards_relations_and_quotable_facts \
  tests/test_web_app.py::test_static_topic_view_has_visible_knowledge_panel_target \
  -q
```

Expected: FAIL with 404 or missing detail fields.

- [ ] **Step 3: Add ContentStore lookup helpers**

Modify `hlm_kg/content_store.py`:

```python
    def topic(self, topic_id: str) -> Topic:
        return self._topics[topic_id]

    def graph_relation(self, relation_id: str) -> GraphRelation:
        return self._graph_relations[relation_id]
```

- [ ] **Step 4: Implement topic detail route**

Add this branch before the `/api/topics` list branch in `handle_api_request()`:

```python
    if method == "GET" and parsed_path.startswith("/api/topics/"):
        topic_id = parsed_path.rsplit("/", 1)[1]
        topic = context.store.topic(topic_id)
        cards = [context.store.knowledge_card(card_id) for card_id in topic.card_ids]
        relations = [context.store.graph_relation(relation_id) for relation_id in topic.relation_ids]
        evidence = [context.store.evidence(evidence_id) for evidence_id in topic.evidence_ids]
        return 200, {
            "topic": _camel(asdict(topic)),
            "cards": [_camel(asdict(card)) for card in cards],
            "relations": [_camel(asdict(relation)) for relation in relations],
            "evidence": [_camel(asdict(item)) for item in evidence],
        }
```

- [ ] **Step 5: Add topic knowledge panel container**

Modify the `#topics` section in `static/index.html`:

```html
<section id="topics" class="view">
  <h2>看专题</h2>
  <div id="topic-list" class="topic-grid"></div>
  <aside id="topic-knowledge-panel" class="knowledge-panel"></aside>
</section>
```

- [ ] **Step 6: Update frontend topic cards**

Replace `loadTopics()` in `static/app.js`:

```javascript
async function loadTopics() {
  const data = await getJson("/api/topics");
  document.querySelector("#topic-list").innerHTML = data.topics
    .map((topic) => `<article><h3>${topic.title}</h3><p>${topic.description}</p><button data-topic-id="${topic.id}">查看专题</button></article>`)
    .join("");
}

async function loadTopicDetail(topicId) {
  const data = await getJson(`/api/topics/${topicId}`);
  const cards = data.cards.map((card) => `<li><button data-card-id="${card.id}">${card.name}</button></li>`).join("");
  const relations = data.relations.map((relation) => `<li>${relation.description}</li>`).join("");
  const facts = data.evidence.map((item) => `<li class="source">第 ${item.chapter} 回：${item.evidenceText}</li>`).join("");
  const patterns = data.topic.typicalQuestionPatterns.map((item) => `<li>${item}</li>`).join("");
  document.querySelector("#topic-list").innerHTML = `
    <article>
      <h3>${data.topic.title}</h3>
      <p>${data.topic.description}</p>
      <h4>核心知识卡</h4>
      <ul>${cards || "<li>暂无可靠资料</li>"}</ul>
      <h4>关系线索</h4>
      <ul>${relations || "<li>暂无可靠资料</li>"}</ul>
      <h4>典型问法</h4>
      <ul>${patterns || "<li>暂无可靠资料</li>"}</ul>
      <h4>可引用事实</h4>
      <ul>${facts || "<li>暂无可靠资料</li>"}</ul>
    </article>
  `;
  document.querySelector("#topic-knowledge-panel").innerHTML = "";
}
```

Add this click branch:

```javascript
  if (target.matches("[data-topic-id]")) {
    loadTopicDetail(target.dataset.topicId);
  }
```

- [ ] **Step 7: Run tests**

Run: `pytest tests/test_web_app.py tests/test_student_language.py -q`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add hlm_kg/web_app.py hlm_kg/content_store.py static/index.html static/app.js tests/test_web_app.py
git commit -m "feat: add topic detail path"
```

### Task 9: Add Internal Validation Samples

**Files:**
- Create: `data/app/validation_samples.json`
- Create: `hlm_kg/validation_samples.py`
- Test: `tests/test_validation_samples.py`

- [ ] **Step 1: Write failing validation sample tests**

Create `tests/test_validation_samples.py`:

```python
from pathlib import Path

from hlm_kg.validation_samples import load_validation_samples, sample_categories


def test_validation_samples_cover_required_categories():
    samples = load_validation_samples(Path("data/app/validation_samples.json"))

    assert 20 <= len(samples) <= 40
    assert sample_categories(samples) == {
        "人物关系与身份别称",
        "章回情节与内容概括",
        "比较鉴赏与论述",
        "诗词判词与人物命运",
        "主题意象与象征",
        "事件因果与伏笔照应",
        "制度礼俗与文化常识",
    }


def test_validation_samples_do_not_require_standard_answers():
    samples = load_validation_samples(Path("data/app/validation_samples.json"))

    for sample in samples:
        assert "standard_answer" not in sample
        assert "answer" not in sample
        assert "score" not in sample
        assert "expected_evidence_types" in sample
        assert "expected_objects" in sample
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/test_validation_samples.py -q`

Expected: FAIL with missing module/file.

- [ ] **Step 3: Add validation sample file**

Create 21 internal validation samples in `data/app/validation_samples.json`:

```json
[
  {
    "id": "sample-alias",
    "category": "人物关系与身份别称",
    "question": "潇湘妃子指的是谁？",
    "expected_objects": ["林黛玉"],
    "expected_chapters": [37],
    "expected_evidence_types": ["graph_relation", "processed_material"],
    "should_refuse": false,
    "quality_notes": "必须说明别称与人物对应，不能作为题库展示。"
  },
  {
    "id": "sample-kinship",
    "category": "人物关系与身份别称",
    "question": "贾宝玉和林黛玉是什么亲属关系？",
    "expected_objects": ["贾宝玉", "林黛玉", "贾府"],
    "expected_chapters": [3],
    "expected_evidence_types": ["original_text", "graph_relation"],
    "should_refuse": false,
    "quality_notes": "需要说明亲属关系和章回依据。"
  },
  {
    "id": "sample-servant-role",
    "category": "人物关系与身份别称",
    "question": "袭人与宝玉的主仆关系如何影响人物表现？",
    "expected_objects": ["袭人", "贾宝玉"],
    "expected_chapters": [],
    "expected_evidence_types": ["processed_material", "graph_relation"],
    "should_refuse": false,
    "quality_notes": "需要具体情节支撑，不能只写身份标签。"
  },
  {
    "id": "sample-plot",
    "category": "章回情节与内容概括",
    "question": "第三回主要写了什么？",
    "expected_objects": ["林黛玉进贾府"],
    "expected_chapters": [3],
    "expected_evidence_types": ["original_text", "processed_material"],
    "should_refuse": false,
    "quality_notes": "可用章节复习卡支撑情节概括。"
  },
  {
    "id": "sample-event-order",
    "category": "章回情节与内容概括",
    "question": "刘姥姥进贾府相关情节应如何按章回定位？",
    "expected_objects": ["刘姥姥进贾府"],
    "expected_chapters": [],
    "expected_evidence_types": ["processed_material", "graph_relation"],
    "should_refuse": false,
    "quality_notes": "需要给出相关章回和事件顺序。"
  },
  {
    "id": "sample-chapter-summary",
    "category": "章回情节与内容概括",
    "question": "第 56 回探春理家主要写了什么？",
    "expected_objects": ["探春理家", "贾探春"],
    "expected_chapters": [56],
    "expected_evidence_types": ["processed_material", "original_text"],
    "should_refuse": false,
    "quality_notes": "需区分情节概括和人物评价。"
  },
  {
    "id": "sample-compare",
    "category": "比较鉴赏与论述",
    "question": "黛玉和宝钗的形象有什么不同？",
    "expected_objects": ["林黛玉", "薛宝钗"],
    "expected_chapters": [],
    "expected_evidence_types": ["processed_material", "graph_relation"],
    "should_refuse": false,
    "quality_notes": "需要具体事实，不能输出套话。"
  },
  {
    "id": "sample-character-view",
    "category": "比较鉴赏与论述",
    "question": "如何评价王熙凤既能干又弄权的复杂性？",
    "expected_objects": ["王熙凤"],
    "expected_chapters": [],
    "expected_evidence_types": ["processed_material", "graph_relation"],
    "should_refuse": false,
    "quality_notes": "需要正反两类事实，不能单面定性。"
  },
  {
    "id": "sample-argument-evidence",
    "category": "比较鉴赏与论述",
    "question": "用具体情节说明探春的管理才干。",
    "expected_objects": ["贾探春", "探春理家"],
    "expected_chapters": [56],
    "expected_evidence_types": ["processed_material", "graph_relation"],
    "should_refuse": false,
    "quality_notes": "输出事实依据，不提供模板化论述。"
  },
  {
    "id": "sample-judgement",
    "category": "诗词判词与人物命运",
    "question": "金陵十二钗判词如何对应人物命运？",
    "expected_objects": ["金陵十二钗判词"],
    "expected_chapters": [5],
    "expected_evidence_types": ["original_text", "graph_relation"],
    "should_refuse": false,
    "quality_notes": "需要判词原文或章回定位。"
  },
  {
    "id": "sample-flower-sign",
    "category": "诗词判词与人物命运",
    "question": "花签如何对应人物命运？",
    "expected_objects": ["花签"],
    "expected_chapters": [],
    "expected_evidence_types": ["original_text", "graph_relation"],
    "should_refuse": false,
    "quality_notes": "需要花签文本、人物映射和章回来源。"
  },
  {
    "id": "sample-poem-person",
    "category": "诗词判词与人物命运",
    "question": "《葬花吟》如何体现黛玉的身世悲感？",
    "expected_objects": ["《葬花吟》", "林黛玉"],
    "expected_chapters": [27],
    "expected_evidence_types": ["original_text", "processed_material"],
    "should_refuse": false,
    "quality_notes": "需要诗文出处和具体解释。"
  },
  {
    "id": "sample-image",
    "category": "主题意象与象征",
    "question": "黛玉葬花中的落花意象有什么作用？",
    "expected_objects": ["黛玉葬花", "《葬花吟》"],
    "expected_chapters": [27],
    "expected_evidence_types": ["original_text", "processed_material"],
    "should_refuse": false,
    "quality_notes": "需要章回定位和具体说明。"
  },
  {
    "id": "sample-object-symbol",
    "category": "主题意象与象征",
    "question": "通灵宝玉在人物关系中有什么作用？",
    "expected_objects": ["通灵宝玉", "贾宝玉"],
    "expected_chapters": [],
    "expected_evidence_types": ["original_text", "graph_relation"],
    "should_refuse": false,
    "quality_notes": "需要区分物件事实和象征解释。"
  },
  {
    "id": "sample-space-symbol",
    "category": "主题意象与象征",
    "question": "潇湘馆如何烘托林黛玉的气质？",
    "expected_objects": ["潇湘馆", "林黛玉"],
    "expected_chapters": [],
    "expected_evidence_types": ["processed_material", "graph_relation"],
    "should_refuse": false,
    "quality_notes": "需要地点、人物和环境描写依据。"
  },
  {
    "id": "sample-foreshadowing",
    "category": "事件因果与伏笔照应",
    "question": "金麒麟如何形成后文关联？",
    "expected_objects": ["金麒麟"],
    "expected_chapters": [31],
    "expected_evidence_types": ["graph_relation"],
    "should_refuse": false,
    "quality_notes": "不能由单回摘要推断后文。"
  },
  {
    "id": "sample-causality",
    "category": "事件因果与伏笔照应",
    "question": "探春理家为什么能体现贾府治理问题？",
    "expected_objects": ["探春理家", "贾府"],
    "expected_chapters": [56],
    "expected_evidence_types": ["processed_material", "graph_relation"],
    "should_refuse": false,
    "quality_notes": "事件因果需要至少两个可定位环节。"
  },
  {
    "id": "sample-later-link",
    "category": "事件因果与伏笔照应",
    "question": "黛玉葬花和后文命运之间有什么关联？",
    "expected_objects": ["黛玉葬花", "林黛玉"],
    "expected_chapters": [27],
    "expected_evidence_types": ["graph_relation", "original_text"],
    "should_refuse": false,
    "quality_notes": "后文关联必须来自全书关系线索。"
  },
  {
    "id": "sample-custom",
    "category": "制度礼俗与文化常识",
    "question": "贾府称谓关系如何帮助理解人物身份？",
    "expected_objects": ["贾府"],
    "expected_chapters": [],
    "expected_evidence_types": ["graph_relation", "processed_material"],
    "should_refuse": false,
    "quality_notes": "需要具体称谓和身份关系。"
  },
  {
    "id": "sample-ritual",
    "category": "制度礼俗与文化常识",
    "question": "贾府宴饮礼俗如何体现人物身份秩序？",
    "expected_objects": ["贾府"],
    "expected_chapters": [],
    "expected_evidence_types": ["original_text", "processed_material"],
    "should_refuse": false,
    "quality_notes": "需要具体场景，不做泛文化解释。"
  },
  {
    "id": "sample-title-custom",
    "category": "制度礼俗与文化常识",
    "question": "人物称谓变化如何帮助判断亲疏和辈分？",
    "expected_objects": ["称谓关系"],
    "expected_chapters": [],
    "expected_evidence_types": ["graph_relation", "processed_material"],
    "should_refuse": false,
    "quality_notes": "需要称谓、人物和关系三者同时出现。"
  }
]
```

- [ ] **Step 4: Implement validation sample loader**

Create `hlm_kg/validation_samples.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_validation_samples(path: Path) -> list[dict[str, Any]]:
    samples = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(samples, list):
        raise ValueError("validation samples must be a list")
    return samples


def sample_categories(samples: list[dict[str, Any]]) -> set[str]:
    return {str(sample["category"]) for sample in samples}
```

- [ ] **Step 5: Run validation tests**

Run: `pytest tests/test_validation_samples.py -q`

Expected: PASS.

- [ ] **Step 6: Run all tests**

Run: `pytest -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add data/app/validation_samples.json hlm_kg/validation_samples.py tests/test_validation_samples.py
git commit -m "test: add reading assistant validation samples"
```

### Task 10: Add Final Guardrail Tests and Manual Smoke Instructions

**Files:**
- Modify: `tests/test_student_language.py`
- Modify: `README.md`

- [ ] **Step 1: Expand forbidden UI language tests**

Update `tests/test_student_language.py`:

```python
def test_static_ui_has_no_account_or_history_features():
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [Path("static/index.html"), Path("static/app.js"), Path("static/styles.css")]
    )

    for term in ["登录", "注册", "个人历史", "收藏", "学习档案", "阅读进度", "书架", "评分"]:
        assert term not in combined
```

- [ ] **Step 2: Run guardrail test**

Run: `pytest tests/test_student_language.py -q`

Expected: PASS. If it fails, remove the forbidden student-facing language or rewrite it using approved domain terms.

- [ ] **Step 3: Add README smoke test instructions**

Add:

```markdown
Smoke test the web app:

1. Run `make web`.
2. Open `http://127.0.0.1:8765`.
3. Ask `黛玉葬花体现了什么？`; verify the answer shows a short conclusion, source, and可引用事实.
4. Ask `请帮我写一篇作文`; verify the app refuses because the product only supports 《红楼梦》阅读理解.
5. Open `读章节`; verify chapter 27 shows original text and chapter review material.
6. Open `看专题`; verify the five topic categories appear.
7. Open the `意象伏笔` topic, click `林黛玉`, and verify the visible panel shows 文本理解、理解角度、关系线索、相关章回.
8. Resize below 760px width; verify the knowledge panel remains usable.
```

- [ ] **Step 4: Run full verification**

Run: `pytest -q`

Expected: PASS.

- [ ] **Step 5: Optional local smoke server**

Run: `make web`

Expected: terminal prints `Serving at http://127.0.0.1:8765`.

Open in browser manually and follow README smoke steps. Stop server with `Ctrl+C`.

- [ ] **Step 6: Commit**

```bash
git add tests/test_student_language.py README.md
git commit -m "test: add reading assistant guardrails"
```

## Final Verification

- [ ] Run all tests:

```bash
pytest -q
```

Expected: all tests pass.

- [ ] Run the web app:

```bash
make web
```

Expected: server starts on `http://127.0.0.1:8765`.

- [ ] Manually verify:
  - Home has 问一问, 读章节, 看专题.
  - 常见理解入口 does not look like a题库.
  - Asking `黛玉葬花体现了什么？` returns answered with chapter source and可引用事实.
  - Asking `请帮我写一篇作文` returns refused.
  - 章节证据页 shows original text and chapter review material.
  - 知识面板 displays 文本理解, 理解角度, 关系线索.
  - 专题 shows 人物关系, 关键事件, 判词命运, 意象伏笔, 可引用事实.
  - Topic detail lets the user click a knowledge card and see 文本理解, 理解角度, 关系线索, and 相关章回 in the visible topic panel.
  - Student-facing UI does not show LightRAG, RAG, 知识图谱, 置信度, 模型分数, 标准答案, 下一题, 提交答案, 批改, 评分, 登录, 收藏, 个人历史, 书架, or 阅读进度.

- [ ] Commit any final README or smoke-test fixes.

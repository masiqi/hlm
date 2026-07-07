# Evidence-Backed Topic Index Design

## Purpose

`看专题` should become a real `专题库`: a browsable set of evidence-backed reading perspectives for 《红楼梦》. It must not become a practice-question `题库`, a popularity list, or an encyclopedia category dump.

The current app has only five thin seed topics in `data/app/topics.json`. The repository already contains richer structured source material in `data/app/chapter_review_cards.json`, including 120 chapter cards with characters, relationships, key events, objects, places, literary texts, understanding focus, current-chapter foreshadowing signals, and later associations. The topic library should be built deterministically from those existing structured materials.

## User Outcome

Students should open `看专题`, choose a familiar category such as `人物关系` or `意象伏笔`, and find many concrete topics under that category. Each topic should expose concise, chapter-locatable evidence and let the student jump back to the relevant chapter evidence page.

Examples of concrete topics:

- `林黛玉`
- `贾宝玉`
- `宝黛钗关系`
- `黛玉葬花`
- `宝钗扑蝶`
- `探春理家`
- `太虚幻境`
- `花`
- `梦`
- `玉`
- `金陵十二钗判词`
- `人物关系出处`

## Terminology

- `专题库`: the generated collection of evidence-backed topics.
- `专题分类`: one of the existing five category labels: `人物关系`, `关键事件`, `判词命运`, `意象伏笔`, `可引用事实`.
- `具体专题`: an individual topic under a category, such as `黛玉葬花`.
- `专题证据`: a generated `Evidence` record derived from a chapter review card field and carrying chapter provenance.
- `专题关系`: a generated `GraphRelation` record derived from a chapter review card relationship or later association.
- `专题知识卡`: a generated or reused `KnowledgeCard` record used by topic detail pages.

Student-facing UI and data must not call this a `题库`.

## Scope

### In Scope

- Add a deterministic topic-index builder.
- Read existing runtime JSON under `data/app`.
- Generate concrete topic records from `chapter_review_cards.json`.
- Generate or extend evidence, relation, and knowledge-card records needed by those topics.
- Keep all generated IDs stable.
- Add tests for builder output, reference integrity, student-facing language, and API payloads.
- Add a Makefile target for rebuilding the topic index.
- Keep the existing `/api/topics` and `/api/topics/<id>` contracts usable.

### Out of Scope

- Using an LLM to generate final topic facts.
- Building a student-facing practice-question feature.
- Requiring PostgreSQL to build the topic index.
- Rewriting the whole topic browser UI in this slice.
- Inferring unsupported claims from model memory or unsourced interpretation.

## Architecture

Create a focused Python module and CLI script:

- `hlm_kg/topic_index.py`: pure aggregation logic and data helpers.
- `scripts/build_topic_index.py`: command-line wrapper that reads/writes files.
- `tests/test_topic_index.py`: focused unit tests for aggregation and integrity.

The builder reads:

- `data/app/chapter_review_cards.json`
- `data/app/topics.json`
- `data/app/evidence.json`
- `data/app/knowledge_cards.json`
- `data/app/graph_relations.json`

The builder writes:

- `data/app/topics.json`
- `data/app/evidence.json`
- `data/app/knowledge_cards.json`
- `data/app/graph_relations.json`

The implementation should be idempotent. Running the command twice should produce the same JSON output.

## Data Model Strategy

The existing `Topic` contract remains:

```ts
type Topic = {
  id: string
  title: string
  category: "人物关系" | "关键事件" | "判词命运" | "意象伏笔" | "可引用事实"
  description: string
  cardIds: string[]
  relationIds: string[]
  typicalQuestionPatterns: string[]
  quotableFactIds: string[]
  evidenceIds: string[]
}
```

This avoids a broad API rewrite. Concrete topics are represented as additional `Topic` records whose `category` is one of the five existing categories.

Generated topic IDs use stable slugs:

- `topic-character-lindaiyu`
- `topic-event-ch027-daiyu-burying-flowers`
- `topic-image-flower`
- `topic-destiny-taixu-huanjing`
- `topic-fact-character-lindaiyu`

Generated evidence IDs use stable chapter and source-field provenance:

- `ev-topic-ch027-character-lindaiyu`
- `ev-topic-ch027-event-001`
- `ev-topic-ch027-image-flower`
- `ev-topic-ch005-destiny-taixu-huanjing`

Generated relation IDs use stable endpoint and chapter provenance:

- `rel-topic-ch027-lindaiyu-luohua`
- `rel-topic-ch056-jiatanchun-zhaoyiniang`

## Extraction Rules

### 人物关系

Use:

- `characters[].name`
- `characters[].aliases`
- `characters[].actions`
- `characters[].traits`
- `characters[].importance`
- `relationships[].source`
- `relationships[].type`
- `relationships[].target`
- `relationships[].description`
- `relationships[].chapter_evidence`

Generate:

- person-centered topics for recurring or important characters;
- relationship topics for concrete source/type/target rows;
- evidence records from character descriptions and relationship evidence;
- relation records when source and target are both present.

### 关键事件

Use:

- `key_events[]`
- high-value `plot_chain[]` entries;
- `understanding_focus[]` when it clearly names an event.

Generate:

- chapter-scoped event topics for high-signal events;
- evidence records from event text;
- typical question patterns such as `概括事件并说明人物表现`.

Events may remain chapter-scoped in the first version. Cross-chapter event merging is not required.

### 判词命运

Use:

- `literary_texts[]`;
- `modern_explanations[]`;
- `later_associations[]` whose topic or description mentions destiny, fate, judgement, poem, song, flower lot, dream, or `太虚幻境`;
- chapter 5 and chapter 63 material when structured fields support it.

Generate:

- topics for judgement/destiny-related literary texts and fate signals;
- evidence records with chapter provenance;
- relation records only when source/target or later-association structure is concrete enough.

The builder must not invent a destiny interpretation when the source material does not contain one.

### 意象伏笔

Use:

- `objects[].name`
- `places[].name`
- `literary_texts[].title`
- `current_chapter_foreshadowing_signals[]`
- `later_associations[].topic`
- `later_associations[].description`

Generate:

- image/object/place/foreshadowing topics;
- evidence records from chapter fields;
- relation records for later associations that include source chapters or source IDs.

### 可引用事实

Use concise, chapter-locatable statements from all supported fields.

Generate:

- fact topics by entity or capability, such as `林黛玉性格事实`, `重要章回出处`, `事件因果出处`;
- evidence records that are short enough to be useful in student answers;
- `quotableFactIds` pointing to the generated evidence IDs.

This category must not generate stock answer templates, standard answers, or unsupported interpretation.

## Filtering and Ranking

The first version should favor reliability over completeness.

Include a concrete topic when at least one of these is true:

- It has evidence from two or more chapters.
- It is chapter-scoped but comes from a high-value field such as `key_events`, `literary_texts`, `current_chapter_foreshadowing_signals`, or `later_associations`.
- It is a recurring character or relation.

For each topic:

- Keep up to 12 evidence IDs.
- Keep up to 12 relation IDs.
- Keep up to 12 card IDs.
- Sort evidence by chapter, then source field, then stable source index.
- Preserve chapter provenance.

## Student-Facing Language Rules

Generated student-facing JSON must not contain:

- `LightRAG`
- `RAG`
- `知识图谱`
- `向量检索`
- `置信度`
- `模型分数`
- `标准答案`
- `题库`
- `刷题`
- `下一题`
- `提交答案`
- `批改`

Use `全书线索`, `关系线索`, `相关章回`, `原文依据`, and `章节资料` instead.

## CLI Behavior

Add:

```bash
python scripts/build_topic_index.py \
  --data-dir data/app \
  --review-cards data/app/chapter_review_cards.json \
  --write
```

Default mode should be dry-run: it prints a summary and does not write files.

`--write` writes formatted JSON with `ensure_ascii=False` and stable ordering.

The command should report:

- number of input chapter cards;
- number of generated topics by category;
- number of generated evidence records;
- number of generated relation records;
- number of generated knowledge cards;
- skipped candidates and reasons.

## Makefile Integration

Add:

```makefile
build-topic-index:
	python scripts/build_topic_index.py --data-dir data/app --review-cards data/app/chapter_review_cards.json --write
```

The local content-refresh sequence becomes:

```bash
make generate-all-chapter-materials ARGS='--chapters 1-120 --json-only --overwrite-cards --no-postgres'
make build-topic-index
make build-static-chapter-cache CHAPTERS=1-120
pytest tests/test_topic_index.py tests/test_content_store.py tests/test_web_app.py tests/test_student_language.py
```

## Error Handling

The builder should fail fast when required files are missing or malformed.

The builder should skip a candidate when:

- it has no title-like text;
- it has no chapter provenance;
- it would generate forbidden student-facing terms;
- it cannot produce any resolvable evidence/card/relation reference.

Skipped candidates should be counted in the summary, not silently ignored.

## Testing

Add tests for:

- generating more concrete topics than the five seed category records;
- each generated topic having at least one evidence/card/relation reference;
- all generated references resolving against the produced JSON payloads;
- generated evidence carrying chapter provenance;
- `判词命运` receiving generated content when literary/destiny material exists;
- dry-run mode not writing files;
- write mode being idempotent;
- forbidden student-facing terms staying out of generated outputs;
- `/api/topics` and `/api/topics/<id>` continuing to return valid payloads from generated JSON.

## Risks

The main risk is noisy topic generation. The first version should therefore generate fewer, higher-signal topics rather than every possible phrase.

The second risk is duplicate or awkward names. Stable slugging and conservative title normalization should avoid most of this, but some generated titles may need future curation.

The third risk is large diffs in seed JSON files. Tests should focus on structure and integrity, while committed generated output should be reviewed carefully.

## Acceptance Criteria

- A repeatable command builds the topic index from chapter review cards.
- The generated topic list includes many concrete topics under the five existing categories.
- Every topic has at least one resolvable evidence/card/relation reference.
- Generated evidence contains chapter provenance.
- `判词命运` is not empty when relevant source material exists.
- Student-facing generated JSON avoids forbidden technical and practice-question terms.
- Focused tests and the full project test suite pass after implementation.

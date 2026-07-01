# 《红楼梦》高效阅读产品设计

## Background

高中生需要阅读《红楼梦》，但原著篇幅长、语言不完全白话、人物关系复杂、伏笔和照应跨越大量章回。学生通常没有足够时间完整细读 120 回，却仍需要在高考和校考的名著阅读部分回答人物、情节、判词、意象、伏笔和表达类问题。

本项目已有以下基础材料：

- `book/红楼梦.txt` 原文。
- `book/chapters/` 拆分后的 120 回章节。
- 全书 LightRAG / RAG 图谱处理流程。
- `questions/` 中 286 道校准样例。
- `docs/question_types.md` 中对题型能力的初步分析。

`questions/` 不是产品题库，而是校准样例：它帮助 LLM 和 Agent 理解真实考试常考能力、问题类型和样式，从而设计知识组织、解释方式和验收样例。校准样例没有标准答案假设，也不能作为事实证据。

## Product Goal

做一个面向高中生的 Web 产品，帮助他们在遇到《红楼梦》相关问题时快速找到：

- 答案是什么。
- 依据在哪一回、哪段原文或哪条关系线索。
- 为什么可以这样理解。
- 这种理解如何迁移到类似名著阅读题中。

产品不是电子书、刷题 App、自由作文批改工具或泛文学百科。它是一个由考试问题反向校准的《红楼梦》高效阅读与解惑工具。

## Scope

第一版只做网页，不做原生 App。网页需要适配桌面和移动浏览器。

第一版采用三入口知识工作台：

- **问一问**：学生遇到具体疑问时直接提问。
- **读章节**：按 120 回进入章节证据页。
- **看专题**：按人物关系、关键事件、判词命运、意象伏笔、可引用事实浏览。

第一版明确不做：

- 不做刷题 App。
- 不把 `questions/` 的 286 道题作为学生题库。
- 不做自由作答批改。
- 不做每日打卡学习计划。
- 不做用户系统、班级管理、权限、支付或推送。
- 不做答案评分、置信度百分比、模型分数或批改结果。
- 不允许 LLM 无依据发挥。

## V1 Coverage Boundaries

第一版需要把“能用”定义清楚，避免把学生端做成电子书、题库或泛教学系统。

V1 最低覆盖：

- 120 回均可进入章节证据页，包含章回标题、原文正文和已生成的章节复习卡内容。
- 知识卡优先覆盖高频人物、核心事件、金陵十二钗相关判词/曲词、以及题型校准中高频出现的意象和伏笔。
- 原文中的可点击标记只标注已有可靠知识卡的知识对象；没有知识卡的词句不强行标注。
- 专题浏览可以先使用策划后的种子列表，不要求每个知识对象和关系都进入专题。
- 当知识卡、关系线索或专题聚合缺失时，界面显示“暂无可靠资料”，不得让 LLM 临时补写。

明确由产品负责人提供或另行处理：

- LightRAG / 知识图谱抽取流程。
- 每章章节复习卡、人物说明、事件说明等处理后材料的生产。
- 具体 prompt 文案的最终确认。

产品侧只消费这些已生成材料，并定义读取、展示、引用和拒答规则。学生端不展示 LightRAG、RAG、知识图谱等技术名词。

## Student-Facing Fact Presentation Standard

产品面向高中生，事实呈现应服务于快速理解和考试迁移。

- 使用清楚、现代的中文，不写成论文腔或文学评论腔。
- 遇到文言、诗词、判词和典故时，只解释与当前证据相关的部分。
- 避免没有证据支撑的宏大主题判断，例如“封建社会必然灭亡”这类泛化表述必须有具体文本支撑才可出现。
- 区分“理解解释”和“可引用事实”：前者帮助学生懂，后者提供具体、可追溯、可用于作答的事实材料。
- 产品不提供万能模板、标准答案或套话。
- 产品整体对齐全国高中名著阅读能力要求，不绑定某一省市或某一年试卷。

## Core Principle: Evidence First

所有解释必须可追溯到原文、处理后材料、LightRAG 结果或图谱关系。LLM 只负责组织、解释和表达，不负责凭模型权重创造事实。

硬规则：

- 回答前必须先检索或读取证据。
- 关键结论必须逐条对应来源，不能只在回答末尾笼统列参考。
- 没有可靠依据时严格拒答。
- 不做猜测、不补全、不输出“可能是”式解释。
- “可引用事实”也必须基于已有证据整理，不能凭空套话。
- `questions/` 只能校准问法和验收覆盖，不得作为事实证据。

拒答模板应类似：

> 当前资料中没有找到足够依据回答这个问题。你可以尝试提供更具体的人物、章回或情节，或者查看相关章节。

拒答后可以提供继续探索方向，但方向也必须来自已找到的相关章节、人物或专题，不能给无依据推断。

## Evidence Sufficiency Policy

系统必须先判定证据是否足够，再进入回答生成。最低证据要求如下：

| 回答类型 | 最低证据 | 必须拒答的情况 |
| --- | --- | --- |
| 人物身份 / 人物关系 | 原文片段，或带章回来源的图谱关系 | 只有无来源处理后材料、无章回关系或无法定位人物 |
| 情节概括 | 原文章节，或带章回号的章节复习卡 | 找不到相关章回，或处理后材料没有对应章回 |
| 判词 / 曲词 / 花签 / 命运 | 原文中的判词/曲词/花签 + 人物映射 + 章回来源 | 只有人物映射但缺少判词原文或来源 |
| 意象 / 伏笔 / 照应 | 至少两个可定位章回证据，或一条明确带来源的图谱关系 | 只有单个模糊联想，无法说明前后照应 |
| 事件因果 | 起因、经过或结果中至少两个环节有来源 | 只能找到事件名，找不到因果链证据 |
| 可引用事实 | 必须由上方已通过校验的证据整理 | 没有可引用证据，或只是题型套话 |

证据优先级：

1. 原文片段。
2. 带原文位置或章回出处的图谱关系。
3. 带章回号的处理后材料或知识卡。
4. 题型校准材料只能影响问法分类和验收样例，不参与事实判断。

当来源之间冲突时，原文优先；如果无法消解冲突，应展示冲突并拒绝给出确定结论。

混合问题必须拆成多个子结论逐条校验。例如“宝钗为什么是牡丹，这种意象如何体现她的命运？”同时涉及意象解释和命运关联，不能因为其中一个子结论证据充分就放行整个答案。每个子结论都必须满足对应类型的证据要求；证据不足的部分应省略并说明原因，或整体拒答。

## Information Architecture

### Home

首页不做营销页，直接呈现学习工具。

首屏核心是提问框：

> 输入你对《红楼梦》的疑问，系统会基于原文、章节资料和关系线索回答。

提问框下方是三个入口：

- 问一问。
- 读章节。
- 看专题。

首页还可以展示预设或由校准样例归纳出的常见理解入口，例如：

- 刘姥姥三进贾府有什么作用？
- 宝钗为什么是牡丹？
- 探春理家体现了什么性格？
- 金陵十二钗判词怎么对应人物命运？

这个区域命名为“常见理解入口”或“常见疑问入口”，不能命名为“题库”“练习”或“真题”。它不是个人历史、热门榜或题库列表。入口点击后进入问答、章节证据页或专题解释，不提供提交答案、批改、下一题、难度、分值、试卷来源等刷题交互。

### Ask

学生输入自然语言问题，系统返回证据约束型回答。

回答结构固定为：

1. **短结论**：1-3 句话先回答问题。
2. **依据**：列出相关章回、原文线索、章节资料或关系线索。
3. **为什么**：解释人物关系、事件因果、象征意义或前后照应。
4. **可引用事实**：整理可用于作答的具体事实，但必须来自上方证据。
5. **继续查看**：跳转到相关章节、人物卡、事件卡或专题页。

### Chapter Evidence Page

章节证据页采用“原文 + 右侧知识面板”的布局。

左侧主区域：

- 章节标题。
- 章节复习卡中的本回白话梗概。
- 本回主要人物。
- 本回关键事件。
- 原文正文。

右侧知识面板：

- 默认显示本回重点。
- 当学生点击或选中原文中的人物、事件、诗词、物件、意象时，显示对应知识卡。
- 原文保持相对干净，只做克制的可点击标记，不做满屏高亮。

响应式要求：

- 桌面端和较宽平板端使用常驻右侧知识面板。
- 移动端使用底部抽屉或全屏抽屉承载同一知识卡结构。
- 移动端的来源引用必须保持可见或一键可达，不能因为屏幕窄而隐藏证据。
- 原文选择、知识对象点击和返回原文位置在移动端也必须可用。

### Topic Browser

专题不是百科目录，而是围绕考试能力覆盖中的常见问题视角组织。

首批专题：

- **人物关系**：人物身份、别称、称谓、主仆/亲属/婚恋/对照关系。
- **关键事件**：事件起因、经过、结果、牵涉人物、章回出处。
- **判词命运**：判词、曲词、花签、灯谜与人物命运。
- **意象伏笔**：物件、颜色、花、梦、石、泪、园林空间等象征和照应。
- **可引用事实**：整理人物关系、事件经过、章回出处、判词原文、意象出现位置、前后照应等可用于作答的事实材料。

每个专题页包含：

- 专题说明：这个主题为什么常考。
- 核心知识卡：人物/事件/判词/意象列表。
- 关系线索：展示它们如何跨章节连接。
- 典型问法：来自校准样例总结出的问法类型，不直接当题库。
- 可引用事实：学生答类似题时可以使用的事实材料。

## Knowledge Panel

知识面板是核心交互。它出现在章节页、问答结果页和专题页。

一个知识卡分三层：

1. **文本理解**
   - 它是谁或是什么。
   - 当前上下文是什么。
   - 这段内容是什么意思。

2. **理解角度**
   - 常考点。
   - 可引用情节。
   - 可引用事实。

3. **关系线索**
   - 相关人物。
   - 相关事件。
   - 前后伏笔。
   - 章回连接。

知识卡字段建议：

- 名称。
- 类型。
- 简短解释。
- 相关章回。
- 原文依据。
- 相关人物/事件/意象。
- 理解角度。
- 可引用事实。
- 来源状态：原文明确 / 处理后材料 / 图谱关系 / 可引用事实。

来源状态用于展示信息出处，不允许作为 LLM 自由发挥的理由。

## Data Sources

产品默认使用四类数据：

1. **原文**
   - `book/红楼梦.txt`
   - `book/chapters/`
   - 原文是最高优先级证据。

2. **处理后材料**
   - 章节复习卡。
   - 每回白话梗概。
   - 情节链、人物表现、人物关系、地点、物件意象、诗词曲文、主题手法、当前章伏笔信号。
   - 可引用事实、RAG 检索标签、知识对象清单。
   - 后文关联只能来自全书图谱或明确后文章回证据，不能由只看当前回的 LLM 推断。

3. **LightRAG / 知识图谱**
   - 知识对象。
   - 图谱关系。
   - 跨章伏笔。
   - 人物关系。
   - 判词命运。
   - 事件因果。
   - 章回出处。

4. **校准样例**
   - `questions/` 中的过往题目材料。
   - 用于总结考试能力覆盖和典型问法。
   - 不作为学生刷题入口。
   - 不作为事实证据。

## V1 Data Contracts

实现计划应优先围绕稳定数据契约展开。以下是产品侧需要消费的最小结构，具体文件格式可以是 JSON、YAML 或数据库表，但字段语义应保持一致。

### Chapter

```ts
type Chapter = {
  id: string
  number: number
  title: string
  originalTextPath: string
  reviewCardId?: string
  primaryEntityIds: string[]
  primaryEventIds: string[]
}
```

### ChapterReviewCard

```ts
type ChapterReviewCard = {
  id: string
  chapter: number
  plainSummary: string
  plotChain: string[]
  keyEvents: string[]
  keyCharacters: string[]
  currentChapterForeshadowingSignals: string[]
  laterAssociationRelationIds: string[]
  quotableFactIds: string[]
  retrievalTags: string[]
  understandingFocus: string[]
  source: {
    promptName: string
    promptVersion: string
    generatedAt?: string
  }
}
```

### Evidence

```ts
type Evidence = {
  id: string
  sourceType: "original_text" | "processed_material" | "knowledge_card" | "graph_relation"
  chapter?: number
  location?: string
  quote?: string
  evidenceText?: string
  entityIds?: string[]
  relationId?: string
  confidence: "explicit" | "derived" | "weak"
  provenance: string
}
```

`confidence: "weak"` 的证据只能用于提示继续阅读方向，不能支撑确定回答。
`confidence: "derived"` 可以支撑结论，但必须能追溯到至少一个 `confidence: "explicit"` 的原文、处理后材料或图谱来源；不能单独作为最终答案依据。

### GraphRelation

```ts
type GraphRelation = {
  id: string
  subjectId: string
  predicate: string
  objectId: string
  chapters: number[]
  evidenceIds: string[]
  provenance: "lightrag" | "curated"
}
```

LightRAG / 知识图谱被视为外部已提供数据源。产品实现不负责抽取图谱，只要求图谱关系能读到知识对象、关系、章回、证据 ID 和来源。

### KnowledgeCard

```ts
type KnowledgeCard = {
  id: string
  name: string
  type: "person" | "event" | "judgement" | "image" | "object" | "place" | "expression"
  brief: string
  textUnderstanding: string[]
  understandingAngles: string[]
  graphRelationIds: string[]
  evidenceIds: string[]
  relatedCardIds: string[]
}
```

### Topic

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

“可引用事实”不是通用答题模板，也必须携带 `evidenceIds`。没有证据的事实材料不能进入专题卡或问答结果。

### AskAnswer

```ts
type AskAnswer = {
  id: string
  question: string
  status: "answered" | "partial" | "refused"
  shortConclusion: AnswerClaim[]
  evidence: Evidence[]
  explanation: AnswerSection[]
  quotableFacts?: AnswerSection
  continuationLinks: ContinuationLink[]
  refusal?: Refusal
}

type AnswerSection = {
  title: string
  claims: AnswerClaim[]
}

type AnswerClaim = {
  text: string
  evidenceIds: string[]
  claimType:
    | "identity_relation"
    | "plot_summary"
    | "judgement_destiny"
    | "image_foreshadowing"
    | "event_causality"
    | "quotable_fact"
}

type Refusal = {
  reason:
    | "NO_EVIDENCE"
    | "AMBIGUOUS_ENTITY"
    | "GRAPH_UNAVAILABLE"
    | "SOURCE_CONFLICT"
    | "OUT_OF_SCOPE"
    | "UNSUPPORTED_SUBCLAIM"
  message: string
}

type ContinuationLink = {
  label: string
  targetType: "chapter" | "card" | "topic" | "relation"
  targetId: string
}
```

`status: "partial"` 只用于混合问题中部分子结论有证据、部分子结论证据不足的情况。前端必须明确显示哪些部分被回答、哪些部分因证据不足未回答。

### PromptDefinition

```ts
type PromptDefinition = {
  name: string
  version: string
  purpose: string
  inputSchema: string
  outputSchema: string
  evidenceRules: string[]
  refusalRules: string[]
}
```

Prompt 定义必须存放在结构化配置中。V1 可以使用产品负责人确认的占位 prompt，但不能在业务代码里散落临时 prompt 字符串。Prompt 编辑 UI 不属于 V1。

### Citation Display

前端展示引用时至少包含：

- 来源类型：原文 / 处理后材料 / 知识卡 / 图谱关系。
- 章回号和章回标题。
- 支撑结论的具体说明；原文短摘录可选但推荐。
- 可点击跳转目标：章节位置、知识卡或关系详情。

问答结果中的每个关键结论都应携带 `evidenceIds`，前端据此展示引用。
引用中的章回标题通过 `Evidence.chapter` 解析到 `Chapter.number` 和 `Chapter.title`。除少数确实不绑定章回的系统性说明外，没有可解析章回或来源标题的证据不能支撑确定结论。
章回定位是最低可追溯要求，不是解释性结论的充分依据。人物性格、主题手法、意象象征或伏笔照应类结论，还必须有来自原文、处理后材料或图谱关系的具体说明。

## Ask Flow

学生提问后的数据流：

1. **问题解析**
   - 判断问题涉及哪些知识对象：人物、事件、章回、判词、意象、物件、关系、专题。

2. **证据检索**
   - 调用 LightRAG 或本地索引。
   - 找相关知识对象、图谱关系、原文线索、处理后材料。

3. **证据校验**
   - 判断是否有足够依据回答。
   - 关键结论必须能对应至少一个明确来源。
   - 混合问题按子结论分别校验；不满足证据要求的子结论不得生成确定回答。

4. **结构化生成**
   - LLM 只能基于检索证据生成回答。
   - 输出 `AskAnswer`，包含短结论、依据、解释、可引用事实、继续查看入口和拒答状态。

5. **来源展示**
   - 前端展示相关章回、具体说明、可选原文摘录或关系线索。
   - 不允许只展示一段无来源自然语言答案。

如果 LightRAG 或图谱数据不可用，Ask Flow 只能回答原文和处理后材料足以支撑的问题；人物关系、跨章伏笔、判词命运、事件因果等依赖图谱的问题必须拒答或提示“关系线索暂不可用”。学生端不展示 LightRAG、RAG 或知识图谱等技术名词。

## Prompt Registry

LLM 提示词是产品资产，不应是散落在代码里的临时字符串。

系统应支持一套受控 prompt：

- 章节复习卡生成 prompt。
- 人物/事件/意象解释 prompt。
- 问答生成 prompt。
- 拒答判定 prompt。
- 可引用事实整理 prompt。
- 证据引用格式 prompt。

每个 prompt 应记录：

- 名称。
- 版本。
- 用途。
- 输入数据结构。
- 输出格式。
- 事实边界。
- 拒答规则。

具体 prompt 可以由产品负责人提供或确认，系统按版本管理和调用。

## Calibration & Acceptance Sample Set

`questions/` 的作用是校准真实考试能力覆盖，不是学生题库，也不是事实来源。

V1 应从 `questions/` 中抽取 20-40 个内部验收样例，覆盖 `docs/question_types.md` 中列出的主要能力：

- 人物关系与身份别称。
- 章回情节与内容概括。
- 比较鉴赏与论述。
- 诗词判词与人物命运。
- 主题意象与象征。
- 事件因果与伏笔照应。
- 制度礼俗与文化常识。

每个验收样例记录：

- 原始问法或归纳后的问法。
- 期望识别的人物、事件、意象、判词或章回。
- 期望证据类型，例如原文、处理后材料、图谱关系。
- 是否应拒答。
- 质量备注：哪些表达是合格的，哪些属于无依据发挥。

验收不要求固定答案逐字一致。通过标准是系统能找到相关证据、引用来源、组织出适合高中生的理解表达，并在证据不足时拒答。

## Architecture

第一版建议是轻量 Web 应用。技术上可以前后端一体，也可以轻量前后端分离，但逻辑上分四层：

1. **内容数据层**
   - 存放原文、章节复习卡、知识卡、专题聚合、校准样例分析结果、prompt 配置和 LightRAG 图谱关系。

2. **检索与证据层**
   - 根据用户问题或页面上下文取证据。
   - 不生成答案，只返回可追溯材料。

3. **回答编排层**
   - 调用 LLM，把证据组织成固定结构回答。
   - 必须执行严格拒答规则。

4. **Web 交互层**
   - 展示问一问、读章节、看专题、原文 + 右侧知识面板。

核心模块：

- **Chapter Evidence Page**：章节证据页模块。
- **Knowledge Panel**：右侧知识面板。
- **Ask Engine**：证据约束问答引擎。
- **Topic Browser**：专题浏览模块。
- **Prompt Registry**：prompt 管理模块。
- **Evidence Store**：证据存储和索引模块。

产品页面不直接相信 LLM 输出的事实。事实必须来自 Evidence Store、处理后材料或 LightRAG。

## Error Handling

### Evidence Missing

严格拒答，不猜测。提供更具体的问法或相关章节入口。

### LightRAG Unavailable

不能假装能回答跨章关系问题。可以降级展示本地章节复习卡和原文，并在学生端提示关系线索暂不可用。

### LLM Failure

如果证据已找到但 LLM 失败，可以展示原始证据和“暂时无法生成解释”。不返回空白页。

### Source Conflict

原文、处理后材料、图谱关系之间出现冲突时，原文优先。页面应提示存在来源不一致，并展示冲突来源。

### Broad Question

对“讲讲红楼梦”这类过泛问题，引导学生缩小范围到人物、事件、章回、判词、意象或专题。

### Out of Scope

对其他名著、现实八卦、作文代写等问题，提示当前产品只支持《红楼梦》阅读理解相关问题。

## Testing Strategy

### Unit Tests

- 章节读取和章回索引。
- 知识卡读取。
- prompt registry 加载。
- 证据对象格式。
- 拒答条件判断。

### Integration Tests

- 给定问题 -> 检索证据 -> 生成结构化回答。
- 给定知识对象 -> 打开知识面板 -> 展示来源。
- 给定章回 -> 展示原文、章节复习卡内容、关键人物/事件。
- LightRAG 不可用时的降级行为。

### Answer Quality Samples

用 `questions/` 中抽样出的典型问法做验收样例，但不把它作为题库。测试重点：

- 是否能找到相关章回、人物、事件。
- 是否展示证据。
- 是否没有编造。
- 是否能输出适合学生理解的解释和可引用事实。

### Refusal Tests

人为构造没有证据的问题，确认系统拒答，而不是胡编。

### Measurable Thresholds

V1 质量门槛：

- 100% 的非拒答问答结果至少展示一个来源。
- 100% 的关键结论携带 `evidenceIds`，前端能展示对应引用。
- 内部验收样例必须覆盖七类主要能力中的每一类。
- 拒答测试集中的 unsupported 问题必须全部拒答。
- LightRAG 不可用时，图谱依赖型问题不得输出确定答案。
- 来源冲突测试必须体现原文优先，并给出冲突提示。
- 移动端冒烟测试必须覆盖问一问、章节阅读和知识面板打开/关闭。

## Acceptance Criteria

第一版满足以下条件即认为可用：

- 学生可以通过首页提问，得到有来源的短结论和解释。
- 学生可以进入任意一回，看到原文、章节复习卡内容和右侧知识面板。
- 学生可以点击已标注且有可靠知识卡的人物、事件、判词或意象，看到文本理解、理解角度和关系线索。
- 至少五类专题可浏览：人物关系、关键事件、判词命运、意象伏笔、可引用事实。
- 所有结论都有来源；没有来源时拒答。
- `questions/` 抽样出的典型问题能被用于验证产品方向：系统能定位材料和整理可引用事实，但不把它做成刷题题库。
- 网页端可在桌面和移动浏览器使用。
- 移动端知识面板使用抽屉或等价结构，保留与桌面端一致的文本理解、理解角度和关系线索。
- 首页“常见理解入口”不会出现刷题、批改、分值、下一题等交互。
- 学生端不展示答案评分、置信度百分比、模型分数或批改结果。
- V1 实现不承担 LightRAG 图谱抽取，只消费带来源的图谱关系。

## Risks and Tradeoffs

### Answer Length

如果回答太长，学生不愿看；如果太短，又不能真正理解。默认应短结论优先，详细解释折叠展开。

### Hallucination Risk

最大技术风险是证据约束不严格导致 LLM 编造。需要通过检索层、prompt、拒答规则和测试样例共同约束。

### Product Sprawl

不要过早加入用户系统、刷题、批改、学习计划、班级管理等模块。第一版的核心是验证“证据约束回答 + 原文知识面板”的学习体验。

### Graph Complexity

知识图谱提取由产品负责人处理，产品侧只消费结果。产品设计不应被图谱构建流程拖住，但必须为来源、关系和章回出处保留结构化展示能力。

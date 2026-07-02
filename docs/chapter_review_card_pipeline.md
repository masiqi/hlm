# Chapter Review Card Pipeline

## Purpose

章节复习卡是 V1 的核心内容层：它把单回原文压缩成高中生能快速理解的章节材料，同时保留人物、事件、地点、物件、主题、伏笔和可检索标签，目标是支撑“8小时读懂全书”。

它不是题库，也不是标准答案。`questions/` 里的真题样例只用于让 agent 理解常见问题类型和证据形态，不导入学生端刷题流程。

## Inputs

- `book/chapters/`: 120 回原文，每个文件名包含章回编号、回目标号和回目标题。
- LightRAG `/query/data`: 全书关系线索和跨章证据来源，用于后文关联、伏笔照应、人物关系和命运线索。
- `data/prompts/definitions.json`: 章节卡提示词契约，当前定义名为 `hongloumeng_chapter_review_card`。

## Generation Order

全量 120 回都需要生成。为降低首批质量风险，先抽样生成并人工检查以下 10 回，再批量处理全书：

1. 第三回：宝黛初会、贾府空间和主要人物出场。
2. 第五回：太虚幻境、判词曲文和命运线索。
3. 第八回：金锁、通灵宝玉和金玉良缘。
4. 第二十七回：宝钗扑蝶、黛玉葬花和《葬花吟》。
5. 第三十一回：晴雯撕扇、金麒麟伏笔。
6. 第三十三回：宝玉挨打和家族礼法冲突。
7. 第五十六回：探春理家和兴利除弊。
8. 第六十三回：群芳开夜宴、花签和命运暗示。
9. 第七十四回：抄检大观园和理想世界崩解。
10. 第九十七回：黛玉焚稿、宝钗成婚和爱情悲剧。

## Prompt Contract

每回生成必须包含：

- 本回一句话概括。
- 本回梗概，250 到 400 字，按情节发展顺序说明主要内容。
- 情节链梳理，标注起因、经过、结果、作用和是否伏笔。
- 主要人物与本回表现，绑定人物行为、性格特点和答题证据。
- 人物关系图谱，说明关系类型、变化和权力/情感差异。
- 关键地点、关键物件意象、诗词曲文和语言细节。
- 主题与艺术手法、伏笔照应与后文关联、可考点、易错点和现代汉语解释。
- 本回核心知识卡片、知识图谱三元组、实体清单和检索标签。
- 本回复习建议，帮助学生知道本回最该记什么、如何联读。

后文关联不能由 LLM 只凭当前回原文或模型常识补写。生成前应先用 LightRAG `/query/data` 检索与本回人物、事件、物件、地点和主题相关的全书关系线索；有可靠关系时写入后文关联，没有可靠关系时写“本回暂不能确定”或“需结合后文”。

## App Import Shape

生成后的章节卡需要能归一化为 `ChapterReviewCard`：

```json
{
  "id": "review-027",
  "chapter": 27,
  "source": {
    "prompt_name": "hongloumeng_chapter_review_card",
    "prompt_version": "2026-07-01",
    "generated_at": "2026-07-02"
  },
  "plain_summary": "第二十七回主要写……",
  "plot_chain": ["……"],
  "key_events": ["……"],
  "key_characters": ["card-lindaiyu"],
  "current_chapter_foreshadowing_signals": ["……"],
  "later_association_relation_ids": ["rel-daiyu-burying-flowers-fate"],
  "quotable_fact_ids": ["ev-027-daiyu-burying-flowers"],
  "retrieval_tags": ["#红楼梦", "#第二十七回", "#黛玉葬花"],
  "understanding_focus": ["把黛玉葬花理解为人物心理、诗意表达和命运线索的交汇点。"]
}
```

`later_association_relation_ids` 和 `quotable_fact_ids` 只能引用已经存在、可回溯的关系或证据。批量导入时如果暂时没有这些 ID，可以留空，但不能伪造 ID。

## Quality Gate

每批生成后至少检查：

- `plain_summary` 非空，且是本回内容，不是全书泛论。
- `plot_chain` 非空，顺序与原文一致。
- 后文关联必须有 LightRAG 关系线索或明确后续章回证据。
- 学生端文字不能出现 `LightRAG`、`RAG`、`知识图谱`、`向量检索`、`置信度`、`模型分数`、`标准答案`、`题库`、`批改`。
- 不能把影视剧、续书、脂批争议内容混成本回原文事实。
- 对资料不足的内容严格写明“不确定”或“需结合后文”，不补编。

## Development Notes

V1 开发不需要等 120 回全部生成完成才能继续。代码路径必须支持：

- 已生成章节卡时展示“章节资料”和快速理解内容。
- 未生成章节卡时仍能展示原文，并提示“章节资料暂未生成，可先阅读原文”。
- 问答时优先使用原文、章节资料和 LightRAG `/query/data` 证据，不直接信任 LightRAG `/query` 的生成式回答。

# Hongloumeng Reading Assistant

This context defines the product language for a web-based assistant that helps high-school students understand 《红楼梦》 through evidence-backed reading support.

## Language

**校准样例**:
Historical exam-style question materials used to show LLMs and agents the kinds, forms, and expectations of problems the product must support. They are not student-facing practice questions, not a question bank, not factual evidence, and do not imply prepared standard answers.
_Avoid_: 题库, 真题库, 练习题, 刷题材料

**问法校准实体**:
Graph entities such as `QuestionTask` and `ExamSource` that help the product and agents understand exam-style task forms and source context. They may guide retrieval, categorisation, and common-understanding entry points, but are not student-facing question-bank entries and cannot support factual claims about the novel.
_Avoid_: 真题入口, 练习列表, 事实依据

**考试能力覆盖**:
The requirement that graph extraction and content preparation cover the kinds of reading-comprehension abilities real exams ask for, such as identifying relationships, summarising plots, interpreting judgement poems, explaining images, tracing foreshadowing, and comparing characters. It is not a student-facing practice, grading, or exercise-explanation feature.
_Avoid_: 练习讲解功能, 刷题能力, 批改功能

**事实证据**:
Material that can support a determinate product answer about 《红楼梦》. It may come from original text, chapter summaries with chapter provenance, knowledge cards with sources, or LightRAG/knowledge graph relations with sources; calibration samples, LLM memory, and unsourced literary interpretation are not factual evidence.
_Avoid_: 资料, 参考, 背景知识, 模型常识

**部分回答**:
An answer to only the subclaims in a mixed question that are supported by factual evidence, while explicitly naming the unsupported parts that are not answered. It is not a softer form of guessing and cannot include probable, approximate, or generally accepted claims without factual evidence.
_Avoid_: 猜测回答, 勉强回答, 弱回答

**可引用事实**:
Concrete facts distilled from factual evidence that students can use when answering reading-comprehension questions, such as character relationships, event sequences, chapter provenance, judgement poems, image occurrences, and foreshadowing links. It should be short, specific, and source-locatable; it may indicate what understanding it supports, but it is not a complete answer sentence, standard answer, stock phrase, or writing framework.
_Avoid_: 常考表达, 答题模板, 万能句式, 套话, 标准答案, 作答框架, 成段答案

**知识卡**:
An evidence index for a single 《红楼梦》 object, connecting that object to factual evidence, chapter provenance, related characters, events, images, and quotable facts. It may include brief explanation, but only to help navigate evidence; it is not an encyclopedia entry or free literary appreciation.
_Avoid_: 百科词条, 自由讲解, 文学赏析卡

**知识对象**:
An object around which the product organises evidence and relations, including characters, aliases, families, roles, places, chapter events, plot actions, relationships, traits, fate foreshadowing, literary texts, symbolic objects, theme concepts, and question-calibration entities. It is a product-domain object, not a generic knowledge point or database implementation detail.
_Avoid_: 知识点, 百科条目, 数据库实体

**专题**:
A problem perspective that groups knowledge cards and factual evidence around a recurring reading-comprehension need, such as character relationships, key events, judgement-and-destiny links, image foreshadowing, or quotable facts. It is not an encyclopedia category, course unit, or practice-question classification.
_Avoid_: 百科栏目, 课程单元, 刷题分类

**常见理解入口**:
A curated entry point, manually configured or derived from calibration samples, that sends students into evidence-constrained Q&A, a chapter evidence page, or a topic. It is not personal history, a popularity ranking, or a question-bank list.
_Avoid_: 热门题榜, 个人历史, 真题列表, 下一题入口

**图谱关系**:
A sourced relationship provided by the LightRAG API or curated graph data, connecting entities such as characters, events, chapters, judgement poems, images, and foreshadowing links. The product consumes and displays graph relations for evidence validation; V1 does not extract, infer, or invent new graph relations.
_Avoid_: AI 推理关系, 模型猜测关系, 自动脑补关系

**学生端来源语言**:
Student-facing UI language for evidence and relationships, using terms such as original evidence, chapter summary, relationship clue, later association, and related chapter instead of implementation terms. Student-facing UI should not show LightRAG, RAG, or knowledge-graph technology names.
_Avoid_: LightRAG, RAG, 知识图谱, 向量检索

**章回定位**:
The minimum student-facing source locator for a claim, pointing to the specific chapter where supporting evidence can be found. It is not sufficient by itself for interpretive claims; character, theme, image, or foreshadowing conclusions also need concrete supporting explanation from original text, sourced processed material, or graph relations.
_Avoid_: 无出处结论, 只给观点, 不可定位来源

**全书图谱**:
The LightRAG/RAG knowledge graph for all 120 chapters, provided to the product as an external content source. Product code can be developed against this provided input contract and does not own the graph extraction workflow.
_Avoid_: 产品内抽取流程, 临时推理图谱, 不完整长期状态

**V1 完整应用**:
The first release is expected to apply the three core content sources together: original text, sourced processed material, and the full-book graph. It is not a deliberately thin version that postpones the core reading experience to a later V2.
_Avoid_: 轻版占位, 后续再补核心能力, V2 才完整

**三源合一阅读支持**:
The core reading experience that uses original text, sourced processed material, and the full-book graph together. Original text provides highest-priority facts, processed material lowers comprehension difficulty, and the full-book graph provides structured links such as relationships, foreshadowing, later associations, and chapter provenance.
_Avoid_: 只读原文, 只看摘要, 只问图谱

**证据加工回答**:
An answer that synthesises original text, sourced processed material, and graph/RAG results into a clear response while preserving factual grounding. The LLM may organise, explain, and phrase the answer for students, but must not rely on model weights to introduce claims that are not supported by those sources.
_Avoid_: 纯编, 自由发挥, 无证据加工, 模型权重补事实

**章节证据页**:
A chapter page that shows original text, chapter summary, annotated knowledge objects, and the knowledge panel so answers can be traced back to chapter evidence and graph relations. It is not a full ebook reader and does not imply bookshelf, reading progress, highlighting, note-taking, theme, or continuous-reading features.
_Avoid_: 电子书阅读器, 书架, 阅读进度, 读书笔记

**知识面板**:
A contextual evidence panel that changes with the current question, chapter, or selected object, showing factual evidence, related knowledge cards, graph relations, and quotable facts. It is not a chat sidebar, free explanation area, or encyclopedia detail panel.
_Avoid_: AI 聊天侧栏, 自由解释区, 百科详情面板

**理解角度**:
Student-facing perspectives that help interpret a knowledge object, such as character, plot, relationship, image, foreshadowing, fate, theme, or technique. Exam ability coverage may inform which perspectives matter, but the UI should not present this layer as exam drilling or standard-answer training.
_Avoid_: 考试角度, 答题角度, 标准答案角度

**证据约束问答**:
A conversational interaction where students may ask questions naturally, but every product answer must be grounded in factual evidence from original text, processed summaries, or LightRAG results. It is not open-ended chat, literary common-knowledge answering, or composition ghostwriting.
_Avoid_: 聊天机器人, AI 助手随便问, 开放问答, 作文代写

**单次会话**:
The temporary interaction context for a student's current use of the web product. V1 does not require login, personal question history, favourites, or long-term learning records.
_Avoid_: 个人历史, 收藏夹, 学习档案, 长期记忆

**处理后材料**:
Structured content generated ahead of time by LLMs or other workflows and saved with chapter or source provenance, such as chapter summaries, character notes, event notes, or chapter exam-focus notes. It can participate in factual evidence only when sourced; live LLM answer text is not processed material.
_Avoid_: LLM 知识, 模型理解, AI 结论

**章节复习卡**:
A sourced processed material generated from one chapter's original text, optionally augmented by LightRAG results after the full-book graph has been extracted. It is broader than a chapter summary and may include plot chains, character performance, relationships, places, images, poems, current-chapter foreshadowing signals, LightRAG-backed later associations, exam-relevant facts, graph triples, entities, and retrieval tags; it must not infer later-book links from the current chapter alone.
_Avoid_: 纯摘要, 无来源总结, 本回外事实, 单回推断后文

**内部校准输出**:
Parts of processed material that help agents or humans understand possible question forms, coverage, or evaluation needs but are not shown as student-facing product content in V1. Generated questions, answer points, and scoring hints in chapter review cards belong here unless a later product explicitly designs a practice feature.
_Avoid_: 学生题库, 训练题, 标准答案

**后文关联**:
A cross-chapter relationship between current-chapter content and later text, supplied by LightRAG, knowledge graph data, or explicitly provided later-chapter evidence. It may appear in a chapter review card when generation can call LightRAG after full-book graph extraction; it cannot be produced as a determinate claim by an LLM that only sees the current chapter.
_Avoid_: 单回摘要推断, 无后文证据的伏笔结论, 当前章硬推后文

**本回事实**:
Facts from the current chapter's original text or sourced current-chapter processed material, describing what has already happened or appeared in that chapter. Later associations must be displayed separately and cannot be mixed into the chapter summary or "what happened in this chapter" content.
_Avoid_: 混入后文, 本回外情节, 未发生事实

**证据不足拒答**:
A normal product behavior where the system explicitly declines to answer when the question is out of scope, ambiguous, graph data is unavailable, sources conflict, or factual evidence is insufficient. It is a quality mechanism against unsupported generation, not an error or fallback answer.
_Avoid_: 失败回答, 兜底答案, 保守猜测

**证据状态**:
The user-facing state of whether the product has enough factual evidence to answer: answered, partial, or refused. V1 does not show answer scores, confidence percentages, model similarity scores, or grading because the product does not own standard answers.
_Avoid_: 答案评分, 置信度百分比, 模型分数, 批改结果

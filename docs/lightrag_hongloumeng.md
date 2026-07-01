# 《红楼梦》LightRAG 关系图谱应用骨架

本仓库提供一个本地骨架，用 HKUDS LightRAG Server/WebUI 来创建《红楼梦》关系图谱。默认命令只做 dry-run，不会调用 LLM 或 Embedding 服务，也不会消耗额度。

## 目录

- 原著：`book/红楼梦.txt`
- 拆分章节：`book/chapters/`
- 章节清单：`book/chapters_manifest.json`
- LightRAG 输入目录：`data/inputs/`
- LightRAG 工作目录：`data/rag_storage/`
- 领域实体提示词：`data/prompts/entity_type/hongloumeng_entity_type.yml`
- 题型盘点：`docs/question_types.md`

## 1. 填写 `.env`

先复制模板：

```bash
make env
```

然后编辑 `.env`，至少填写：

- `LLM_BINDING`、`LLM_BINDING_HOST`、`LLM_BINDING_API_KEY`、`LLM_MODEL`
- `EMBEDDING_BINDING`、`EMBEDDING_BINDING_HOST`、`EMBEDDING_BINDING_API_KEY`、`EMBEDDING_MODEL`、`EMBEDDING_DIM`
- 如需分角色模型，可填写 `EXTRACT_*`、`KEYWORD_*`、`QUERY_*`

不要把真实 key 写入 `.env.example`。`.env` 已被 `.gitignore` 忽略。

## 2. 拆分章节

```bash
make split-chapters
```

脚本会检查 `book/红楼梦.txt` 中的章回标题。当前文本格式为 `第1章 ...` 到 `第120章 ...`，脚本会生成 120 个章节文件，并在文件名中规范成 `001-第一回-...txt` 这类格式。原始 `book/红楼梦.txt` 不会被修改。

如果脚本不能确认正好 120 回，会停止并输出检测到的标题数量和样例标题。

## 3. 题目样例盘点

```bash
make analyze-questions
```

该命令只解析 `questions/zujuan_questions_2026-06-30.jsonl` 并生成题型盘点，不会解答题库。若未来有人误写 `quesitons/`，当前交付不依赖该目录，实际输入以 `questions/` 为准。

## 4. Dry-run 验证

```bash
make dry-run
```

dry-run 会完成：

- 检查 `.env` 是否存在，不存在则从 `.env.example` 创建；
- 验证必要配置项是否存在；
- 拆分并校验 120 个章节；
- 打印目标 LightRAG 地址、WebUI 地址、输入目录、模型配置摘要；
- 检测 `.env` 是否仍是占位 API key；
- 不复制文件到 LightRAG 输入目录，不启动服务，不调用 `/documents/scan`。

## 5. 启动 LightRAG WebUI

填好 `.env` 后启动服务：

```bash
make lightrag-up
```

默认 WebUI 地址：

```text
http://127.0.0.1:9621/webui
```

如果修改了 `HOST` 或 `PORT`，以 `.env` 中的值为准。Docker 容器内使用官方目录约定：

- `/app/data/rag_storage`
- `/app/data/inputs`
- `/app/data/prompts`

## 6. 一键创建图谱

确认 `.env` 中 LLM 和 Embedding key 都不是占位值后运行：

```bash
make build-kg
```

真实模式会执行：

1. 检查 `.env`；
2. 拆分章节并写入 `book/chapters_manifest.json`；
3. 启动 LightRAG Docker 服务；
4. 将 120 个章节文件复制到 `data/inputs/`；
5. 检查 `GET /health`；
6. 调用 `POST /documents/scan`；
7. 轮询 `/documents/track_status/{track_id}` 和 `/documents/pipeline_status`；
8. 输出 WebUI 地址。

这一步会调用 LLM 和 Embedding 服务并产生费用，只有在你明确执行 `make build-kg` 时才会发生。

## 7. 查询建议

图谱构建完成后，在 WebUI 中优先使用 `mix` 或 `hybrid` 模式提问，例如：

- 概括第三回林黛玉进贾府的主要情节，并列出关键人物。
- 说明贾宝玉、林黛玉、薛宝钗之间的关系及章回依据。
- 某句判词对应哪位人物？它暗示了怎样的命运？
- 某个物件或意象在前后章回中如何伏笔照应？
- 某一事件的起因、经过、结果和牵涉人物关系是什么？

`mix` / `hybrid` 模式更适合同时利用向量召回和关系图谱，回答高中语文整本书阅读题时通常比单纯向量检索更容易给出人物关系、章回出处和情节因果。

## 8. 更换 Embedding 时必须重建

LightRAG 的向量索引依赖 Embedding 模型、维度和查询/文档前缀配置。只要修改以下任一项，就必须清空 `data/rag_storage/` 并重新索引：

- `EMBEDDING_MODEL`
- `EMBEDDING_DIM`
- `EMBEDDING_ASYMMETRIC`
- `EMBEDDING_QUERY_PREFIX`
- `EMBEDDING_DOCUMENT_PREFIX`

原因是旧向量与新模型的语义空间或维度不一致，继续混用会导致检索结果失真，某些存储后端还会因为维度不同直接报错。

## 9. 常见失败处理

- `.env` 缺少字段：对照 `.env.example` 补齐 LLM、Embedding、目录和提示词配置。
- dry-run 检测到占位 key：真实构建会拒绝运行，填入实际服务配置后再执行。
- Docker 拉取失败：检查网络或手动拉取 `ghcr.io/hkuds/lightrag:latest`。
- `/health` 不可达：先运行 `docker compose logs -f lightrag` 查看服务启动错误。
- `/documents/scan` 返回 busy：等待当前 pipeline 完成，或在 WebUI 检查文档处理状态。
- 更换 Embedding 后结果异常：停止服务，清空 `data/rag_storage/`，再重新运行 `make build-kg`。

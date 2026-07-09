# hlm

《红楼梦》整本书阅读助手。项目包含三部分：

- 本地 Web 应用：章节阅读、专题浏览、知识卡和 `问一问`。
- LightRAG 图谱：用全书 120 回构建可检索的实体、关系和 chunk evidence。
- 可选 PostgreSQL 数据层：把章节、知识卡、关系、证据和缓存导入数据库，便于部署和多人共享。

默认仓库已带一套 `data/app/*.json` 应用数据，可以先启动 Web 应用体验；只有在重新构建图谱、启用高质量 `问一问`、或使用 PostgreSQL 时才需要配置 `.env` 和外部服务。

## 目录结构

- `book/红楼梦.txt`：原著全文。
- `book/chapters/`：拆分后的 120 回章节文本。
- `book/chapters_manifest.json`：章节清单。
- `data/app/`：Web 应用默认读取的 JSON 数据和缓存。
- `data/eval/ask_quality_dataset.json`：`问一问` 检索质量评估样例。
- `data/inputs/`：LightRAG 扫描输入目录。
- `data/rag_storage/`：LightRAG 工作目录。
- `data/prompts/`：LightRAG 和内容生成提示词。
- `static/`：前端页面资源。
- `hlm_kg/`：后端应用代码。
- `scripts/`：内容生成、缓存构建和 PostgreSQL 同步脚本。
- `docs/`：更细的建设文档。

## 环境要求

本地开发建议使用：

- Python 3.12 或更新版本。
- `uv`，用于创建虚拟环境和运行 Python 命令。
- Docker 和 Docker Compose，仅在启动 LightRAG Server/WebUI 时需要。
- PostgreSQL，仅在使用数据库模式时需要。

初始化 Python 环境：

```bash
uv venv
uv pip install -r requirements.txt
```

如果机器上已经有可用的 `python` 命令，也可以直接使用 Makefile 中的 `make web`、`make test` 等快捷命令；如果没有裸 `python`，优先使用文档中的 `uv run python -m ...` 命令。

## 快速启动：只体验 Web 应用

这条路径使用仓库内已有的 `data/app/*.json` 数据，不需要 LightRAG、LLM、Embedding 或 PostgreSQL。

```bash
uv run python -m hlm_kg.web_app
```

终端会打印类似地址：

```text
Serving at http://127.0.0.1:8765
```

打开该地址即可体验：

- `读一读`：查看章节原文和章节材料。
- `看专题`：查看专题聚合和知识卡。
- `问一问`：在未配置 LightRAG/LLM 时只能使用有限本地证据；证据不足会拒答。

如果本机有 `python` 命令，也可以使用：

```bash
make web
```

Web 应用默认绑定 `127.0.0.1`，端口从 `8765` 开始自动寻找可用端口。

## 完整本地部署：LightRAG + Web 应用

这条路径会启动 LightRAG、构建全书图谱，并让 Web 应用的 `问一问` 连接 LightRAG `/query/data` 获取证据。

### 1. 生成并填写 `.env`

```bash
make env
```

编辑 `.env`，至少填写：

```bash
LLM_BINDING=openai
LLM_BINDING_HOST=https://api.openai.com/v1
LLM_BINDING_API_KEY=...
LLM_MODEL=...

EMBEDDING_BINDING=openai
EMBEDDING_BINDING_HOST=https://api.openai.com/v1
EMBEDDING_BINDING_API_KEY=...
EMBEDDING_MODEL=...
EMBEDDING_DIM=...
```

如果要让 Web 应用里的 `问一问` 连接本地 LightRAG，还需要补充：

```bash
LIGHTRAG_BASE_URL=http://127.0.0.1:9621
LIGHTRAG_TIMEOUT_SECONDS=300
```

这里有两个容易混淆的变量：

- `HOST` / `PORT`：LightRAG Server 自己监听的地址和端口。
- `LIGHTRAG_BASE_URL`：本项目 Web 后端访问 LightRAG API 的地址。

`问一问` 的 planner 和 evidence judge 默认会继承 `LLM_BINDING_HOST`、`LLM_BINDING_API_KEY`、`LLM_MODEL`。如果希望用更便宜或更快的轻量模型，可以单独填写：

```bash
HLM_ASK_PLANNER_BASE_URL=https://api.openai.com/v1
HLM_ASK_PLANNER_API_KEY=...
HLM_ASK_PLANNER_MODEL=...

HLM_ASK_EVIDENCE_JUDGE_BASE_URL=https://api.openai.com/v1
HLM_ASK_EVIDENCE_JUDGE_API_KEY=...
HLM_ASK_EVIDENCE_JUDGE_MODEL=...
```

不要提交 `.env`，也不要在日志、Issue 或 PR 中粘贴真实 key。

### 2. 先做 dry-run

```bash
uv run python -m hlm_kg.lightrag_app --dry-run
```

或：

```bash
make dry-run
```

dry-run 会检查配置、章节拆分、LightRAG 目标地址和占位 key，不会调用 LLM/Embedding，也不会产生费用。

### 3. 构建全书 LightRAG 图谱

确认 `.env` 里的 LLM 和 Embedding key 都不是占位值后运行：

```bash
uv run python -m hlm_kg.lightrag_app --real --start-server
```

或：

```bash
make build-kg
```

这一步会：

1. 拆分并校验 120 回章节。
2. 启动 LightRAG Docker 服务。
3. 将章节文本复制到 `data/inputs/`。
4. 调用 LightRAG `/documents/scan`。
5. 轮询处理状态直到图谱构建完成。

这一步会调用 LLM 和 Embedding 服务，会产生费用。

如果图谱已经构建过，只需要启动 LightRAG：

```bash
make lightrag-up
```

LightRAG WebUI 默认地址：

```text
http://127.0.0.1:9621/webui
```

### 4. 启动 Web 应用

```bash
uv run python -m hlm_kg.web_app
```

或：

```bash
make web
```

此时 `问一问` 会读取 `.env` 中的：

- `LIGHTRAG_BASE_URL`
- `LIGHTRAG_TIMEOUT_SECONDS`
- `HLM_ASK_PLANNER_*` 或通用 `LLM_*`
- `HLM_ASK_EVIDENCE_JUDGE_*` 或通用 `LLM_*`

Ask 当前使用 LightRAG `/query/data` 的 `mix` 模式获取结构化证据，再由本项目进行 evidence judge、原文核验和拒答判断；不会直接把 LightRAG `/query` 的生成答案透给用户。

## PostgreSQL 部署模式

默认模式读取 `data/app/*.json`。如果要用 PostgreSQL 承载章节、知识卡、关系和证据，先在 `.env` 中配置：

```bash
DATABASE_URL=postgresql://用户:密码@主机:5432/数据库名
PGVECTOR_AVAILABLE=true
HLM_CONTENT_STORE=postgres
```

初始化数据库：

```bash
uv run python scripts/migrate_postgres.py
uv run python scripts/import_postgres_seed.py
```

或在有裸 `python` 的环境中运行：

```bash
make postgres-migrate
make postgres-import-seed
```

启动 PostgreSQL 模式的 Web 应用：

```bash
HLM_CONTENT_STORE=postgres uv run python -m hlm_kg.web_app
```

更多权限、迁移和单章同步说明见 [docs/postgres_trace_graph.md](docs/postgres_trace_graph.md)。

## 部署到服务器

推荐部署方式：

1. 在服务器上拉取代码。
2. 安装 Python 依赖。
3. 准备 `.env`。
4. 如果需要 Ask 高质量检索，启动并构建 LightRAG。
5. 如需数据库模式，初始化 PostgreSQL 并导入 seed。
6. 用进程管理器启动 Web 应用。
7. 用 Nginx、Caddy、Cloudflare Tunnel 或内网网关转发到 Web 应用端口。

示例启动命令：

```bash
uv run python -m hlm_kg.web_app
```

Web 应用当前绑定 `127.0.0.1`，适合作为本机服务由反向代理转发。不要直接把 `.env`、LightRAG API Key、数据库连接串暴露到公网。

如果需要把 LightRAG 暴露到非本机环境：

- 设置 `LIGHTRAG_API_KEY` 或 LightRAG 的认证配置。
- 不要在无认证情况下把 `HOST` 改成公网可访问的 `0.0.0.0`。
- Web 应用的 `LIGHTRAG_BASE_URL` 应指向后端可访问的 LightRAG API 地址。

## 常用维护命令

拆分章节：

```bash
uv run python -m hlm_kg.chapters
```

分析组卷样例题型：

```bash
uv run python -m hlm_kg.questions
```

校验内部校准样例：

```bash
uv run python -m hlm_kg.validation_samples
```

校验 `问一问` 质量评估数据集：

```bash
uv run python -m hlm_kg.ask_quality_dataset
```

或：

```bash
make validate-ask-quality-dataset
```

构建专题索引：

```bash
uv run python scripts/build_topic_index.py --data-dir data/app --review-cards data/app/chapter_review_cards.json --write
```

运行测试：

```bash
uv run python -m pytest -q
```

## Smoke Test

启动 Web 应用后建议手动检查：

1. 打开终端打印的 URL。
2. 进入 `读一读`，确认能打开第 27 回并看到原文。
3. 进入 `看专题`，确认专题列表不是几千个实体平铺。
4. 打开 `大观园` 或 `螃蟹宴` 专题，确认简介和证据不是模板空话。
5. 在 `问一问` 输入 `林黛玉生的什么病？`，确认回答聚焦病症证据，不跑到宝黛关系。
6. 输入 `林黛玉最喜欢什么颜色？`，如果没有直接证据，应看到证据不足的拒答。
7. 输入 `请帮我写一篇作文`，确认产品拒绝超出《红楼梦》阅读理解范围的请求。
8. 缩小浏览器宽度到移动端尺寸，确认章节、专题和问答页面可用。

## 常见问题

### `make web` 提示找不到 `python`

使用 uv 直接启动：

```bash
uv run python -m hlm_kg.web_app
```

### `问一问` 一直拒答或没有使用 LightRAG

检查 `.env` 是否配置：

```bash
LIGHTRAG_BASE_URL=http://127.0.0.1:9621
LIGHTRAG_TIMEOUT_SECONDS=300
```

并确认 LightRAG 正在运行：

```bash
make lightrag-up
```

### LightRAG 构建结果异常

如果更换了 Embedding 模型、维度、query/document 前缀，必须清空旧索引并重建：

```bash
make lightrag-down
rm -rf data/rag_storage/*
make build-kg
```

执行 `rm -rf data/rag_storage/*` 前确认不需要保留旧图谱。

### PostgreSQL 模式启动失败

检查：

- `.env` 中是否有 `DATABASE_URL`。
- `HLM_CONTENT_STORE=postgres` 是否生效。
- 是否已执行迁移和 seed 导入。
- 数据库账号是否有建表、读写和 sequence 权限。

## 进一步文档

- LightRAG 构建说明：[docs/lightrag_hongloumeng.md](docs/lightrag_hongloumeng.md)
- 章节复习卡流水线：[docs/chapter_review_card_pipeline.md](docs/chapter_review_card_pipeline.md)
- PostgreSQL 数据层：[docs/postgres_trace_graph.md](docs/postgres_trace_graph.md)
- 问题类型盘点：[docs/question_types.md](docs/question_types.md)

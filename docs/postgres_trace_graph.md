# PostgreSQL 信息卡线索数据层

本项目可以使用 PostgreSQL 承载章节、章节卡、信息卡、关系、证据、原文标注和全书线索。PostgreSQL 模式是可选模式；没有配置时仍使用 `data/app/*.json`。

## 环境变量

在本地 `.env` 配置：

```bash
DATABASE_URL=postgresql://用户:密码@主机:5432/数据库名
PGVECTOR_AVAILABLE=true
HLM_CONTENT_STORE=postgres
```

不要提交 `.env`，不要在 Issue、PR 或日志中粘贴真实密码。

## 初始化

先安装项目 Python 依赖：

```bash
python -m pip install -r requirements.txt
```

如果应用账号不是数据库 owner，需要管理员先在目标数据库执行：

```sql
GRANT USAGE, CREATE ON SCHEMA public TO hlm_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO hlm_app;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO hlm_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO hlm_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO hlm_app;
```

```bash
make postgres-migrate
make postgres-import-seed
```

`make postgres-migrate` 会执行 `db/migrations/001_postgres_trace_graph.sql`，创建章节、章节卡、信息卡、关系、证据、原文标注、全书线索和可选向量表。pgvector 可用时会自动启用；不可用时主表仍然可以创建，向量列先用 JSONB 承载，后续可单独迁移。

`make postgres-import-seed` 会把现有 `book/chapters_manifest.json`、`book/chapters/*.txt` 和 `data/app/*.json` 导入 PostgreSQL。导入脚本使用幂等 upsert，可以重复执行。

## 单章章节卡同步

章节卡生成仍先写入 `generated/`，作为人审、校对和可回滚的结构化产物。单章内容通过质量门禁后，可以只同步该章的章节卡到 PostgreSQL：

```bash
python scripts/generate_chapter_cards.py --chapters 27 --overwrite
python scripts/import_chapter_cards.py generated/chapter_review_cards.raw.json generated/chapter_review_cards.checked.json data/app
make sync-chapter-card-postgres CHAPTER=27 INPUT=generated/chapter_cards_import/027.json
```

单章同步只 upsert `chapter_cards` 中对应章节卡，不重建 120 章原文、知识卡、关系或证据。该命令从 `.env` 或环境变量读取 `DATABASE_URL`，错误信息不得输出连接串、密码或 API Key。

## 启动网站

```bash
HLM_CONTENT_STORE=postgres make web
```

章节接口会返回 `annotations`，信息卡接口会返回 `traceItems`。前端用这些结构渲染原文内标注、信息卡侧边栏和线索跳转。

## 数据来源边界

用户可见内容必须来自原文、章节卡、关系或证据数据。资料不足时显示空状态，不用模型常识补全。

## 手动烟测

```bash
python scripts/migrate_postgres.py
python scripts/import_postgres_seed.py
HLM_CONTENT_STORE=postgres python - <<'PY'
from pathlib import Path
from hlm_kg.web_app import create_app_context, handle_api_request

context = create_app_context(
    manifest_path=Path("book/chapters_manifest.json"),
    data_dir=Path("data/app"),
    static_dir=Path("static"),
    use_postgres_store=True,
)
status, chapter = handle_api_request(context, "GET", "/api/chapters/27")
print(status, chapter["chapter"]["number"], len(chapter["originalText"]), len(chapter["annotations"]))
status, card = handle_api_request(context, "GET", "/api/cards/card-lindaiyu")
print(status, card["card"]["name"], len(card["traceItems"]))
PY
```

期望第一行以 `200 27` 开头，第二行以 `200 林黛玉` 开头。不要输出 `DATABASE_URL`。

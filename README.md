# hlm

基于 HKUDS LightRAG Server/WebUI 的《红楼梦》关系图谱应用骨架。

常用命令：

```bash
make env
make split-chapters
make analyze-questions
make dry-run
make web
```

填好 `.env` 中的 LLM 与 Embedding 服务配置后，再运行真实图谱构建：

```bash
make build-kg
```

完整说明见 [docs/lightrag_hongloumeng.md](docs/lightrag_hongloumeng.md)。

提示词定义登记在 `data/prompts/definitions.json`。这里保存提示词名称、版本、用途、输入输出 schema、证据规则和拒答规则，用于约束后续章节复习卡生成与基于证据的问答加工；学生端网页不会直接展示这些提示词定义。

运行 V1 阅读助手网页：

```bash
make web
```

然后打开终端打印的地址；默认是 `http://127.0.0.1:8765`，如果端口被占用会自动使用后续可用端口。

Smoke test the web app:

1. Run `make web`.
2. Open the URL printed by the terminal.
3. Ask `黛玉葬花体现了什么？`; verify the answer shows a short conclusion, source, and 可引用事实.
4. Ask `请帮我写一篇作文`; verify the app refuses because the product only supports 《红楼梦》阅读理解.
5. Open `读章节`; verify chapter 27 shows original text and chapter review material.
6. Open `看专题`; verify the five topic categories appear.
7. Open the `意象伏笔` topic, click `林黛玉`, and verify the visible panel shows 文本理解、理解角度、关系线索、相关章回.
8. Resize below 760px width; verify the knowledge panel remains usable.

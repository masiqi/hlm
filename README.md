# hlm

基于 HKUDS LightRAG Server/WebUI 的《红楼梦》关系图谱应用骨架。

常用命令：

```bash
make env
make split-chapters
make analyze-questions
make dry-run
```

填好 `.env` 中的 LLM 与 Embedding 服务配置后，再运行真实图谱构建：

```bash
make build-kg
```

完整说明见 [docs/lightrag_hongloumeng.md](docs/lightrag_hongloumeng.md)。

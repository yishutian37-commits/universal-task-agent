# RAG + UTA 当前集成交接记录

日期：2026-06-24
分支：`rag-knowledge-base`

## 当前阶段

当前项目已经超过 `rag-v0.2-mvp`。RAG 已经整合进 UTA 主项目，并继续向桌面端和 research 任务链路推进：

1. `rag/` 已位于项目根目录，不再使用旧的 `rag-knowledge-base/` 子目录。
2. RAG 测试已经合并到根目录 `tests/test_rag_*.py`。
3. RAG 已具备 CLI：`ingest/query/ask/list/stats/delete/rebuild`。
4. RAG 已具备 FastAPI：`/health`、`/stats`、`/documents`、`/ingest`、`/query`、`/ask`。
5. 桌面端已接入知识库 Tab，默认内嵌轻量 KB，支持首次打开自动 seed UTA 文档、memory 和 skills。
6. UTA 当前分支已有 research 任务链路：Search Provider、`search_tool`、报告生成、来源校验和 CLI demo；默认使用 Bing HTML 联网搜索。

## 本次收口点

- `desktop.history_store` 改为兼容入口，真实实现迁移到 `core.history_store`，为桌面端/API 复用同一套历史记录读取逻辑做准备。
- 修正 RAG API 的真实模型环境变量：统一使用 `KB_USE_REAL_MODELS`，同时兼容历史错拼 `KB_USE_REAL_MODES`。
- 补齐 `requirements.txt` 中 API 运行/测试依赖：`fastapi`、`uvicorn`、`httpx`。
- 将 research 默认搜索从 fixture 假数据切到 Bing HTML 联网搜索，fixture 只保留给测试/演示。
- 更新 `README.md`、`rag/README.md`、`CHANGELOG.md`，删除用户可见文档里的旧运行路径。
- `.env.example` 新增 `KB_USE_REAL_MODELS` 和 `KB_API_URL`。

## 重要命令

RAG CLI：

```bash
.venv/bin/python -m rag.cli --help
.venv/bin/python -m rag.cli ingest README.md
.venv/bin/python -m rag.cli ask "UTA 当前有哪些能力"
```

RAG API：

```bash
.venv/bin/python -m rag.api
```

research demo：

```bash
.venv/bin/python main.py --task "调研 UTA Agent 路线"
```

测试：

```bash
.venv/bin/python -m pytest -q
```

## 版本标记建议

当前本地已有 RAG tag：`rag-v0.1-skeleton`、`rag-v0.2-mvp`。

建议补：

- `rag-v0.2.5-real-models`
- `rag-v0.3-cli`
- `rag-v0.4-api`
- `rag-v0.5-desktop-integration`

这些 tag 用来补齐版本记录，不代表新增功能。

## 后续建议

下一步先不要继续扩大桌面功能。建议先做两件事：

1. 把当前分支提交并补齐 tag。
2. 再决定 research 任务是继续走 CLI 优先，还是先把桌面端暴露一个“调研任务”入口。

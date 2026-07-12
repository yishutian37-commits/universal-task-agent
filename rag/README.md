# RAG 知识库

RAG 知识库系统，支持 Markdown、TXT、PDF、DOCX 文档摄入、向量检索和 LLM 问答。PDF 必须包含可提取文本；扫描件需要先经过 OCR。当前已经合并进 UTA 主项目根目录，不再使用旧的 `rag-knowledge-base/` 子目录。

## 当前状态

- `v0.1-skeleton`：六层管线骨架（Loader/Chunker/Embedder/VectorStore/Retriever/Generator），全 fake 实现，接口契约确立。
- `v0.2-mvp`：真实管线（TextLoader/FixedChunker/SqliteStore/VectorRetriever），能摄入 MD 文件、检索、生成答案。embedding/generator 为临时实现，真实版本见 v0.2.5。
- `v0.2.5`：真实语义检索（bge-small-zh-v1.5）+ 真实 LLM 答案生成（mimo-v2.5-pro），语义检索准确率远超 hash。
- `v0.3-cli`：提供 `ingest/query/ask/list/stats/delete/rebuild` 命令。
- `v0.4-api`：提供 FastAPI REST 接口：`/health`、`/stats`、`/documents`、`/ingest`、`/query`、`/ask`。
- `desktop-integration`：桌面端已接入知识库 Tab，打包后默认用轻量内嵌模式，并支持首次打开自动 seed UTA 文档、memory 和 skills。

## 架构

分层插件式，每层一个抽象接口。UTA 未来接入只需：

```python
from rag import create_default_kb

kb = create_default_kb()
answer = kb.ask("问题")
```

详细设计见 `docs/superpowers/specs/2026-06-24-rag-knowledge-base-design.md`。

## v0.1 验收

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest tests/test_rag_package.py tests/test_rag_models.py -q
```

预期：六层接口 + KnowledgeBase 编排测试全部通过。本阶段为骨架，真实 Loader/Embedder/Store 实现见 v0.2-mvp。

## v0.2 验收

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest tests/test_rag_*.py -q
```

端到端冒烟（摄入真实 MD 并问答）：

```python
from rag import create_default_kb
kb = create_default_kb(db_path="data/knowledge.db")
kb.ingest_path("notes.md")
ans = kb.ask("UTA 是什么")
print(ans.answer)
```

本阶段能真实摄入 MD 文件并检索问答。真实语义 embedding 和 LLM 生成见 v0.2.5。

## v0.2.5 真实模型

真实语义检索（bge-small-zh）和 LLM 问答（mimo）：

```python
from rag import create_default_kb
kb = create_default_kb(use_real_models=True)
kb.ingest_path("notes.md")
print(kb.ask("问题").answer)
```

需要：`pip install sentence-transformers`（含 torch），且 `.env` 配置了 `LLM_API_KEY`。
首次加载 bge 模型自动走 hf-mirror.com 镜像（HuggingFace 直连超时）。
从临时实现切换时需删 `data/knowledge.db` 重新 ingest（向量语义空间不同）。

## v0.3 CLI

```bash
.venv/bin/python -m rag.cli --help
.venv/bin/python -m rag.cli ingest README.md
.venv/bin/python -m rag.cli query "UTA 是什么"
.venv/bin/python -m rag.cli ask "UTA 当前有哪些能力"
.venv/bin/python -m rag.cli list
.venv/bin/python -m rag.cli stats
```

默认数据库路径是 `data/knowledge.db`，也可以用 `--db-path` 指定临时库：

```bash
.venv/bin/python -m rag.cli --db-path /tmp/uta-rag.db ingest README.md
```

## v0.4 API

启动：

```bash
.venv/bin/python -m rag.api
```

常用环境变量：

```bash
KB_DB_PATH=data/knowledge.db
KB_API_HOST=127.0.0.1
KB_API_PORT=8000
KB_USE_REAL_MODELS=0
```

开发环境要启用真实 bge + mimo 时，把 `KB_USE_REAL_MODELS=1`，并确认 `.env` 里有 `LLM_API_KEY`。为了兼容历史配置，API 也会识别旧的错拼变量 `KB_USE_REAL_MODES`，但新配置统一使用 `KB_USE_REAL_MODELS`。

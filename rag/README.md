# RAG 知识库

独立 RAG 知识库系统，支持文档摄入、向量检索、LLM 问答。CLI 自用 + REST API 给 UTA 接入。

## 当前状态

- `v0.1-skeleton`：六层管线骨架（Loader/Chunker/Embedder/VectorStore/Retriever/Generator），全 fake 实现，接口契约确立。
- `v0.2-mvp`：真实管线（TextLoader/FixedChunker/SqliteStore/VectorRetriever），能摄入 MD 文件、检索、生成答案。embedding/generator 为临时实现，真实版本见 v0.2.5。
- `v0.2.5`：真实语义检索（bge-small-zh-v1.5）+ 真实 LLM 答案生成（mimo-v2.5-pro），语义检索准确率远超 hash。

## 架构

分层插件式，每层一个抽象接口。UTA 未来接入只需：

```python
from rag import KnowledgeBase
kb = KnowledgeBase()
answer = kb.ask("问题")
```

详细设计见 `docs/superpowers/specs/2026-06-24-rag-knowledge-base-design.md`。

## v0.1 验收

```bash
cd rag-knowledge-base
python -m pip install -r requirements.txt
python -m pytest -v
```

预期：六层接口 + KnowledgeBase 编排测试全部通过。本阶段为骨架，真实 Loader/Embedder/Store 实现见 v0.2-mvp。

## v0.2 验收

```bash
cd rag-knowledge-base
python -m pip install -r requirements.txt
python -m pytest -v          # 全量测试通过（71 passed）
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

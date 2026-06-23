# RAG 知识库

独立 RAG 知识库系统，支持文档摄入、向量检索、LLM 问答。CLI 自用 + REST API 给 UTA 接入。

## 当前状态

- `v0.1-skeleton`：六层管线骨架（Loader/Chunker/Embedder/VectorStore/Retriever/Generator），全 fake 实现，接口契约确立。

## 架构

分层插件式，每层一个抽象接口。UTA 未来接入只需：

```python
from rag import KnowledgeBase
kb = KnowledgeBase()
answer = kb.ask("问题")
```

详细设计见 `docs/superpowers/specs/2026-06-24-rag-knowledge-base-design.md`。

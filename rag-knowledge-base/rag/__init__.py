"""RAG 知识库核心库。

UTA 未来接入的唯一入口：

    from rag import KnowledgeBase
    kb = KnowledgeBase()
    answer = kb.ask("问题")
"""

from __future__ import annotations

from rag.kb import KnowledgeBase
from rag.models import Answer, Chunk, Document, RetrievedChunk

__all__ = ["KnowledgeBase", "Answer", "Chunk", "Document", "RetrievedChunk"]

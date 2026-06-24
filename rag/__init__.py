"""RAG 知识库核心库。

UTA 未来接入的唯一入口：

    from rag import KnowledgeBase
    kb = KnowledgeBase()
    answer = kb.ask("问题")
"""

from __future__ import annotations

from rag.defaults import create_default_kb
from rag.kb import KnowledgeBase
from rag.models import Answer, Chunk, Document, RetrievedChunk

__all__ = [
    "KnowledgeBase",
    "create_default_kb",
    "Answer",
    "Chunk",
    "Document",
    "RetrievedChunk",
]

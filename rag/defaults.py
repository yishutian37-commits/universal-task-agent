from __future__ import annotations

from rag.chunkers.fixed_chunker import FixedChunker
from rag.embeddings.hashing_embedder import HashingEmbedder
from rag.generation.echo_generator import EchoGenerator
from rag.kb import KnowledgeBase
from rag.loaders.base import LoaderFactory
from rag.retrieval.vector_retriever import VectorRetriever
from rag.store.sqlite_store import SqliteStore


def create_default_kb(db_path: str = "data/knowledge.db") -> KnowledgeBase:
    """装配 v0.2 默认组件：真实管线 + 临时 embedding/generator。

    - TextLoader（MD/TXT）
    - FixedChunker（512/64）
    - HashingEmbedder（512 维，临时）
    - SqliteStore（持久化）
    - VectorRetriever（numpy 余弦）
    - EchoGenerator（回显，临时）
    """
    embedder = HashingEmbedder(dim=512)
    store = SqliteStore(db_path, dim=embedder.dim)
    return KnowledgeBase(
        loader_factory=LoaderFactory.for_text(),
        chunker=FixedChunker(),
        embedder=embedder,
        store=store,
        retriever=VectorRetriever(),
        generator=EchoGenerator(),
    )

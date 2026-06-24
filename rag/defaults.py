from __future__ import annotations

from rag.chunkers.fixed_chunker import FixedChunker
from rag.kb import KnowledgeBase
from rag.loaders.base import LoaderFactory
from rag.retrieval.vector_retriever import VectorRetriever
from rag.store.sqlite_store import SqliteStore


def create_default_kb(
    db_path: str = "data/knowledge.db",
    use_real_models: bool = False,
) -> KnowledgeBase:
    """装配知识库组件。

    use_real_models=False（默认）：用临时实现（HashingEmbedder + EchoGenerator），
        不依赖模型/网络，适合测试和离线。
    use_real_models=True：用真实实现（LocalEmbedder + LLMGenerator），
        需要已装 torch/sentence-transformers 且配置了 LLM API key。

    切换实现时维度可能变化，需清空旧库重建（delete data/knowledge.db）。
    """
    if use_real_models:
        from rag.embeddings.local_embedder import LocalEmbedder
        from rag.generation.llm_generator import LLMGenerator

        embedder = LocalEmbedder()
        generator = LLMGenerator()
    else:
        from rag.embeddings.hashing_embedder import HashingEmbedder
        from rag.generation.echo_generator import EchoGenerator

        embedder = HashingEmbedder(dim=512)
        generator = EchoGenerator()

    store = SqliteStore(db_path, dim=embedder.dim)
    return KnowledgeBase(
        loader_factory=LoaderFactory.for_text(),
        chunker=FixedChunker(),
        embedder=embedder,
        store=store,
        retriever=VectorRetriever(),
        generator=generator,
    )

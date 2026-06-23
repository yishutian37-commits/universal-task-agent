from __future__ import annotations

import os
import uuid
from datetime import datetime

from rag.chunkers.base import BaseChunker
from rag.embeddings.base import BaseEmbedder
from rag.errors import EmptyStoreError
from rag.generation.base import BaseGenerator
from rag.loaders.base import LoaderFactory
from rag.models import Answer, Document, RetrievedChunk
from rag.retrieval.base import BaseRetriever
from rag.store.base import BaseVectorStore


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class KnowledgeBase:
    """RAG 知识库编排类——唯一知道全部六层的入口。

    UTA 未来接入只需实例化本类，调用 ingest_path / query / ask。
    """

    def __init__(
        self,
        loader_factory: LoaderFactory,
        chunker: BaseChunker,
        embedder: BaseEmbedder,
        store: BaseVectorStore,
        retriever: BaseRetriever,
        generator: BaseGenerator,
    ) -> None:
        self.loader_factory = loader_factory
        self.chunker = chunker
        self.embedder = embedder
        self._store = store
        self.retriever = retriever
        self.generator = generator

    @classmethod
    def from_config(cls, db_path: str = "data/knowledge.db") -> "KnowledgeBase":
        """无参装配：用 v0.2 默认组件创建实例。"""
        from rag.defaults import create_default_kb

        return create_default_kb(db_path=db_path)

    def ingest_path(self, source: str) -> dict:
        """摄入单个来源（文件路径）：加载→切片→嵌入→存储，幂等。"""
        loader = self.loader_factory.get(source)
        loaded = loader.load(source)

        doc_id = str(uuid.uuid4())
        # 幂等：先删旧的同源 chunk
        self._store.delete_by_source(source)

        chunks = self.chunker.chunk_text(loaded.text, doc_id, source)
        vectors = self.embedder.embed([c.text for c in chunks])
        self._store.add(chunks, vectors)

        doc = Document(
            doc_id=doc_id,
            source=source,
            title=loaded.metadata.get("title", os.path.basename(source)),
            type=loaded.metadata.get("type", os.path.splitext(source)[1].lstrip(".")),
            chunk_count=len(chunks),
            ingested_at=_now_iso(),
            metadata=loaded.metadata,
        )
        self._store.upsert_doc(doc)

        return {"doc_id": doc_id, "chunk_count": len(chunks), "source": source}

    def query(self, question: str, top_k: int = 5) -> list[RetrievedChunk]:
        """只检索，返回 top-k 片段（不调 LLM）。空库抛 EmptyStoreError。"""
        if self._store.count() == 0:
            raise EmptyStoreError("知识库为空，请先 ingest 文档")

        query_vec = self.embedder.embed([question])[0]
        vectors, chunks = self._store.all_vectors()
        if not chunks:
            raise EmptyStoreError("知识库为空，请先 ingest 文档")
        return self.retriever.search(vectors, chunks, query_vec, top_k)

    def ask(self, question: str, top_k: int = 5) -> Answer:
        """端到端问答：检索 → 生成，返回带来源引用的答案。"""
        retrieved = self.query(question, top_k=top_k)
        contexts = [r.chunk for r in retrieved]
        answer_text = self.generator.generate(question, contexts)
        return Answer(answer=answer_text, sources=retrieved)

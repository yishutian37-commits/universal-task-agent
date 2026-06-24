from __future__ import annotations

import uuid

import pytest

from rag.chunkers.base import BaseChunker
from rag.embeddings.base import BaseEmbedder
from rag.generation.base import BaseGenerator
from rag.loaders.base import BaseLoader, LoadedDoc, LoaderFactory
from rag.models import Chunk, Document, RetrievedChunk
from rag.retrieval.base import BaseRetriever
from rag.store.base import BaseVectorStore


class FakeLoader(BaseLoader):
    def __init__(self, text: str = "示例文本内容") -> None:
        self._text = text

    def load(self, source: str) -> LoadedDoc:
        return LoadedDoc(text=self._text, source=source, metadata={"type": "md"})


class FakeChunker(BaseChunker):
    def chunk_text(self, text, doc_id, source):
        # 简单按句号切
        pieces = [p for p in text.split("。") if p]
        if not pieces:
            pieces = [text]
        return [
            Chunk(
                chunk_id=str(uuid.uuid4()),
                doc_id=doc_id,
                source=source,
                chunk_index=i,
                text=p,
                metadata={},
            )
            for i, p in enumerate(pieces)
        ]


class FakeEmbedder(BaseEmbedder):
    @property
    def dim(self) -> int:
        return 3

    def embed(self, texts):
        return [
            [float(len(t) % 10), float(i), 0.0] for i, t in enumerate(texts)
        ]


class FakeStore(BaseVectorStore):
    def __init__(self) -> None:
        self.chunks: list[Chunk] = []
        self.vectors: list[list[float]] = []
        self.docs: dict[str, Document] = {}

    def add(self, chunks, vectors):
        self.chunks.extend(chunks)
        self.vectors.extend(vectors)
        return len(chunks)

    def delete_by_source(self, source):
        before = len(self.chunks)
        keep = [
            (v, c) for v, c in zip(self.vectors, self.chunks) if c.source != source
        ]
        self.vectors = [v for v, _ in keep]
        self.chunks = [c for _, c in keep]
        return before - len(self.chunks)

    def delete_doc(self, doc_id):
        before = len(self.chunks)
        keep = [
            (v, c) for v, c in zip(self.vectors, self.chunks) if c.doc_id != doc_id
        ]
        self.vectors = [v for v, _ in keep]
        self.chunks = [c for _, c in keep]
        self.docs.pop(doc_id, None)
        return before - len(self.chunks)

    def upsert_doc(self, doc):
        self.docs[doc.doc_id] = doc

    def list_docs(self):
        return list(self.docs.values())

    def all_vectors(self):
        return self.vectors, self.chunks

    def count(self):
        return len(self.chunks)

    def clear(self):
        self.chunks = []
        self.vectors = []
        self.docs = {}


class FakeRetriever(BaseRetriever):
    def search(self, vectors, chunks, query_vec, top_k):
        scored = [
            (sum((a - b) ** 2 for a, b in zip(v, query_vec)), c)
            for v, c in zip(vectors, chunks)
        ]
        scored.sort(key=lambda x: x[0])  # 距离越小越相似
        return [RetrievedChunk(chunk=c, score=-d) for d, c in scored[:top_k]]


class FakeGenerator(BaseGenerator):
    def generate(self, question, contexts):
        refs = ", ".join(c.source for c in contexts)
        return f"答案（来源 {refs}）：关于「{question}」"


@pytest.fixture
def fake_components():
    """返回一组 fake 组件，供 KnowledgeBase 装配测试。"""
    store = FakeStore()
    return {
        "loader_factory": LoaderFactory(
            {".md": FakeLoader("第一句。第二句。第三句。")}
        ),
        "chunker": FakeChunker(),
        "embedder": FakeEmbedder(),
        "store": store,
        "retriever": FakeRetriever(),
        "generator": FakeGenerator(),
    }

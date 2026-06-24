from __future__ import annotations

from rag.models import Chunk, RetrievedChunk
from rag.retrieval.base import BaseRetriever


class _FakeRetriever(BaseRetriever):
    """fake：按向量第一维大小排序，取 top-k。"""

    def search(self, vectors, chunks, query_vec, top_k):
        scored = [
            RetrievedChunk(chunk=c, score=query_vec[0] + v[0])
            for v, c in zip(vectors, chunks)
        ]
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:top_k]


def test_search_returns_top_k_sorted():
    retriever = _FakeRetriever()
    chunks = [Chunk(f"c{i}", "d", "s", i, f"t{i}", {}) for i in range(3)]
    vectors = [[0.1], [0.9], [0.5]]
    results = retriever.search(vectors, chunks, [1.0], top_k=2)
    assert len(results) == 2
    assert results[0].score >= results[1].score
    assert results[0].chunk.text == "t1"

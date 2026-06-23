from __future__ import annotations

from rag.models import Chunk
from rag.retrieval.vector_retriever import VectorRetriever


def _chunk(idx, text):
    return Chunk(f"c{idx}", "d", "s", idx, text, {})


def test_exact_match_scores_highest():
    retriever = VectorRetriever()
    query = [1.0, 0.0, 0.0]
    vectors = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    chunks = [_chunk(i, f"t{i}") for i in range(3)]
    results = retriever.search(vectors, chunks, query, top_k=1)
    assert results[0].chunk.text == "t0"
    assert results[0].score > 0.99


def test_top_k_limits_results():
    retriever = VectorRetriever()
    query = [1.0, 0.0]
    vectors = [[1.0, 0.0], [0.9, 0.1], [0.1, 0.9]]
    chunks = [_chunk(i, f"t{i}") for i in range(3)]
    results = retriever.search(vectors, chunks, query, top_k=2)
    assert len(results) == 2


def test_results_sorted_by_score_desc():
    retriever = VectorRetriever()
    query = [1.0, 0.0]
    vectors = [[0.1, 0.9], [0.99, 0.01], [0.5, 0.5]]
    chunks = [_chunk(i, f"t{i}") for i in range(3)]
    results = retriever.search(vectors, chunks, query, top_k=3)
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_empty_vectors_returns_empty():
    retriever = VectorRetriever()
    results = retriever.search([], [], [1.0, 0.0], top_k=5)
    assert results == []


def test_top_k_larger_than_pool():
    retriever = VectorRetriever()
    query = [1.0, 0.0]
    vectors = [[1.0, 0.0]]
    chunks = [_chunk(0, "only")]
    results = retriever.search(vectors, chunks, query, top_k=10)
    assert len(results) == 1


def test_orthogonal_scores_zero():
    retriever = VectorRetriever()
    query = [1.0, 0.0]
    vectors = [[0.0, 1.0]]
    chunks = [_chunk(0, "ortho")]
    results = retriever.search(vectors, chunks, query, top_k=1)
    assert abs(results[0].score) < 0.01

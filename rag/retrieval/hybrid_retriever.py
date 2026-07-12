from __future__ import annotations

import math
import re
from collections import Counter

from rag.models import Chunk, RetrievedChunk
from rag.retrieval.base import BaseRetriever
from rag.retrieval.vector_retriever import VectorRetriever


class HybridRetriever(BaseRetriever):
    """融合向量相似度与 BM25 关键词相关度。"""

    def __init__(self, vector_weight: float = 0.35, keyword_weight: float = 0.65) -> None:
        self.vector_weight = float(vector_weight)
        self.keyword_weight = float(keyword_weight)
        self.vector_retriever = VectorRetriever()

    def search(
        self,
        vectors: list[list[float]],
        chunks: list[Chunk],
        query_vec: list[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        return self.vector_retriever.search(vectors, chunks, query_vec, top_k)

    def search_with_text(
        self,
        vectors: list[list[float]],
        chunks: list[Chunk],
        query_vec: list[float],
        query_text: str,
        top_k: int,
    ) -> list[RetrievedChunk]:
        if not chunks:
            return []
        vector_results = self.vector_retriever.search(vectors, chunks, query_vec, len(chunks))
        vector_scores = {item.chunk.chunk_id: max(0.0, float(item.score)) for item in vector_results}
        keyword_scores = _bm25_scores(query_text, chunks)
        vector_max = max(vector_scores.values(), default=1.0) or 1.0
        keyword_max = max(keyword_scores.values(), default=1.0) or 1.0
        combined = [
            RetrievedChunk(
                chunk=chunk,
                score=(
                    self.vector_weight * vector_scores.get(chunk.chunk_id, 0.0) / vector_max
                    + self.keyword_weight * keyword_scores.get(chunk.chunk_id, 0.0) / keyword_max
                ),
            )
            for chunk in chunks
        ]
        combined.sort(key=lambda item: item.score, reverse=True)
        return combined[: min(max(0, int(top_k)), len(combined))]


def search_tokens(text: str) -> list[str]:
    normalized = str(text or "").casefold()
    ascii_tokens = re.findall(r"[a-z0-9_+-]{2,}", normalized)
    chinese_runs = re.findall(r"[\u4e00-\u9fff]+", normalized)
    chinese_tokens: list[str] = []
    for run in chinese_runs:
        if len(run) <= 2:
            chinese_tokens.append(run)
        else:
            chinese_tokens.extend(run[index : index + 2] for index in range(len(run) - 1))
    return ascii_tokens + chinese_tokens


def _bm25_scores(query: str, chunks: list[Chunk]) -> dict[str, float]:
    query_terms = search_tokens(query)
    if not query_terms or not chunks:
        return {chunk.chunk_id: 0.0 for chunk in chunks}
    documents = [search_tokens(chunk.text) for chunk in chunks]
    average_length = sum(len(document) for document in documents) / max(1, len(documents))
    document_frequency = Counter(
        term
        for document in documents
        for term in set(document)
    )
    scores: dict[str, float] = {}
    k1 = 1.5
    b = 0.75
    for chunk, document in zip(chunks, documents):
        frequencies = Counter(document)
        score = 0.0
        for term in query_terms:
            frequency = frequencies.get(term, 0)
            if not frequency:
                continue
            doc_frequency = document_frequency.get(term, 0)
            inverse_frequency = math.log(1 + (len(documents) - doc_frequency + 0.5) / (doc_frequency + 0.5))
            denominator = frequency + k1 * (1 - b + b * len(document) / max(1.0, average_length))
            score += inverse_frequency * frequency * (k1 + 1) / denominator
        scores[chunk.chunk_id] = score
    return scores

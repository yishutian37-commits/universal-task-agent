from __future__ import annotations

from rag.models import RetrievedChunk
from rag.retrieval.hybrid_retriever import search_tokens


class KeywordDiversityReranker:
    """按查询词覆盖率重排，并轻微降低同源片段连续占位。"""

    def rerank(
        self,
        question: str,
        candidates: list[RetrievedChunk],
        top_k: int,
    ) -> list[RetrievedChunk]:
        query_tokens = set(search_tokens(question))
        ranked: list[RetrievedChunk] = []
        source_counts: dict[str, int] = {}
        remaining = list(candidates)
        while remaining and len(ranked) < top_k:
            best_index = 0
            best_score = float("-inf")
            for index, item in enumerate(remaining):
                text_tokens = set(search_tokens(item.chunk.text))
                coverage = len(query_tokens & text_tokens) / max(1, len(query_tokens))
                source_penalty = 0.04 * source_counts.get(item.chunk.source, 0)
                score = float(item.score) + 0.35 * coverage - source_penalty
                if score > best_score:
                    best_index = index
                    best_score = score
            selected = remaining.pop(best_index)
            ranked.append(RetrievedChunk(chunk=selected.chunk, score=best_score))
            source_counts[selected.chunk.source] = source_counts.get(selected.chunk.source, 0) + 1
        return ranked

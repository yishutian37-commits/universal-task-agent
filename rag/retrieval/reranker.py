from __future__ import annotations

import re

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
        query_named_tokens = set(re.findall(r"[a-z0-9_]{2,}", str(question or "").casefold()))
        ranked: list[RetrievedChunk] = []
        source_counts: dict[str, int] = {}
        remaining = list(candidates)
        while remaining and len(ranked) < top_k:
            best_index = 0
            best_score = float("-inf")
            for index, item in enumerate(remaining):
                text_tokens = set(search_tokens(item.chunk.text))
                coverage = len(query_tokens & text_tokens) / max(1, len(query_tokens))
                source_tokens = set(
                    re.findall(r"[a-z0-9_]{2,}", str(item.chunk.source or "").casefold())
                )
                named_matches = query_named_tokens & (text_tokens | source_tokens)
                named_coverage = len(named_matches) / max(1, len(query_named_tokens))
                named_bonus = 0.55 * named_coverage if query_named_tokens else 0.0
                missing_named_penalty = (
                    0.45 if query_named_tokens and not named_matches else 0.0
                )
                source_bonus = 0.18 if query_named_tokens & source_tokens else 0.0
                source_penalty = 0.04 * source_counts.get(item.chunk.source, 0)
                score = (
                    float(item.score)
                    + 0.35 * coverage
                    + named_bonus
                    + source_bonus
                    - missing_named_penalty
                    - source_penalty
                )
                if score > best_score:
                    best_index = index
                    best_score = score
            selected = remaining.pop(best_index)
            ranked.append(RetrievedChunk(chunk=selected.chunk, score=best_score))
            source_counts[selected.chunk.source] = source_counts.get(selected.chunk.source, 0) + 1
        return ranked

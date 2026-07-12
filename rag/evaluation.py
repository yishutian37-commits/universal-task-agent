from __future__ import annotations

from pathlib import Path
from typing import Any


def evaluate_retrieval(kb, cases: list[dict[str, Any]], *, top_k: int = 3) -> dict[str, Any]:
    results = []
    reciprocal_ranks = []
    for case in cases:
        question = str(case.get("question") or "")
        expected_source = str(case.get("expected_source") or "")
        retrieved = kb.query(question, top_k=top_k)
        sources = [Path(item.chunk.source).name for item in retrieved]
        rank = next((index for index, source in enumerate(sources, start=1) if source == expected_source), None)
        reciprocal_rank = 1.0 / rank if rank else 0.0
        reciprocal_ranks.append(reciprocal_rank)
        results.append(
            {
                "id": str(case.get("id") or "case"),
                "question": question,
                "expected_source": expected_source,
                "retrieved_sources": sources,
                "rank": rank,
                "passed": rank is not None,
            }
        )
    total = len(results)
    hits = sum(1 for result in results if result["passed"])
    return {
        "total": total,
        "passed": hits,
        "failed": total - hits,
        "top_k": top_k,
        "hit_at_k": round(hits / total, 4) if total else 0.0,
        "mrr": round(sum(reciprocal_ranks) / total, 4) if total else 0.0,
        "results": results,
    }

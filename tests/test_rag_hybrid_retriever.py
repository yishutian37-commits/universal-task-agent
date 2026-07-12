from rag.models import Chunk
from rag.retrieval.hybrid_retriever import HybridRetriever


def _chunk(index, text, source):
    return Chunk(f"c{index}", f"d{index}", source, index, text, {})


def test_hybrid_retriever_prefers_exact_keyword_when_vectors_tie():
    retriever = HybridRetriever()
    vectors = [[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]]
    chunks = [
        _chunk(0, "普通任务可以保存状态", "general.md"),
        _chunk(1, "checkpoint 可以恢复未完成任务", "checkpoint.md"),
        _chunk(2, "天气查询使用实时接口", "weather.md"),
    ]

    results = retriever.search_with_text(
        vectors,
        chunks,
        [1.0, 0.0],
        "如何从 checkpoint 恢复任务",
        top_k=2,
    )

    assert results[0].chunk.source == "checkpoint.md"
    assert len(results) == 2

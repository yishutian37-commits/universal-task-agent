from rag.models import Chunk, RetrievedChunk
from rag.retrieval.hybrid_retriever import HybridRetriever
from rag.retrieval.reranker import KeywordDiversityReranker


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


def test_reranker_uses_source_filename_to_disambiguate_named_topic():
    candidates = [
        RetrievedChunk(_chunk(0, "如何构建智能体", "08-agent-interfaces.md"), 0.8),
        RetrievedChunk(_chunk(1, "如何构建知识库", "rag-knowledge-base-design.md"), 0.8),
    ]

    results = KeywordDiversityReranker().rerank("RAG 如何构建", candidates, top_k=2)

    assert results[0].chunk.source == "rag-knowledge-base-design.md"


def test_reranker_requires_named_topic_instead_of_only_matching_question_words():
    candidates = [
        RetrievedChunk(_chunk(0, "如何构建智能体并操作真实环境", "agent-interfaces.md"), 0.95),
        RetrievedChunk(_chunk(1, "RAG 基础流水线：加载、切片、向量化、检索和生成", "memory-rag.md"), 0.55),
    ]

    results = KeywordDiversityReranker().rerank("RAG 如何构建", candidates, top_k=2)

    assert results[0].chunk.source == "memory-rag.md"

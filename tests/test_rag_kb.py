from __future__ import annotations

import pytest

from rag.errors import EmptyStoreError
from rag.kb import KnowledgeBase, _lexical_overlap
from rag.models import Chunk, RetrievedChunk


def test_ask_on_empty_store_raises(fake_components):
    kb = KnowledgeBase(**fake_components)
    with pytest.raises(EmptyStoreError):
        kb.ask("任何问题")


def test_query_on_empty_store_raises(fake_components):
    kb = KnowledgeBase(**fake_components)
    with pytest.raises(EmptyStoreError):
        kb.query("任何问题")


def test_ingest_then_ask_roundtrip(fake_components):
    kb = KnowledgeBase(**fake_components)
    result = kb.ingest_path("notes.md")
    assert result["chunk_count"] > 0
    assert result["source"] == "notes.md"

    answer = kb.ask("问题")
    assert "notes.md" in answer.answer
    assert len(answer.sources) > 0


def test_ingest_is_idempotent(fake_components):
    kb = KnowledgeBase(**fake_components)
    kb.ingest_path("notes.md")
    first_count = kb._store.count()

    kb.ingest_path("notes.md")  # 重复摄入
    second_count = kb._store.count()

    assert second_count == first_count  # 不应翻倍


def test_query_returns_chunks_without_llm(fake_components):
    kb = KnowledgeBase(**fake_components)
    kb.ingest_path("notes.md")
    chunks = kb.query("问题", top_k=2)
    assert len(chunks) <= 2
    assert all(hasattr(c, "score") for c in chunks)


def test_query_with_neighbors_expands_contiguous_chunks_from_hit_source(fake_components):
    kb = KnowledgeBase(**fake_components)
    kb.ingest_path("notes.md")

    chunks = kb.query_with_neighbors("问题", top_k=1, neighbor_window=1, max_sources=1)
    indexes = [item.chunk.chunk_index for item in chunks]

    assert len(chunks) >= 2
    assert indexes == list(range(min(indexes), max(indexes) + 1))
    assert {item.chunk.source for item in chunks} == {"notes.md"}


def test_query_with_neighbors_excludes_weak_secondary_sources(fake_components, monkeypatch):
    kb = KnowledgeBase(**fake_components)
    relevant = Chunk("c1", "d1", "rag-design.md", 0, "RAG 构建方案", {})
    supporting = Chunk("c2", "d2", "rag-guide.md", 0, "RAG 实施步骤", {})
    unrelated = Chunk("c3", "d3", "agent-interfaces.md", 0, "如何构建浏览器 Agent", {})
    hits = [
        RetrievedChunk(relevant, 1.0),
        RetrievedChunk(supporting, 0.85),
        RetrievedChunk(unrelated, 0.70),
    ]
    monkeypatch.setattr(kb, "query", lambda question, top_k: hits[:top_k])
    monkeypatch.setattr(
        kb._store,
        "all_vectors",
        lambda: ([[1.0], [0.8], [0.5]], [relevant, supporting, unrelated]),
    )

    chunks = kb.query_with_neighbors(
        "RAG 如何构建",
        top_k=3,
        neighbor_window=0,
        max_sources=3,
    )

    assert {item.chunk.source for item in chunks} == {"rag-design.md", "rag-guide.md"}
    assert "agent-interfaces.md" not in {item.chunk.source for item in chunks}


def test_lexical_overlap_rewards_exact_english_and_chinese_terms():
    relevant = _lexical_overlap("UTA 如何保存长期记忆", "UTA 支持会话压缩和长期记忆管理")
    unrelated = _lexical_overlap("UTA 如何保存长期记忆", "今天的天气适合出门")

    assert relevant > unrelated
    assert relevant > 0

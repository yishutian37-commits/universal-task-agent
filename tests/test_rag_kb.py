from __future__ import annotations

import pytest

from rag.errors import EmptyStoreError
from rag.kb import KnowledgeBase, _lexical_overlap


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


def test_lexical_overlap_rewards_exact_english_and_chinese_terms():
    relevant = _lexical_overlap("UTA 如何保存长期记忆", "UTA 支持会话压缩和长期记忆管理")
    unrelated = _lexical_overlap("UTA 如何保存长期记忆", "今天的天气适合出门")

    assert relevant > unrelated
    assert relevant > 0

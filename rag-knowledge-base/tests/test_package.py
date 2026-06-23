from __future__ import annotations

import rag


def test_knowledgebase_exported():
    assert hasattr(rag, "KnowledgeBase")


def test_models_exported():
    for name in ["Answer", "Chunk", "Document", "RetrievedChunk"]:
        assert hasattr(rag, name)


def test_all_list_consistent():
    for name in rag.__all__:
        assert hasattr(rag, name)

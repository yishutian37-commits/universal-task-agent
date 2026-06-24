from __future__ import annotations

from rag.embeddings.hashing_embedder import HashingEmbedder


def test_dim_is_configurable():
    emb = HashingEmbedder(dim=64)
    assert emb.dim == 64


def test_embed_returns_correct_shape():
    emb = HashingEmbedder(dim=8)
    vectors = emb.embed(["hello", "world", "foo"])
    assert len(vectors) == 3
    assert all(len(v) == 8 for v in vectors)


def test_same_text_same_vector():
    emb = HashingEmbedder(dim=16)
    a = emb.embed(["text"])[0]
    b = emb.embed(["text"])[0]
    assert a == b  # 确定性


def test_different_text_different_vector():
    emb = HashingEmbedder(dim=16)
    a = emb.embed(["apple"])[0]
    b = emb.embed(["banana"])[0]
    assert a != b


def test_batch_order_preserved():
    emb = HashingEmbedder(dim=8)
    vectors = emb.embed(["a", "b", "c"])
    single = emb.embed(["b"])[0]
    assert vectors[1] == single  # 批量结果和单条一致


def test_empty_input_returns_empty():
    emb = HashingEmbedder(dim=8)
    assert emb.embed([]) == []

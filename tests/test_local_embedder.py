from __future__ import annotations

import pytest

from rag.embeddings.local_embedder import LocalEmbedder


@pytest.mark.integration
class TestLocalEmbedder:
    """真实模型测试，需本地有模型缓存或网络。CI 跳过。"""

    def test_dim_is_512(self):
        emb = LocalEmbedder()
        assert emb.dim == 512

    def test_embed_returns_vectors(self):
        emb = LocalEmbedder()
        vectors = emb.embed(["如何处理报错", "错误排查"])
        assert len(vectors) == 2
        assert all(len(v) == 512 for v in vectors)

    def test_semantic_similarity(self):
        """语义相近的文本，向量余弦相似度应高于不相关的。"""
        emb = LocalEmbedder()
        vecs = emb.embed(["如何处理报错", "错误排查方法", "今天天气真好"])
        import numpy as np

        a, b, c = [np.asarray(v) for v in vecs]
        sim_ab = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
        sim_ac = float(np.dot(a, c) / (np.linalg.norm(a) * np.linalg.norm(c)))
        # "报错"和"错误排查"应比"报错"和"天气"更相似
        assert sim_ab > sim_ac

    def test_empty_input_returns_empty(self):
        emb = LocalEmbedder()
        assert emb.embed([]) == []

    def test_deterministic(self):
        emb = LocalEmbedder()
        a = emb.embed(["测试文本"])[0]
        b = emb.embed(["测试文本"])[0]
        assert a == b

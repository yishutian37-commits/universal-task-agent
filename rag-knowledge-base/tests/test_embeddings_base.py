from __future__ import annotations

from rag.embeddings.base import BaseEmbedder


class _FakeEmbedder(BaseEmbedder):
    """fake：把每个字符的 ord 编码成定长向量。"""

    @property
    def dim(self) -> int:
        return 4

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [
            [float(ord(c)) for c in t[: self.dim]]
            + [0.0] * (self.dim - len(t))
            for t in texts
        ]


def test_embedder_returns_equal_length():
    emb = _FakeEmbedder()
    vectors = emb.embed(["ab", "c"])
    assert len(vectors) == 2
    assert all(len(v) == emb.dim for v in vectors)


def test_embedder_dim_is_constant():
    emb = _FakeEmbedder()
    assert emb.dim == 4

from __future__ import annotations

import hashlib


class HashingEmbedder:
    """确定性 hash 嵌入——v0.2 临时实现。

    用 SHA256 把文本稳定映射到固定维度向量。相同文本必出相同向量，
    不同文本大概率不同。这不是语义嵌入，仅用于让管线跑通。
    真实语义嵌入（bge / API）留 v0.2.5。
    """

    def __init__(self, dim: int = 512) -> None:
        if dim <= 0:
            raise ValueError("dim 必须为正数")
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        # 循环扩展 hash 字节直到填满 dim
        needed = self._dim
        raw = b""
        counter = 0
        while len(raw) < needed:
            raw += hashlib.sha256(f"{counter}:{text}".encode("utf-8")).digest()
            counter += 1
        # 取前 dim 字节，归一化到 [-1, 1]
        return [((b / 255.0) * 2 - 1) for b in raw[:needed]]

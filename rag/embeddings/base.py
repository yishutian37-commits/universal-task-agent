from __future__ import annotations

from abc import ABC, abstractmethod


class BaseEmbedder(ABC):
    """嵌入接口。把文本批量转成向量。dim 是契约——建库后不可变。"""

    @property
    @abstractmethod
    def dim(self) -> int:
        """向量维度，建库时锁定。"""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量嵌入，返回与输入等长的向量列表。"""

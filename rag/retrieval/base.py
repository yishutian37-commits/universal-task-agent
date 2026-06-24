from __future__ import annotations

from abc import ABC, abstractmethod

from rag.models import Chunk, RetrievedChunk


class BaseRetriever(ABC):
    """检索接口。输入查询向量 + 全量向量，返回带分的 top-k 片段。"""

    @abstractmethod
    def search(
        self,
        vectors: list[list[float]],
        chunks: list[Chunk],
        query_vec: list[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        """在给定向量集中检索，返回按相似度排序的 top-k 结果。"""

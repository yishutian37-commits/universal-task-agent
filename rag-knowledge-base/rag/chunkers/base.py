from __future__ import annotations

from abc import ABC, abstractmethod

from rag.models import Chunk


class BaseChunker(ABC):
    """文本切片接口。把纯文本切成带索引的 Chunk 列表。"""

    @abstractmethod
    def chunk_text(
        self, text: str, doc_id: str, source: str
    ) -> list[Chunk]:
        """把文本切片，返回带 chunk_id/doc_id/chunk_index 的片段列表。"""

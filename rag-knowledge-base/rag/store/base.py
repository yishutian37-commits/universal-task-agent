from __future__ import annotations

from abc import ABC, abstractmethod

from rag.models import Chunk, Document


class BaseVectorStore(ABC):
    """向量存储接口。管理 chunks、向量和文档元数据，支持幂等去重。"""

    @abstractmethod
    def add(self, chunks: list[Chunk], vectors: list[list[float]]) -> int:
        """写入切片和对应向量，返回写入条数。"""

    @abstractmethod
    def delete_by_source(self, source: str) -> int:
        """按来源删除所有 chunk（幂等摄入用），返回删除条数。"""

    @abstractmethod
    def delete_doc(self, doc_id: str) -> int:
        """按 doc_id 删除文档及其 chunk，返回删除条数。"""

    @abstractmethod
    def upsert_doc(self, doc: Document) -> None:
        """写入或更新文档元数据。"""

    @abstractmethod
    def list_docs(self) -> list[Document]:
        """列出库内所有文档。"""

    @abstractmethod
    def all_vectors(self) -> tuple[list[list[float]], list[Chunk]]:
        """返回全部向量和对应 chunk，供检索层批量读取。"""

    @abstractmethod
    def count(self) -> int:
        """返回库内 chunk 总数。"""

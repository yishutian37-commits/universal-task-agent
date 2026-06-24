"""RAG 知识库统一异常层级。快失败、明确报错、不静默吞。"""

from __future__ import annotations


class KnowledgeBaseError(Exception):
    """RAG 知识库所有异常的基类。"""


class UnsupportedSourceError(KnowledgeBaseError):
    """Loader 不支持的文件扩展名或来源类型。"""


class EmbedderMismatchError(KnowledgeBaseError):
    """Embedder 维度与已建库的维度不一致，需重建库。"""


class EmptyStoreError(KnowledgeBaseError):
    """知识库为空时执行 query/ask，需先 ingest。"""


class IngestError(KnowledgeBaseError):
    """文档摄入失败（文件读不出、切片失败、写入异常等）。"""


class LLMError(KnowledgeBaseError):
    """LLM 调用失败（超时、网络错误、响应无效等）。"""

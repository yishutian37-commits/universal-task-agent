from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Document:
    """摄入文档的元数据记录，对应 documents 表。"""

    doc_id: str
    source: str
    title: str
    type: str
    chunk_count: int
    ingested_at: str
    metadata: dict = field(default_factory=dict)


@dataclass
class Chunk:
    """切片后的文本片段。"""

    chunk_id: str
    doc_id: str
    source: str
    chunk_index: int
    text: str
    metadata: dict = field(default_factory=dict)


@dataclass
class RetrievedChunk:
    """检索命中的片段，附带相似度分。"""

    chunk: Chunk
    score: float


@dataclass
class Answer:
    """端到端问答结果，含答案和来源引用。"""

    answer: str
    sources: list[RetrievedChunk] = field(default_factory=list)

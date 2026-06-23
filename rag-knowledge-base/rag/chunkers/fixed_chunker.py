from __future__ import annotations

import uuid

from rag.models import Chunk


class FixedChunker:
    """按字符数定长切片，支持重叠。

    默认 chunk_size=512, overlap=64（对齐 spec）。
    step = chunk_size - overlap，保证相邻切片有 overlap 字符重叠。
    """

    def __init__(self, chunk_size: int = 512, overlap: int = 64) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size 必须为正数")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap 必须满足 0 <= overlap < chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_text(self, text: str, doc_id: str, source: str) -> list[Chunk]:
        if not text:
            return []

        step = self.chunk_size - self.overlap
        chunks: list[Chunk] = []
        index = 0
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            piece = text[start:end]
            chunks.append(
                Chunk(
                    chunk_id=str(uuid.uuid4()),
                    doc_id=doc_id,
                    source=source,
                    chunk_index=index,
                    text=piece,
                    metadata={},
                )
            )
            index += 1
            start += step
        return chunks

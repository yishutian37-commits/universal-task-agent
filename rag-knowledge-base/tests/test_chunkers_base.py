from __future__ import annotations

from rag.chunkers.base import BaseChunker
from rag.models import Chunk


class _DoubleChunker(BaseChunker):
    """fake：把文本按 2 字符切片，无重叠。"""

    def chunk_text(self, text: str, doc_id: str, source: str) -> list[Chunk]:
        pieces = [text[i : i + 2] for i in range(0, len(text), 2)]
        return [
            Chunk(
                chunk_id=f"{doc_id}-{i}",
                doc_id=doc_id,
                source=source,
                chunk_index=i,
                text=p,
                metadata={},
            )
            for i, p in enumerate(pieces)
        ]


def test_chunker_returns_chunks():
    chunker = _DoubleChunker()
    chunks = chunker.chunk_text("abcdef", "d1", "a.md")
    assert len(chunks) == 3
    assert chunks[0].text == "ab"
    assert chunks[2].chunk_index == 2

from __future__ import annotations

from rag.chunkers.fixed_chunker import FixedChunker


def test_short_text_single_chunk():
    chunker = FixedChunker(chunk_size=100, overlap=0)
    chunks = chunker.chunk_text("短文本", "d1", "a.md")
    assert len(chunks) == 1
    assert chunks[0].text == "短文本"
    assert chunks[0].chunk_index == 0


def test_splits_long_text():
    chunker = FixedChunker(chunk_size=10, overlap=0)
    text = "0123456789" * 3  # 30 字符
    chunks = chunker.chunk_text(text, "d1", "a.md")
    assert len(chunks) == 3
    assert chunks[0].text == "0123456789"
    assert chunks[1].chunk_index == 1
    assert all(c.doc_id == "d1" for c in chunks)
    assert all(c.source == "a.md" for c in chunks)


def test_overlap_creates_duplicate_text():
    chunker = FixedChunker(chunk_size=10, overlap=4)
    text = "0123456789ABCDEFGH"  # 18 字符
    chunks = chunker.chunk_text(text, "d1", "a.md")
    # chunk0 = text[0:10], chunk1 = text[6:16], chunk2 = text[12:18]
    assert chunks[0].text == "0123456789"
    assert chunks[1].text == "6789ABCDEF"  # 重叠 4 字符
    assert chunks[2].text == "CDEFGH"


def test_empty_text_returns_empty_list():
    chunker = FixedChunker(chunk_size=10, overlap=0)
    chunks = chunker.chunk_text("", "d1", "a.md")
    assert chunks == []


def test_chunks_have_unique_ids():
    chunker = FixedChunker(chunk_size=5, overlap=0)
    chunks = chunker.chunk_text("0123456789", "d1", "a.md")
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))  # 无重复


def test_default_params():
    chunker = FixedChunker()
    assert chunker.chunk_size == 512
    assert chunker.overlap == 64

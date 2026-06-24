from __future__ import annotations

from rag.models import Answer, Chunk, Document, RetrievedChunk


def test_document_defaults():
    doc = Document(
        doc_id="d1",
        source="notes.md",
        title="Notes",
        type="md",
        chunk_count=0,
        ingested_at="2026-06-24T00:00:00",
        metadata={},
    )
    assert doc.doc_id == "d1"
    assert doc.source == "notes.md"
    assert doc.metadata == {}


def test_chunk_has_required_fields():
    chunk = Chunk(
        chunk_id="c1",
        doc_id="d1",
        source="notes.md",
        chunk_index=0,
        text="hello",
        metadata={},
    )
    assert chunk.text == "hello"
    assert chunk.chunk_index == 0


def test_retrieved_chunk_wraps_chunk_with_score():
    chunk = Chunk(
        chunk_id="c1",
        doc_id="d1",
        source="notes.md",
        chunk_index=0,
        text="hello",
        metadata={},
    )
    rc = RetrievedChunk(chunk=chunk, score=0.9)
    assert rc.chunk.text == "hello"
    assert rc.score == 0.9


def test_answer_holds_text_and_sources():
    chunk = Chunk(
        chunk_id="c1",
        doc_id="d1",
        source="notes.md",
        chunk_index=0,
        text="hello",
        metadata={},
    )
    rc = RetrievedChunk(chunk=chunk, score=0.9)
    ans = Answer(answer="因为...", sources=[rc])
    assert ans.answer == "因为..."
    assert len(ans.sources) == 1

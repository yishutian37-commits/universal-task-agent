from __future__ import annotations

from rag.models import Chunk, Document
from rag.store.base import BaseVectorStore


class _FakeStore(BaseVectorStore):
    """fake：全部用内存列表存。"""

    def __init__(self) -> None:
        self.chunks: list[Chunk] = []
        self.vectors: list[list[float]] = []
        self.docs: dict[str, Document] = {}

    def add(self, chunks, vectors):
        self.chunks.extend(chunks)
        self.vectors.extend(vectors)
        return len(chunks)

    def delete_by_source(self, source):
        before = len(self.chunks)
        keep = [
            (v, c) for v, c in zip(self.vectors, self.chunks) if c.source != source
        ]
        self.vectors = [v for v, _ in keep]
        self.chunks = [c for _, c in keep]
        return before - len(self.chunks)

    def delete_doc(self, doc_id):
        before = len(self.chunks)
        keep = [
            (v, c) for v, c in zip(self.vectors, self.chunks) if c.doc_id != doc_id
        ]
        self.vectors = [v for v, _ in keep]
        self.chunks = [c for _, c in keep]
        self.docs.pop(doc_id, None)
        return before - len(self.chunks)

    def upsert_doc(self, doc):
        self.docs[doc.doc_id] = doc

    def list_docs(self):
        return list(self.docs.values())

    def all_vectors(self):
        return self.vectors, self.chunks

    def count(self):
        return len(self.chunks)

    def clear(self):
        self.chunks = []
        self.vectors = []
        self.docs = {}


def _make_chunk(source="a.md", doc_id="d1"):
    return Chunk(
        chunk_id="c1",
        doc_id=doc_id,
        source=source,
        chunk_index=0,
        text="t",
        metadata={},
    )


def test_add_and_count():
    store = _FakeStore()
    n = store.add([_make_chunk()], [[1.0, 2.0]])
    assert n == 1
    assert store.count() == 1


def test_delete_by_source():
    store = _FakeStore()
    store.add([_make_chunk()], [[1.0, 2.0]])
    assert store.delete_by_source("a.md") == 1
    assert store.count() == 0


def test_delete_doc():
    store = _FakeStore()
    store.add([_make_chunk(doc_id="d1")], [[1.0]])
    assert store.delete_doc("d1") == 1
    assert store.count() == 0


def test_list_docs():
    store = _FakeStore()
    doc = Document("d1", "a.md", "A", "md", 1, "2026", {})
    store.upsert_doc(doc)
    assert len(store.list_docs()) == 1

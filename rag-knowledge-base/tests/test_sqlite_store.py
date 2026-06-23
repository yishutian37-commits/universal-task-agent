from __future__ import annotations

import sqlite3

import pytest

from rag.errors import EmbedderMismatchError
from rag.models import Chunk, Document
from rag.store.sqlite_store import SqliteStore


def _make_chunk(source="a.md", doc_id="d1", idx=0, text="hello"):
    return Chunk(
        chunk_id=f"c-{idx}",
        doc_id=doc_id,
        source=source,
        chunk_index=idx,
        text=text,
        metadata={"k": "v"},
    )


def _make_doc(doc_id="d1", source="a.md", count=1):
    return Document(
        doc_id=doc_id,
        source=source,
        title="A",
        type="md",
        chunk_count=count,
        ingested_at="2026-06-24",
        metadata={"foo": "bar"},
    )


def test_add_and_count(tmp_path):
    store = SqliteStore(str(tmp_path / "kb.db"), dim=4)
    store.add([_make_chunk()], [[1.0, 2.0, 3.0, 4.0]])
    assert store.count() == 1


def test_add_multiple(tmp_path):
    store = SqliteStore(str(tmp_path / "kb.db"), dim=4)
    chunks = [_make_chunk(idx=i, text=f"t{i}") for i in range(3)]
    vectors = [[float(i)] * 4 for i in range(3)]
    n = store.add(chunks, vectors)
    assert n == 3
    assert store.count() == 3


def test_all_vectors_returns_pairs(tmp_path):
    store = SqliteStore(str(tmp_path / "kb.db"), dim=4)
    store.add([_make_chunk(text="x")], [[1.0, 0.0, 0.0, 0.0]])
    vectors, chunks = store.all_vectors()
    assert len(vectors) == 1
    assert len(chunks) == 1
    assert chunks[0].text == "x"
    assert len(vectors[0]) == 4


def test_delete_by_source(tmp_path):
    store = SqliteStore(str(tmp_path / "kb.db"), dim=4)
    store.add(
        [_make_chunk(source="a.md"), _make_chunk(source="b.md", idx=1, doc_id="d2")],
        [[1.0, 0, 0, 0], [0, 1.0, 0, 0]],
    )
    assert store.delete_by_source("a.md") == 1
    assert store.count() == 1
    _, chunks = store.all_vectors()
    assert chunks[0].source == "b.md"


def test_delete_doc(tmp_path):
    store = SqliteStore(str(tmp_path / "kb.db"), dim=4)
    store.upsert_doc(_make_doc("d1"))
    store.add([_make_chunk(doc_id="d1")], [[1.0, 0, 0, 0]])
    assert store.delete_doc("d1") == 1
    assert store.count() == 0
    assert store.list_docs() == []


def test_upsert_and_list_docs(tmp_path):
    store = SqliteStore(str(tmp_path / "kb.db"), dim=4)
    store.upsert_doc(_make_doc("d1", count=5))
    docs = store.list_docs()
    assert len(docs) == 1
    assert docs[0].doc_id == "d1"
    assert docs[0].chunk_count == 5
    assert docs[0].metadata == {"foo": "bar"}


def test_dim_mismatch_raises(tmp_path):
    store = SqliteStore(str(tmp_path / "kb.db"), dim=4)
    store.add([_make_chunk()], [[1.0, 2, 3, 4]])
    with pytest.raises(EmbedderMismatchError):
        SqliteStore(str(tmp_path / "kb.db"), dim=8)


def test_same_dim_reopen_ok(tmp_path):
    store = SqliteStore(str(tmp_path / "kb.db"), dim=4)
    store.add([_make_chunk()], [[1.0, 2, 3, 4]])
    store2 = SqliteStore(str(tmp_path / "kb.db"), dim=4)
    assert store2.count() == 1


def test_empty_store_all_vectors(tmp_path):
    store = SqliteStore(str(tmp_path / "kb.db"), dim=4)
    vectors, chunks = store.all_vectors()
    assert vectors == []
    assert chunks == []
    assert store.count() == 0


def test_metadata_roundtrip_json(tmp_path):
    store = SqliteStore(str(tmp_path / "kb.db"), dim=4)
    store.add([_make_chunk()], [[1.0, 2, 3, 4]])
    _, chunks = store.all_vectors()
    assert chunks[0].metadata == {"k": "v"}


def test_create_tables(tmp_path):
    SqliteStore(str(tmp_path / "kb.db"), dim=4)
    conn = sqlite3.connect(str(tmp_path / "kb.db"))
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    conn.close()
    assert {"documents", "chunks", "kb_meta"} <= tables

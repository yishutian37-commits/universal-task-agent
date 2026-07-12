from __future__ import annotations

from pathlib import Path

from rag.defaults import create_default_kb


def test_list_docs_returns_ingested_documents(tmp_path: Path):
    f = tmp_path / "notes.md"
    f.write_text("UTA 是学习型 Agent。", encoding="utf-8")
    kb = create_default_kb(db_path=str(tmp_path / "kb.db"))

    result = kb.ingest_path(str(f))
    docs = kb.list_docs()

    assert len(docs) == 1
    assert docs[0].doc_id == result["doc_id"]
    assert docs[0].source == str(f)


def test_stats_returns_documents_chunks_and_dim(tmp_path: Path):
    f = tmp_path / "notes.md"
    f.write_text("一段内容", encoding="utf-8")
    kb = create_default_kb(db_path=str(tmp_path / "kb.db"))
    kb.ingest_path(str(f))

    stats = kb.stats()

    assert stats["documents"] == 1
    assert stats["chunks"] == 1
    assert stats["dim"] == 512


def test_delete_by_doc_id(tmp_path: Path):
    f = tmp_path / "notes.md"
    f.write_text("一段内容", encoding="utf-8")
    kb = create_default_kb(db_path=str(tmp_path / "kb.db"))
    result = kb.ingest_path(str(f))

    deleted = kb.delete(result["doc_id"])

    assert deleted == {"deleted": 1, "target": result["doc_id"]}
    assert kb.stats()["chunks"] == 0


def test_delete_by_source(tmp_path: Path):
    f = tmp_path / "notes.md"
    f.write_text("一段内容", encoding="utf-8")
    kb = create_default_kb(db_path=str(tmp_path / "kb.db"))
    kb.ingest_path(str(f))

    deleted = kb.delete(str(f))

    assert deleted == {"deleted": 1, "target": str(f)}
    assert kb.stats()["chunks"] == 0
    assert kb.stats()["documents"] == 0
    assert kb.list_docs() == []


def test_delete_missing_target_returns_zero(tmp_path: Path):
    kb = create_default_kb(db_path=str(tmp_path / "kb.db"))

    assert kb.delete("missing") == {"deleted": 0, "target": "missing"}


def test_rebuild_clears_store(tmp_path: Path):
    f = tmp_path / "notes.md"
    f.write_text("一段内容", encoding="utf-8")
    kb = create_default_kb(db_path=str(tmp_path / "kb.db"))
    kb.ingest_path(str(f))

    result = kb.rebuild()

    assert result["documents"] == 0
    assert result["chunks"] == 0
    assert kb.list_docs() == []
    assert kb.stats()["chunks"] == 0

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import rag.api as rag_api
from rag.api import app, set_kb
from rag.defaults import create_default_kb


@pytest.fixture
def client(tmp_path: Path):
    kb = create_default_kb(db_path=str(tmp_path / "kb.db"))
    set_kb(kb)
    yield TestClient(app)


@pytest.fixture
def md_file(tmp_path: Path) -> Path:
    f = tmp_path / "notes.md"
    f.write_text("# 笔记\nUTA 是学习型 Agent 框架，支持总结和分析。\n", encoding="utf-8")
    return f


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_stats_empty(client):
    resp = client.get("/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["documents"] == 0
    assert data["chunks"] == 0


def test_api_uses_real_models_env_var(monkeypatch, tmp_path):
    captured = {}

    def fake_create_default_kb(db_path: str, use_real_models: bool):
        captured["db_path"] = db_path
        captured["use_real_models"] = use_real_models
        return create_default_kb(db_path=str(tmp_path / "fake.db"))

    monkeypatch.setattr(rag_api, "_kb", None)
    monkeypatch.setenv("KB_DB_PATH", str(tmp_path / "env.db"))
    monkeypatch.setenv("KB_USE_REAL_MODELS", "1")
    monkeypatch.setattr("rag.defaults.create_default_kb", fake_create_default_kb)

    rag_api._get_kb()

    assert captured == {
        "db_path": str(tmp_path / "env.db"),
        "use_real_models": True,
    }


def test_ingest(client, md_file):
    resp = client.post("/ingest", json={"path": str(md_file)})
    assert resp.status_code == 200
    data = resp.json()
    assert data["chunk_count"] >= 1


def test_ingest_not_found(client):
    resp = client.post("/ingest", json={"path": "/nonexistent/file.md"})
    assert resp.status_code == 404


def test_ingest_directory(client, tmp_path):
    (tmp_path / "a.md").write_text("内容A", encoding="utf-8")
    (tmp_path / "b.md").write_text("内容B", encoding="utf-8")
    resp = client.post("/ingest", json={"path": str(tmp_path)})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["ingested"]) == 2


def test_list_documents(client, md_file):
    client.post("/ingest", json={"path": str(md_file)})
    resp = client.get("/documents")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1


def test_query(client, md_file):
    client.post("/ingest", json={"path": str(md_file)})
    resp = client.post("/query", json={"question": "UTA", "top_k": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["chunks"]) >= 1
    assert "score" in data["chunks"][0]


def test_query_can_expand_neighboring_chunks(client, md_file):
    client.post("/ingest", json={"path": str(md_file)})

    resp = client.post(
        "/query",
        json={
            "question": "UTA",
            "top_k": 1,
            "expand": True,
            "neighbor_window": 2,
            "max_sources": 1,
            "max_chars": 4_000,
        },
    )

    assert resp.status_code == 200
    assert resp.json()["expanded"] is True


def test_query_empty_store(client):
    resp = client.post("/query", json={"question": "test"})
    assert resp.status_code == 409


def test_ask(client, md_file):
    client.post("/ingest", json={"path": str(md_file)})
    resp = client.post("/ask", json={"question": "UTA 是什么", "top_k": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "sources" in data
    assert len(data["sources"]) >= 1


def test_ask_empty_store(client):
    resp = client.post("/ask", json={"question": "test"})
    assert resp.status_code == 409


def test_delete(client, md_file):
    ingest_resp = client.post("/ingest", json={"path": str(md_file)})
    doc_id = ingest_resp.json()["doc_id"]
    resp = client.delete(f"/documents/{doc_id}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] >= 1
    # 确认删干净
    stats = client.get("/stats").json()
    assert stats["chunks"] == 0

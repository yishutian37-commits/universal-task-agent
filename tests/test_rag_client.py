from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from desktop.api import DesktopAPI
from desktop.rag_client import RAGClient


@pytest.fixture
def md_file(tmp_path: Path) -> Path:
    f = tmp_path / "notes.md"
    f.write_text("# 笔记\nUTA 是学习型 Agent 框架。\n", encoding="utf-8")
    return f


# ---- RAGClient 内嵌模式 ----


def test_embedded_mode_default():
    import os

    client = RAGClient(api_url="")
    assert client.mode == "embedded"


def test_http_mode_when_url_set():
    client = RAGClient(api_url="http://localhost:8000")
    assert client.mode == "http"


def test_embedded_ingest_and_ask(md_file: Path, tmp_path: Path):
    client = RAGClient(api_url="")
    # 用临时目录的 KB
    from rag.defaults import create_default_kb

    client._kb = create_default_kb(db_path=str(tmp_path / "kb.db"))

    result = client.ingest(str(md_file))
    assert result["ok"] is True
    assert result["chunk_count"] >= 1

    answer = client.ask("UTA 是什么")
    assert answer["ok"] is True
    assert "UTA" in answer["answer"]
    assert len(answer["sources"]) >= 1


def test_embedded_ingest_folder_imports_supported_documents(tmp_path: Path):
    folder = tmp_path / "knowledge"
    folder.mkdir()
    (folder / "one.md").write_text("# One\n第一份文档", encoding="utf-8")
    (folder / "two.txt").write_text("第二份文档", encoding="utf-8")
    (folder / "ignored.json").write_text("{}", encoding="utf-8")
    client = RAGClient(api_url="")
    from rag.defaults import create_default_kb

    client._kb = create_default_kb(db_path=str(tmp_path / "kb.db"))

    result = client.ingest(str(folder))

    assert result["ok"] is True
    assert len(result["ingested"]) == 2
    assert client.stats()["documents"] == 2


def test_embedded_stats(md_file: Path, tmp_path: Path):
    client = RAGClient(api_url="")
    from rag.defaults import create_default_kb

    client._kb = create_default_kb(db_path=str(tmp_path / "kb.db"))
    client.ingest(str(md_file))
    stats = client.stats()
    assert stats["documents"] == 1
    assert stats["chunks"] >= 1


def test_embedded_query_empty_returns_error(tmp_path: Path):
    client = RAGClient(api_url="")
    from rag.defaults import create_default_kb

    client._kb = create_default_kb(db_path=str(tmp_path / "kb.db"))
    result = client.query("问题")
    assert result["ok"] is False


def test_embedded_query_does_not_truncate_retrieved_chunk_to_200_characters(tmp_path: Path):
    source = tmp_path / "long.md"
    source.write_text("RAG构建步骤：" + "先清洗文档再切片。" * 35, encoding="utf-8")
    client = RAGClient(api_url="")
    from rag.defaults import create_default_kb

    client._kb = create_default_kb(db_path=str(tmp_path / "kb.db"))
    client.ingest(str(source))

    result = client.query("RAG构建步骤", top_k=1)

    assert len(result["chunks"][0]["text"]) > 200
    assert "chunk_index" in result["chunks"][0]


def test_http_expanded_query_requests_neighboring_context():
    client = RAGClient(api_url="http://localhost:8000")
    client._http = MagicMock(return_value={"chunks": []})

    client.query_expanded("把知识库中 RAG 如何构建的详细内容发给我", top_k=4)

    client._http.assert_called_once_with(
        "POST",
        "/query",
        {
            "question": "RAG 如何构建 基础流程 核心步骤 架构",
            "top_k": 4,
            "expand": True,
            "neighbor_window": 4,
            "max_sources": 2,
            "max_chars": 14_000,
        },
    )


def test_http_query_removes_natural_language_delivery_wrappers():
    client = RAGClient(api_url="http://localhost:8000")
    client._http = MagicMock(return_value={"chunks": []})

    client.query("把知识库中 Loop 相关知识发给我", top_k=4)

    client._http.assert_called_once_with(
        "POST",
        "/query",
        {"question": "Loop", "top_k": 4},
    )


# ---- HTTP 模式（mock）----


def test_http_mode_calls_url():
    client = RAGClient(api_url="http://localhost:8000")
    client._http = MagicMock(return_value={"documents": 2, "chunks": 5})
    stats = client.stats()
    client._http.assert_called_once_with("GET", "/stats")
    assert stats["documents"] == 2


def test_http_mode_ask():
    client = RAGClient(api_url="http://localhost:8000")
    client._http = MagicMock(
        return_value={"answer": "LLM 答案", "sources": [{"score": 0.9, "source": "a.md"}]}
    )
    result = client.ask("问题", top_k=3)
    client._http.assert_called_once_with(
        "POST", "/ask", {"question": "问题", "top_k": 3}
    )
    assert result["answer"] == "LLM 答案"


# ---- DesktopAPI 集成 ----


def test_desktop_api_rag_methods_exist():
    api = DesktopAPI()
    for method in ["rag_stats", "rag_list_docs", "rag_ingest", "rag_query", "rag_ask", "rag_delete"]:
        assert hasattr(api, method)


def test_desktop_api_rag_ask(md_file: Path, tmp_path: Path):
    rag_client = RAGClient(api_url="")
    from rag.defaults import create_default_kb

    rag_client._kb = create_default_kb(db_path=str(tmp_path / "kb.db"))
    api = DesktopAPI(rag_client=rag_client)

    api.rag_ingest(str(md_file))
    result = api.rag_ask("UTA 是什么")
    assert result["ok"] is True
    assert "UTA" in result["answer"]

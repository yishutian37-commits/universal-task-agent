from __future__ import annotations

from pathlib import Path

from rag.defaults import create_default_kb
from rag.generation.echo_generator import EchoGenerator
from rag.loaders.text_loader import TextLoader
from rag.retrieval.vector_retriever import VectorRetriever


def test_defaults_assembles_real_components(tmp_path: Path):
    kb = create_default_kb(db_path=str(tmp_path / "kb.db"))
    assert isinstance(kb.loader_factory.get("a.md"), TextLoader)
    assert isinstance(kb.retriever, VectorRetriever)
    assert isinstance(kb.generator, EchoGenerator)


def test_defaults_end_to_end(tmp_path: Path):
    f = tmp_path / "notes.md"
    f.write_text("UTA 是学习型 Agent 框架。\n它支持总结和表格分析。\n", encoding="utf-8")

    kb = create_default_kb(db_path=str(tmp_path / "kb.db"))
    result = kb.ingest_path(str(f))
    assert result["chunk_count"] >= 1

    answer = kb.ask("UTA 是什么")
    assert "UTA" in answer.answer
    assert len(answer.sources) > 0
    assert "notes.md" in answer.sources[0].chunk.source


def test_defaults_query_only(tmp_path: Path):
    f = tmp_path / "doc.md"
    f.write_text("第一段内容。第二段内容。", encoding="utf-8")

    kb = create_default_kb(db_path=str(tmp_path / "kb.db"))
    kb.ingest_path(str(f))
    chunks = kb.query("内容", top_k=1)
    assert len(chunks) == 1


def test_defaults_reuses_existing_db(tmp_path: Path):
    db = str(tmp_path / "kb.db")
    f = tmp_path / "a.md"
    f.write_text("测试内容", encoding="utf-8")

    kb1 = create_default_kb(db_path=db)
    kb1.ingest_path(str(f))

    kb2 = create_default_kb(db_path=db)  # 重新打开同一库
    assert kb2._store.count() == 1  # 数据持久化了


def test_knowledgebase_from_config_classmethod(tmp_path: Path):
    from rag.kb import KnowledgeBase

    kb = KnowledgeBase.from_config(db_path=str(tmp_path / "kb.db"))
    f = tmp_path / "x.md"
    f.write_text("内容", encoding="utf-8")
    kb.ingest_path(str(f))
    assert kb._store.count() == 1

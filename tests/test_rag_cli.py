from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

VENV_PYTHON = str(Path(__file__).resolve().parents[1] / ".venv" / "bin" / "python")
PROJECT_ROOT = str(Path(__file__).resolve().parents[1])


def _run_cli(db_path: str, *args: str) -> subprocess.CompletedProcess:
    """运行 CLI，返回结果。"""
    return subprocess.run(
        [VENV_PYTHON, "-m", "rag.cli", "--db-path", db_path, *args],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        timeout=30,
    )


@pytest.fixture
def md_file(tmp_path: Path) -> Path:
    f = tmp_path / "notes.md"
    f.write_text("# 笔记\n\nUTA 是学习型 Agent 框架，支持总结和表格分析。\n", encoding="utf-8")
    return f


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "kb.db")


def test_ingest_single_file(db_path: str, md_file: Path):
    result = _run_cli(db_path, "ingest", str(md_file), "--json")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["chunk_count"] >= 1
    assert str(md_file) in data["source"]


def test_ingest_human_output(db_path: str, md_file: Path):
    result = _run_cli(db_path, "ingest", str(md_file))
    assert result.returncode == 0
    assert "已摄入" in result.stdout


def test_stats(db_path: str, md_file: Path):
    _run_cli(db_path, "ingest", str(md_file))
    result = _run_cli(db_path, "stats", "--json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["documents"] == 1
    assert data["chunks"] >= 1
    assert data["dim"] == 512


def test_list(db_path: str, md_file: Path):
    _run_cli(db_path, "ingest", str(md_file))
    result = _run_cli(db_path, "list", "--json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert data[0]["chunk_count"] >= 1


def test_query(db_path: str, md_file: Path):
    _run_cli(db_path, "ingest", str(md_file))
    result = _run_cli(db_path, "query", "UTA", "--top-k", "2", "--json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert len(data) >= 1
    assert "score" in data[0]
    assert "text" in data[0]


def test_ask(db_path: str, md_file: Path):
    _run_cli(db_path, "ingest", str(md_file))
    result = _run_cli(db_path, "ask", "UTA 是什么", "--json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "answer" in data
    assert "sources" in data
    assert len(data["sources"]) >= 1


def test_ask_empty_store_returns_error(db_path: str):
    result = _run_cli(db_path, "ask", "问题")
    assert result.returncode == 1
    assert "为空" in result.stderr or "empty" in result.stderr.lower()


def test_delete_by_source(db_path: str, md_file: Path):
    _run_cli(db_path, "ingest", str(md_file))
    result = _run_cli(db_path, "delete", str(md_file), "--json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["deleted"] >= 1
    # 确认删干净
    stats = json.loads(_run_cli(db_path, "stats", "--json").stdout)
    assert stats["chunks"] == 0


def test_rebuild_requires_yes(db_path: str, md_file: Path):
    _run_cli(db_path, "ingest", str(md_file))
    result = _run_cli(db_path, "rebuild")
    assert result.returncode == 1
    assert "--yes" in result.stderr


def test_rebuild_with_yes(db_path: str, md_file: Path):
    _run_cli(db_path, "ingest", str(md_file))
    result = _run_cli(db_path, "rebuild", "--yes", "--json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["chunks"] == 0


def test_ingest_directory(db_path: str, tmp_path: Path):
    (tmp_path / "a.md").write_text("内容A", encoding="utf-8")
    (tmp_path / "b.md").write_text("内容B", encoding="utf-8")
    result = _run_cli(db_path, "ingest", str(tmp_path), "--json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert len(data) == 2

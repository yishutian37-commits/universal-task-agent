from __future__ import annotations

from pathlib import Path

import pytest

from rag.errors import UnsupportedSourceError
from rag.loaders.base import LoadedDoc
from rag.loaders.text_loader import TextLoader


def test_load_md_file(tmp_path: Path):
    f = tmp_path / "notes.md"
    f.write_text("# 标题\n\n正文内容。", encoding="utf-8")
    loader = TextLoader()
    doc = loader.load(str(f))
    assert isinstance(doc, LoadedDoc)
    assert "正文内容" in doc.text
    assert doc.source == str(f)
    assert doc.metadata["type"] == "md"


def test_load_txt_file(tmp_path: Path):
    f = tmp_path / "readme.txt"
    f.write_text("纯文本内容", encoding="utf-8")
    loader = TextLoader()
    doc = loader.load(str(f))
    assert "纯文本内容" in doc.text
    assert doc.metadata["type"] == "txt"


def test_load_preserves_unicode(tmp_path: Path):
    f = tmp_path / "cn.md"
    f.write_text("你好世界 🌍", encoding="utf-8")
    loader = TextLoader()
    doc = loader.load(str(f))
    assert "你好世界" in doc.text
    assert "🌍" in doc.text


def test_load_missing_file_raises(tmp_path: Path):
    loader = TextLoader()
    with pytest.raises(FileNotFoundError):
        loader.load(str(tmp_path / "nope.md"))


def test_factory_routes_md():
    from rag.loaders.base import LoaderFactory

    factory = LoaderFactory.for_text()
    loader = factory.get("a.md")
    assert isinstance(loader, TextLoader)


def test_factory_rejects_unknown():
    from rag.loaders.base import LoaderFactory
    from rag.errors import UnsupportedSourceError

    factory = LoaderFactory.for_text()
    with pytest.raises(UnsupportedSourceError):
        factory.get("a.pdf")

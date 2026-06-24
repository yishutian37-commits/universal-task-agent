from __future__ import annotations

import pytest

from rag.errors import UnsupportedSourceError
from rag.loaders.base import LoadedDoc, LoaderFactory


def test_loaded_doc_holds_text_and_source():
    doc = LoadedDoc(text="内容", source="a.md", metadata={"type": "md"})
    assert doc.text == "内容"
    assert doc.source == "a.md"


class _FakeMdLoader:
    def load(self, source: str) -> LoadedDoc:
        return LoadedDoc(text="fake", source=source, metadata={"type": "md"})


def test_factory_routes_by_extension():
    factory = LoaderFactory({".md": _FakeMdLoader()})
    loader = factory.get("notes.md")
    doc = loader.load("notes.md")
    assert doc.metadata["type"] == "md"


def test_factory_raises_on_unsupported():
    factory = LoaderFactory({".md": _FakeMdLoader()})
    with pytest.raises(UnsupportedSourceError):
        factory.get("unknown.xyz")

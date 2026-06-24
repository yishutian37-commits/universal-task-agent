from __future__ import annotations

import pytest

from rag.errors import (
    EmbedderMismatchError,
    EmptyStoreError,
    IngestError,
    KnowledgeBaseError,
    LLMError,
    UnsupportedSourceError,
)


@pytest.mark.parametrize(
    "exc_class",
    [
        UnsupportedSourceError,
        EmbedderMismatchError,
        EmptyStoreError,
        IngestError,
        LLMError,
    ],
)
def test_all_errors_inherit_base(exc_class):
    assert issubclass(exc_class, KnowledgeBaseError)


def test_base_inherits_exception():
    assert issubclass(KnowledgeBaseError, Exception)


def test_errors_carry_message():
    err = EmptyStoreError("库里没有文档")
    assert str(err) == "库里没有文档"

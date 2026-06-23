from __future__ import annotations

from rag.generation.base import BaseGenerator
from rag.models import Chunk


class _FakeGenerator(BaseGenerator):
    def generate(self, question, contexts):
        refs = ", ".join(c.source for c in contexts)
        return f"关于「{question}」的回答，来源：{refs}"


def test_generate_uses_contexts():
    gen = _FakeGenerator()
    chunks = [
        Chunk("c1", "d1", "a.md", 0, "内容A", {}),
        Chunk("c2", "d1", "b.md", 0, "内容B", {}),
    ]
    answer = gen.generate("什么是X", chunks)
    assert "a.md" in answer
    assert "b.md" in answer

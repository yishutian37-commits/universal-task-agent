from __future__ import annotations

from rag.generation.llm_generator import LLMGenerator
from rag.models import Chunk


class FakeLLMClient:
    """fake：记录 prompt，返回固定答案。"""

    def __init__(self, response: str = "这是模拟答案") -> None:
        self.response = response
        self.last_system = ""
        self.last_user = ""

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        self.last_system = system_prompt
        self.last_user = user_prompt
        return self.response


def _chunk(source="a.md", text="片段内容"):
    return Chunk("c1", "d1", source, 0, text, {})


def test_generate_returns_llm_response():
    client = FakeLLMClient("LLM 说：答案是 42")
    gen = LLMGenerator(client=client)
    answer = gen.generate("宇宙的答案", [_chunk()])
    assert answer == "LLM 说：答案是 42"


def test_prompt_includes_question_and_context():
    client = FakeLLMClient()
    gen = LLMGenerator(client=client)
    gen.generate("什么是 RAG", [_chunk("a.md", "RAG 是检索增强生成")])
    assert "什么是 RAG" in client.last_user
    assert "RAG 是检索增强生成" in client.last_user
    assert "a.md" in client.last_user


def test_system_prompt_instructs_citation():
    client = FakeLLMClient()
    gen = LLMGenerator(client=client)
    gen.generate("问题", [_chunk()])
    assert "来源" in client.last_system or "引用" in client.last_system


def test_empty_contexts_still_works():
    client = FakeLLMClient("无相关信息")
    gen = LLMGenerator(client=client)
    answer = gen.generate("问题", [])
    assert answer == "无相关信息"


def test_multiple_contexts_all_in_prompt():
    client = FakeLLMClient()
    gen = LLMGenerator(client=client)
    gen.generate("问题", [_chunk("a.md", "内容A"), _chunk("b.md", "内容B")])
    assert "内容A" in client.last_user
    assert "内容B" in client.last_user

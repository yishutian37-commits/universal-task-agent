import pytest

from llm.llm_client import LLMClient, LLMClientError


class StaticChatClient(LLMClient):
    def __init__(self, content: str):
        super().__init__(api_key="key", model="mimo-v2.5-pro", base_url="http://example.com/v1")
        self.content = content

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        return self.content


def test_normalizes_full_chat_completions_url():
    client = LLMClient(
        api_key="key",
        model="mimo-v2.5-pro",
        base_url="https://token-plan-cn.xiaomimimo.com/v1/chat/completions",
    )

    assert client.endpoint == "https://token-plan-cn.xiaomimimo.com/v1/chat/completions"


def test_normalizes_v1_base_url():
    client = LLMClient(api_key="key", model="mimo-v2.5-pro", base_url="http://127.0.0.1:15721/v1")

    assert client.endpoint == "http://127.0.0.1:15721/v1/chat/completions"


def test_chat_uses_injected_transport_and_returns_content():
    def fake_transport(endpoint, headers, payload, timeout):
        assert endpoint == "http://example.com/v1/chat/completions"
        assert headers["Authorization"] == "Bearer key"
        assert payload["model"] == "mimo-v2.5-pro"
        assert payload["messages"][0]["content"] == "sys"
        assert payload["messages"][1]["content"] == "user"
        return {"choices": [{"message": {"content": "hello"}}]}

    client = LLMClient(
        api_key="key",
        model="mimo-v2.5-pro",
        base_url="http://example.com/v1",
        transport=fake_transport,
    )

    assert client.chat("sys", "user") == "hello"


def test_chat_requires_api_key():
    client = LLMClient(api_key="", model="mimo-v2.5-pro", base_url="http://example.com/v1")

    with pytest.raises(LLMClientError, match="LLM_API_KEY is required"):
        client.chat("sys", "user")


def test_chat_json_parses_plain_json():
    client = StaticChatClient('{"task_type": "summarize"}')

    assert client.chat_json("sys", "user") == {"task_type": "summarize"}


def test_chat_json_parses_json_code_block():
    client = StaticChatClient('```json\n{"task_type": "data_analysis"}\n```')

    assert client.chat_json("sys", "user") == {"task_type": "data_analysis"}


def test_chat_json_raises_on_bad_json():
    client = StaticChatClient("not json")

    with pytest.raises(LLMClientError):
        client.chat_json("sys", "user")

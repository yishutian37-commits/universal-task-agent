import pytest
import sys
from types import SimpleNamespace

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


def test_default_transport_can_disable_ssl_verification(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"choices":[{"message":{"content":"ok"}}]}'

    def fake_urlopen(req, timeout, context=None):
        captured["context"] = context
        return FakeResponse()

    monkeypatch.setattr("llm.llm_client.request.urlopen", fake_urlopen)
    client = LLMClient(
        api_key="key",
        model="mimo-v2.5-pro",
        base_url="https://example.com/v1",
        ssl_verify=False,
    )

    assert client.chat("sys", "user") == "ok"
    assert captured["context"] is not None
    assert captured["context"].check_hostname is False


def test_default_transport_uses_certifi_when_ssl_verification_enabled(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"choices":[{"message":{"content":"ok"}}]}'

    def fake_urlopen(req, timeout, context=None):
        captured["context"] = context
        return FakeResponse()

    def fake_context(cafile=None):
        captured["cafile"] = cafile
        return "certifi-context"

    monkeypatch.setitem(sys.modules, "certifi", SimpleNamespace(where=lambda: "/tmp/cacert.pem"))
    monkeypatch.setattr("llm.llm_client.ssl.create_default_context", fake_context)
    monkeypatch.setattr("llm.llm_client.request.urlopen", fake_urlopen)
    client = LLMClient(
        api_key="key",
        model="mimo-v2.5-pro",
        base_url="https://example.com/v1",
        ssl_verify=True,
    )

    assert client.chat("sys", "user") == "ok"
    assert captured["cafile"] == "/tmp/cacert.pem"
    assert captured["context"] == "certifi-context"


def test_chat_falls_back_to_curl_transport_on_urllib_ssl_eof():
    calls = []

    def eof_transport(endpoint, headers, payload, timeout):
        calls.append(("primary", endpoint, headers, payload, timeout))
        raise LLMClientError(
            "LLM network error: [SSL: UNEXPECTED_EOF_WHILE_READING] "
            "EOF occurred in violation of protocol"
        )

    def fallback_transport(endpoint, headers, payload, timeout):
        calls.append(("fallback", endpoint, headers, payload, timeout))
        return {"choices": [{"message": {"content": "fallback ok"}}]}

    client = LLMClient(
        api_key="key",
        model="mimo-v2.5-pro",
        base_url="https://example.com/v1",
        transport=eof_transport,
        fallback_transport=fallback_transport,
    )

    assert client.chat("sys", "user") == "fallback ok"
    assert [call[0] for call in calls] == ["primary", "fallback"]
    assert calls[1][2]["Authorization"] == "Bearer key"


def test_chat_does_not_fallback_for_non_eof_errors():
    def http_error_transport(endpoint, headers, payload, timeout):
        raise LLMClientError("LLM HTTP error 500: broken")

    def fallback_transport(endpoint, headers, payload, timeout):
        raise AssertionError("fallback should not be called")

    client = LLMClient(
        api_key="key",
        model="mimo-v2.5-pro",
        base_url="https://example.com/v1",
        transport=http_error_transport,
        fallback_transport=fallback_transport,
    )

    with pytest.raises(LLMClientError, match="LLM HTTP error 500"):
        client.chat("sys", "user")


def test_curl_transport_passes_secret_through_stdin_not_command(monkeypatch):
    captured = {}

    def fake_run(cmd, input, text, capture_output, timeout):
        captured["cmd"] = cmd
        captured["input"] = input
        captured["text"] = text
        captured["capture_output"] = capture_output
        captured["timeout"] = timeout
        return SimpleNamespace(
            returncode=0,
            stdout='{"choices":[{"message":{"content":"curl ok"}}]}\n200',
            stderr="",
        )

    monkeypatch.setattr("llm.llm_client.shutil.which", lambda name: "/usr/bin/curl")
    monkeypatch.setattr("llm.llm_client.subprocess.run", fake_run)
    client = LLMClient(api_key="secret-key", model="mimo-v2.5-pro", base_url="https://example.com/v1")

    response = client._curl_transport(
        client.endpoint,
        {"Authorization": "Bearer secret-key", "Content-Type": "application/json"},
        {"model": "mimo-v2.5-pro", "messages": [{"role": "user", "content": "ping"}]},
        30,
    )

    assert response["choices"][0]["message"]["content"] == "curl ok"
    assert captured["cmd"] == ["/usr/bin/curl", "--config", "-"]
    assert "secret-key" not in " ".join(captured["cmd"])
    assert "Authorization: Bearer secret-key" in captured["input"]
    assert "data-raw" in captured["input"]


def test_curl_transport_converts_http_errors(monkeypatch):
    def fake_run(cmd, input, text, capture_output, timeout):
        return SimpleNamespace(
            returncode=0,
            stdout='{"error":{"message":"Invalid API Key"}}\n401',
            stderr="",
        )

    monkeypatch.setattr("llm.llm_client.shutil.which", lambda name: "/usr/bin/curl")
    monkeypatch.setattr("llm.llm_client.subprocess.run", fake_run)
    client = LLMClient(api_key="key", model="mimo-v2.5-pro", base_url="https://example.com/v1")

    with pytest.raises(LLMClientError, match="LLM HTTP error 401"):
        client._curl_transport(client.endpoint, {}, {"model": "mimo-v2.5-pro"}, 30)


def test_curl_transport_reports_missing_curl(monkeypatch):
    monkeypatch.setattr("llm.llm_client.shutil.which", lambda name: None)
    client = LLMClient(api_key="key", model="mimo-v2.5-pro", base_url="https://example.com/v1")

    with pytest.raises(LLMClientError, match="curl is not available"):
        client._curl_transport(client.endpoint, {}, {"model": "mimo-v2.5-pro"}, 30)


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

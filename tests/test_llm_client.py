import pytest
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


def test_chat_stream_uses_injected_stream_transport_and_yields_deltas():
    captured = {}

    def fake_stream_transport(endpoint, headers, payload, timeout):
        captured.update(endpoint=endpoint, headers=headers, payload=payload, timeout=timeout)
        yield "你"
        yield "好"

    client = LLMClient(
        api_key="key",
        model="mimo-v2.5-pro",
        base_url="http://example.com/v1",
        stream_transport=fake_stream_transport,
    )

    assert list(client.chat_stream("sys", "user")) == ["你", "好"]
    assert captured["payload"]["stream"] is True
    assert captured["payload"]["messages"][1]["content"] == "user"


def test_chat_stream_falls_back_to_complete_reply_before_any_delta():
    def eof_stream_transport(endpoint, headers, payload, timeout):
        del endpoint, headers, payload, timeout
        raise LLMClientError("LLM network error: UNEXPECTED_EOF_WHILE_READING")
        yield "unreachable"

    def eof_transport(endpoint, headers, payload, timeout):
        raise LLMClientError("LLM network error: UNEXPECTED_EOF_WHILE_READING")

    def fallback_transport(endpoint, headers, payload, timeout):
        return {"choices": [{"message": {"content": "完整回退"}}]}

    client = LLMClient(
        api_key="key",
        model="mimo-v2.5-pro",
        base_url="https://example.com/v1",
        transport=eof_transport,
        fallback_transport=fallback_transport,
        stream_transport=eof_stream_transport,
    )

    assert list(client.chat_stream("sys", "user")) == ["完整回退"]


def test_parse_stream_line_reads_sse_delta_and_done_marker():
    client = LLMClient(api_key="key", model="m", base_url="http://example.com/v1")

    assert client._parse_stream_line('data: {"choices":[{"delta":{"content":"片段"}}]}') == "片段"
    assert client._parse_stream_line("data: [DONE]") is None


def test_default_transport_can_disable_ssl_verification(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, timeout, verify):
            captured["timeout"] = timeout
            captured["verify"] = verify

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, endpoint, headers, json):
            captured["endpoint"] = endpoint
            captured["headers"] = headers
            captured["payload"] = json
            return FakeResponse()

    class FakeResponse:
        def raise_for_status(self):
            return self

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr("llm.llm_client.httpx.Client", FakeClient)
    client = LLMClient(
        api_key="key",
        model="mimo-v2.5-pro",
        base_url="https://example.com/v1",
        ssl_verify=False,
    )

    assert client.chat("sys", "user") == "ok"
    assert captured["verify"] is False


def test_default_transport_uses_certifi_when_ssl_verification_enabled(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, timeout, verify):
            captured["timeout"] = timeout
            captured["verify"] = verify

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, endpoint, headers, json):
            return FakeResponse()

    class FakeResponse:
        def raise_for_status(self):
            return self

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr("llm.llm_client.certifi.where", lambda: "/tmp/cacert.pem")
    monkeypatch.setattr("llm.llm_client.httpx.Client", FakeClient)
    client = LLMClient(
        api_key="key",
        model="mimo-v2.5-pro",
        base_url="https://example.com/v1",
        ssl_verify=True,
    )

    assert client.chat("sys", "user") == "ok"
    assert captured["verify"] == "/tmp/cacert.pem"


def test_from_config_enables_curl_fallback_by_default(monkeypatch):
    import config

    monkeypatch.setattr(config, "LLM_API_KEY", "key")
    monkeypatch.setattr(config, "LLM_MODEL", "mimo-v2.5-pro")
    monkeypatch.setattr(config, "LLM_BASE_URL", "https://example.com/v1")
    monkeypatch.setattr(config, "LLM_SSL_VERIFY", True)

    client = LLMClient.from_config()

    assert client.fallback_transport is not None


def test_chat_falls_back_on_ssl_eof():
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

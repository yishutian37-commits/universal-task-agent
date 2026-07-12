import pytest


class FakeResponse:
    def __init__(self, text="hello", status_code=200, headers=None):
        self.text = text
        self.status_code = status_code
        self.headers = headers or {"content-type": "text/plain"}


class FakeHttpClient:
    def __init__(self):
        self.calls = []

    def get(self, url, timeout, follow_redirects):
        self.calls.append((url, timeout, follow_redirects))
        return FakeResponse("hello world", 200)


class FakeSearchTool:
    def __init__(self):
        self.calls = []

    def run(self, action_name, params):
        self.calls.append((action_name, params))
        return {
            "message": "找到 1 条搜索结果",
            "query": params["query"],
            "search_results": [{"title": "结果", "url": "https://example.com"}],
        }


def test_calculator_tool_evaluates_safe_math_expression():
    from tools.langchain_common_tools import CalculatorLangChainTool

    result = CalculatorLangChainTool().invoke({"expression": "2 + 3 * 4"})

    assert result["expression"] == "2 + 3 * 4"
    assert result["result"] == 14


def test_calculator_tool_extracts_expression_from_natural_query():
    from tools.langchain_common_tools import CalculatorLangChainTool

    result = CalculatorLangChainTool().invoke({"query": "计算 2 + 3 * 4"})

    assert result["expression"] == "2 + 3 * 4"
    assert result["result"] == 14


def test_calculator_tool_rejects_unsafe_expression():
    from tools.langchain_common_tools import CalculatorLangChainTool

    with pytest.raises(ValueError, match="不支持的计算表达式"):
        CalculatorLangChainTool().invoke({"expression": "__import__('os').system('echo bad')"})


def test_datetime_tool_returns_injected_current_time():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from tools.langchain_common_tools import DateTimeLangChainTool

    fixed = datetime(2026, 7, 9, 10, 11, 12, tzinfo=ZoneInfo("Asia/Shanghai"))
    tool = DateTimeLangChainTool(now_provider=lambda timezone: fixed)

    result = tool.invoke({"timezone": "Asia/Shanghai"})

    assert result["timezone"] == "Asia/Shanghai"
    assert result["date"] == "2026-07-09"
    assert result["time"] == "10:11:12"


def test_json_tool_formats_and_extracts_path():
    from tools.langchain_common_tools import JsonLangChainTool

    result = JsonLangChainTool().invoke(
        {
            "json_text": '{"user": {"name": "天甲树"}, "count": 2}',
            "path": "user.name",
        }
    )

    assert result["valid"] is True
    assert result["value"] == "天甲树"
    assert '"count": 2' in result["pretty"]


def test_json_tool_extracts_json_text_from_natural_query():
    from tools.langchain_common_tools import JsonLangChainTool

    result = JsonLangChainTool().invoke({"query": "格式化 JSON：{\"a\": 1}"})

    assert result["valid"] is True
    assert result["parsed"] == {"a": 1}


def test_json_tool_reports_invalid_json():
    from tools.langchain_common_tools import JsonLangChainTool

    result = JsonLangChainTool().invoke({"json_text": "{bad json"})

    assert result["valid"] is False
    assert "error" in result


def test_http_get_tool_fetches_public_url_with_limits():
    from tools.langchain_common_tools import HttpGetLangChainTool

    client = FakeHttpClient()
    tool = HttpGetLangChainTool(
        http_client=client,
        max_chars=5,
        hostname_resolver=lambda hostname: ["93.184.216.34"],
    )

    result = tool.invoke({"url": "https://example.com/page"})

    assert client.calls == [("https://example.com/page", 10, False)]
    assert result["status_code"] == 200
    assert result["text"] == "hello"
    assert result["truncated"] is True


def test_http_get_tool_rejects_localhost():
    from tools.langchain_common_tools import HttpGetLangChainTool

    with pytest.raises(ValueError, match="不允许访问本机或内网地址"):
        HttpGetLangChainTool(http_client=FakeHttpClient()).invoke({"url": "http://127.0.0.1:8000"})


def test_http_get_tool_rejects_non_http_scheme():
    from tools.langchain_common_tools import HttpGetLangChainTool

    with pytest.raises(ValueError, match="只支持 http/https"):
        HttpGetLangChainTool(http_client=FakeHttpClient()).invoke({"url": "file:///etc/passwd"})


def test_http_get_tool_rejects_hostname_that_resolves_to_private_ip():
    from tools.langchain_common_tools import HttpGetLangChainTool

    tool = HttpGetLangChainTool(
        http_client=FakeHttpClient(),
        hostname_resolver=lambda hostname: ["127.0.0.1"],
    )

    with pytest.raises(ValueError, match="不允许访问本机或内网地址"):
        tool.invoke({"url": "https://public.example/data"})


def test_http_get_tool_revalidates_redirect_target():
    from tools.langchain_common_tools import HttpGetLangChainTool

    class RedirectClient:
        def get(self, url, timeout, follow_redirects):
            return FakeResponse("", 302, {"location": "http://127.0.0.1/private"})

    tool = HttpGetLangChainTool(
        http_client=RedirectClient(),
        hostname_resolver=lambda hostname: ["93.184.216.34"],
    )

    with pytest.raises(ValueError, match="不允许访问本机或内网地址"):
        tool.invoke({"url": "https://public.example/redirect"})


def test_http_get_tool_pins_validated_ip_for_real_request():
    from tools.langchain_common_tools import HttpGetLangChainTool

    tool = HttpGetLangChainTool(hostname_resolver=lambda hostname: ["93.184.216.34"])

    pinned_url, headers, extensions = tool._pinned_request_args(
        "https://example.com:8443/page",
        "93.184.216.34",
    )

    assert pinned_url == "https://93.184.216.34:8443/page"
    assert headers == {"Host": "example.com:8443"}
    assert extensions == {"sni_hostname": "example.com"}


def test_search_tool_wraps_existing_search_tool():
    from tools.langchain_common_tools import SearchLangChainTool

    fake_search = FakeSearchTool()
    result = SearchLangChainTool(fake_search).invoke({"query": "UTA Agent"})

    assert fake_search.calls == [("search", {"query": "UTA Agent", "max_results": 5})]
    assert result["query"] == "UTA Agent"
    assert result["search_results"][0]["title"] == "结果"


def test_weather_tool_wraps_existing_search_tool_as_weather_query():
    from tools.langchain_common_tools import WeatherLangChainTool

    fake_search = FakeSearchTool()
    result = WeatherLangChainTool(fake_search).invoke({"city": "包头"})

    assert fake_search.calls == [("search", {"query": "包头 天气", "max_results": 5})]
    assert result["query"] == "包头 天气"


def test_build_common_langchain_tools_contains_safe_tool_names():
    from tools.langchain_common_tools import build_common_langchain_tools

    names = {tool.name for tool in build_common_langchain_tools(search_tool=FakeSearchTool())}

    assert {
        "langchain_calculator_tool",
        "langchain_datetime_tool",
        "langchain_http_get_tool",
        "langchain_search_tool",
        "langchain_weather_tool",
        "langchain_json_tool",
    }.issubset(names)

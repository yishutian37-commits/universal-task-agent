from search_providers.base_search_provider import SearchResponse, SearchResult
from tools.search_tool import SearchTool


class FakeSearchProvider:
    provider_name = "fake"

    def __init__(self):
        self.seen_query = None
        self.seen_max_results = None

    def search(self, query, max_results=5):
        self.seen_query = query
        self.seen_max_results = max_results
        return SearchResponse(
            query=query,
            provider=self.provider_name,
            results=[
                SearchResult(
                    title="测试结果",
                    url="https://example.com/result",
                    snippet="测试摘要",
                    source="fake",
                )
            ],
        )


class FakeWeatherProvider:
    provider_name = "fake-weather"

    def __init__(self):
        self.seen_city = None

    def current_weather(self, city):
        self.seen_city = city
        return {
            "city": city,
            "provider": self.provider_name,
            "source_url": "https://example.com/weather",
            "time": "2026-06-24T14:00",
            "weather_text": "晴",
            "temperature": 23.4,
            "apparent_temperature": 22.8,
            "relative_humidity": 41,
            "precipitation": 0,
            "wind_speed": 12.5,
            "wind_direction": 270,
        }


def test_search_tool_uses_explicit_query():
    provider = FakeSearchProvider()
    result = SearchTool(search_provider=provider).run(
        "search",
        {"query": "UTA 路线", "max_results": 3},
    )

    assert provider.seen_query == "UTA 路线"
    assert provider.seen_max_results == 3
    assert result["message"] == "找到 1 条搜索结果"
    assert result["query"] == "UTA 路线"
    assert result["provider"] == "fake"
    assert result["sources"] == ["https://example.com/result"]
    assert result["search_results"][0]["title"] == "测试结果"


def test_search_tool_extracts_query_from_chinese_task():
    provider = FakeSearchProvider()

    SearchTool(search_provider=provider).run(
        "search",
        {"user_input": "请帮我调研 UTA Agent 框架下一步路线"},
    )

    assert provider.seen_query == "UTA Agent 框架下一步路线"


def test_search_tool_strips_live_search_prefix_from_chinese_task():
    provider = FakeSearchProvider()

    SearchTool(search_provider=provider).run(
        "search",
        {"user_input": "联网搜索包头市的介绍"},
    )

    assert provider.seen_query == "包头市的介绍"


def test_search_tool_handles_weather_query_without_generic_search():
    search_provider = FakeSearchProvider()
    weather_provider = FakeWeatherProvider()

    result = SearchTool(
        search_provider=search_provider,
        weather_provider=weather_provider,
    ).run(
        "search",
        {"user_input": "联网搜索包头今日天气状况"},
    )

    assert search_provider.seen_query is None
    assert weather_provider.seen_city == "包头"
    assert result["message"] == "获取到 包头 当前天气"
    assert result["provider"] == "fake-weather"
    assert result["weather_result"]["weather_text"] == "晴"
    assert result["search_results"][0]["title"] == "包头 今日天气"
    assert result["sources"] == ["https://example.com/weather"]


def test_search_tool_returns_empty_results():
    class EmptyProvider:
        provider_name = "empty"

        def search(self, query, max_results=5):
            return SearchResponse(query=query, provider=self.provider_name, results=[])

    result = SearchTool(search_provider=EmptyProvider()).run(
        "search",
        {"user_input": "调研 不存在的主题"},
    )

    assert result["message"] == "找到 0 条搜索结果"
    assert result["search_results"] == []
    assert result["sources"] == []

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

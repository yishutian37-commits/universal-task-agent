from __future__ import annotations

from search_providers.base_search_provider import BaseSearchProvider, SearchResponse, SearchResult


class FixtureSearchProvider(BaseSearchProvider):
    provider_name = "fixture"

    def search(self, query: str, max_results: int = 5) -> SearchResponse:
        normalized_query = query.strip() or "UTA Agent"
        results = [
            SearchResult(
                title="UTA Agent Loop 学习路线",
                url="https://example.com/uta-agent-loop",
                snippet=f"{normalized_query} 可以先从 Task Parser、Planner、Loop、Verifier 和 Memory 的闭环理解。",
                source="fixture",
            ),
            SearchResult(
                title="Agent 调研任务设计",
                url="https://example.com/agent-research-task",
                snippet="调研任务需要把搜索结果、来源列表和不确定性说明放进同一份报告。",
                source="fixture",
            ),
            SearchResult(
                title="Search Provider 抽象",
                url="https://example.com/search-provider",
                snippet="可插拔 Provider 能让测试使用 fixture，生产环境再切到真实 HTTP 搜索接口。",
                source="fixture",
            ),
        ]
        return SearchResponse(
            query=normalized_query,
            results=results[: max(0, max_results)],
            provider=self.provider_name,
        )

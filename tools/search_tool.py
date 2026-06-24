from __future__ import annotations

import re
from typing import Any

from search_providers.base_search_provider import BaseSearchProvider, response_to_dict
from search_providers.factory import build_search_provider
from tools.base_tool import BaseTool


class SearchTool(BaseTool):
    name = "search_tool"
    description = "Search external sources through a configurable SearchProvider."

    def __init__(self, search_provider: BaseSearchProvider | None = None):
        self.search_provider = search_provider if search_provider is not None else build_search_provider()

    def run(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        del action_name
        query = self._query_from_params(params)
        max_results = int(params.get("max_results") or 5)
        response = self.search_provider.search(query, max_results=max_results)
        payload = response_to_dict(response)
        search_results = payload["results"]
        sources = [
            item["url"]
            for item in search_results
            if item.get("url")
        ]
        return {
            "message": f"找到 {len(search_results)} 条搜索结果",
            "query": payload["query"],
            "search_results": search_results,
            "sources": sources,
            "provider": payload["provider"],
        }

    def _query_from_params(self, params: dict[str, Any]) -> str:
        explicit = str(params.get("query") or "").strip()
        if explicit:
            return explicit
        text = str(params.get("user_input") or params.get("goal") or "").strip()
        text = re.sub(
            r"^(?:请|帮我|请帮我|麻烦)?(?:联网|上网|网络|互联网|在线)?(?:搜索|调研|查找|研究|查询)",
            "",
            text,
        ).strip()
        return text or "UTA Agent"

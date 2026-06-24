from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from search_providers.base_search_provider import BaseSearchProvider, SearchResponse, SearchResult


class HttpSearchProvider(BaseSearchProvider):
    provider_name = "http"

    def __init__(self, api_url: str, api_key: str, timeout_seconds: int = 10):
        if not api_url:
            raise ValueError("SEARCH_API_URL is required")
        if not api_key:
            raise ValueError("SEARCH_API_KEY is required")
        self.api_url = api_url
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def search(self, query: str, max_results: int = 5) -> SearchResponse:
        payload = json.dumps(
            {"query": query, "max_results": max_results},
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            self.api_url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                parsed = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"搜索请求失败：{exc}") from exc

        return SearchResponse(
            query=query,
            results=self._results_from_payload(parsed, max_results),
            provider=self.provider_name,
        )

    def _results_from_payload(self, payload: Any, max_results: int) -> list[SearchResult]:
        if not isinstance(payload, dict):
            return []
        raw_results = payload.get("results", [])
        if not isinstance(raw_results, list):
            return []
        results = []
        for item in raw_results[: max(0, max_results)]:
            if not isinstance(item, dict):
                continue
            results.append(
                SearchResult(
                    title=str(item.get("title") or ""),
                    url=str(item.get("url") or ""),
                    snippet=str(item.get("snippet") or ""),
                    source=str(item.get("source") or ""),
                )
            )
        return results

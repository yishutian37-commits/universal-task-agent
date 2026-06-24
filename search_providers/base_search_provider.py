from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class SearchResponse:
    query: str
    results: list[SearchResult]
    provider: str


class BaseSearchProvider:
    provider_name = "base"

    def search(self, query: str, max_results: int = 5) -> SearchResponse:
        raise NotImplementedError


def response_to_dict(response: SearchResponse) -> dict[str, Any]:
    return {
        "query": response.query,
        "provider": response.provider,
        "results": [result.to_dict() for result in response.results],
    }

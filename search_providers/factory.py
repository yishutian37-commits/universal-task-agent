from __future__ import annotations

import os

from search_providers.base_search_provider import BaseSearchProvider
from search_providers.fixture_search_provider import FixtureSearchProvider
from search_providers.http_search_provider import HttpSearchProvider


def build_search_provider() -> BaseSearchProvider:
    provider = os.getenv("SEARCH_PROVIDER", "fixture").strip().lower()
    if provider == "fixture":
        return FixtureSearchProvider()
    if provider == "http":
        return HttpSearchProvider(
            api_url=os.getenv("SEARCH_API_URL", "").strip(),
            api_key=os.getenv("SEARCH_API_KEY", "").strip(),
            timeout_seconds=int(os.getenv("SEARCH_TIMEOUT_SECONDS", "10")),
        )
    raise ValueError(f"Unsupported SEARCH_PROVIDER: {provider}")

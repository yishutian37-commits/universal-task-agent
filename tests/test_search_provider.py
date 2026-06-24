import json
import urllib.error

import pytest

from search_providers.factory import build_search_provider
from search_providers.fixture_search_provider import FixtureSearchProvider
from search_providers.http_search_provider import HttpSearchProvider


def test_fixture_search_provider_returns_stable_results():
    response = FixtureSearchProvider().search("UTA Agent 路线", max_results=2)

    assert response.query == "UTA Agent 路线"
    assert response.provider == "fixture"
    assert len(response.results) == 2
    assert response.results[0].title
    assert response.results[0].url.startswith("https://")
    assert response.results[0].snippet


def test_factory_defaults_to_fixture(monkeypatch):
    monkeypatch.delenv("SEARCH_PROVIDER", raising=False)

    provider = build_search_provider()

    assert isinstance(provider, FixtureSearchProvider)


def test_factory_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDER", "unknown-provider")

    with pytest.raises(ValueError, match="Unsupported SEARCH_PROVIDER"):
        build_search_provider()


def test_http_search_provider_requires_url():
    with pytest.raises(ValueError, match="SEARCH_API_URL is required"):
        HttpSearchProvider(api_url="", api_key="secret")


def test_http_search_provider_requires_key():
    with pytest.raises(ValueError, match="SEARCH_API_KEY is required"):
        HttpSearchProvider(api_url="https://search.example.test", api_key="")


def test_http_search_provider_parses_results(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(
                {
                    "results": [
                        {
                            "title": "结果一",
                            "url": "https://example.com/one",
                            "snippet": "第一条摘要",
                            "source": "example",
                        }
                    ]
                },
                ensure_ascii=False,
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["authorization"] = request.headers["Authorization"]
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    response = HttpSearchProvider(
        api_url="https://search.example.test",
        api_key="secret",
        timeout_seconds=7,
    ).search("UTA", max_results=3)

    assert captured["url"] == "https://search.example.test"
    assert captured["body"] == {"query": "UTA", "max_results": 3}
    assert captured["authorization"] == "Bearer secret"
    assert captured["timeout"] == 7
    assert response.provider == "http"
    assert response.results[0].title == "结果一"
    assert response.results[0].url == "https://example.com/one"
    assert response.results[0].snippet == "第一条摘要"


def test_http_search_provider_reports_network_errors(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.URLError("timeout")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    provider = HttpSearchProvider(api_url="https://search.example.test", api_key="secret")

    with pytest.raises(RuntimeError, match="搜索请求失败"):
        provider.search("UTA")

import json
import subprocess
import urllib.error

import pytest

from search_providers.bing_search_provider import BingSearchProvider
from search_providers.factory import build_search_provider
from search_providers.duckduckgo_search_provider import DuckDuckGoSearchProvider
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


def test_factory_defaults_to_bing(monkeypatch):
    monkeypatch.delenv("SEARCH_PROVIDER", raising=False)

    provider = build_search_provider()

    assert isinstance(provider, BingSearchProvider)


def test_factory_builds_duckduckgo_provider(monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDER", "duckduckgo")

    provider = build_search_provider()

    assert isinstance(provider, DuckDuckGoSearchProvider)


def test_factory_builds_fixture_provider(monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDER", "fixture")

    provider = build_search_provider()

    assert isinstance(provider, FixtureSearchProvider)


def test_duckduckgo_search_provider_parses_html_results(monkeypatch):
    captured = {}
    html = """
    <html><body>
      <a class="result__a" href="/l/?uddg=https%3A%2F%2Fexample.com%2Fone&amp;rut=abc">
        示例结果一
      </a>
      <a class="result__snippet">第一条摘要</a>
      <a class="result__a" href="https://example.org/two">示例结果二</a>
      <div class="result__snippet">第二条摘要</div>
    </body></html>
    """

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return html.encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    response = DuckDuckGoSearchProvider(timeout_seconds=6).search("UTA Agent", max_results=2)

    assert captured["url"].startswith("https://html.duckduckgo.com/html/?")
    assert "q=UTA+Agent" in captured["url"]
    assert captured["headers"]["User-agent"].startswith("Mozilla/")
    assert captured["timeout"] == 6
    assert response.provider == "duckduckgo"
    assert [result.title for result in response.results] == ["示例结果一", "示例结果二"]
    assert response.results[0].url == "https://example.com/one"
    assert response.results[0].snippet == "第一条摘要"
    assert response.results[0].source == "example.com"


def test_bing_search_provider_parses_html_results(monkeypatch):
    captured = {}
    html = """
    <html><body>
      <li class="b_algo">
        <h2><a href="https://example.com/one">示例结果一</a></h2>
        <div class="b_caption"><p>第一条摘要</p></div>
      </li>
      <li class="b_algo">
        <h2><a href="https://example.org/two">示例结果二</a></h2>
        <div class="b_caption"><p>第二条摘要</p></div>
      </li>
    </body></html>
    """

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return html.encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    response = BingSearchProvider(timeout_seconds=8).search("UTA Agent", max_results=2)

    assert captured["url"].startswith("https://www.bing.com/search?")
    assert "q=UTA+Agent" in captured["url"]
    assert captured["headers"]["User-agent"].startswith("Mozilla/")
    assert captured["timeout"] == 8
    assert response.provider == "bing"
    assert [result.title for result in response.results] == ["示例结果一", "示例结果二"]
    assert response.results[0].url == "https://example.com/one"
    assert response.results[0].snippet == "第一条摘要"
    assert response.results[0].source == "example.com"


def test_bing_search_provider_uses_curl_fallback_when_urllib_fails(monkeypatch):
    captured = {}
    html = """
    <html><body>
      <li class="b_algo">
        <h2><a href="https://example.com/one">示例结果一</a></h2>
        <div class="b_caption"><p>第一条摘要</p></div>
      </li>
    </body></html>
    """

    def fake_urlopen(request, timeout):
        raise urllib.error.URLError("ssl timeout")

    def fake_which(name):
        return "/usr/bin/curl" if name == "curl" else None

    def fake_run(args, input, text, capture_output, timeout):
        captured["args"] = args
        captured["config"] = input
        captured["timeout"] = timeout
        return subprocess.CompletedProcess(args, 0, stdout=f"{html}\n200", stderr="")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("shutil.which", fake_which)
    monkeypatch.setattr("subprocess.run", fake_run)

    response = BingSearchProvider(timeout_seconds=5).search("UTA Agent", max_results=1)

    assert captured["args"] == ["/usr/bin/curl", "--config", "-"]
    assert "url = \"https://www.bing.com/search?q=UTA+Agent\"" in captured["config"]
    assert "write-out = \"\\n%{http_code}\"" in captured["config"]
    assert captured["timeout"] == 10
    assert response.results[0].title == "示例结果一"


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

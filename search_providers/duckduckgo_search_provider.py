from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urlencode, urljoin, urlparse
import urllib.error
import urllib.request

from search_providers.base_search_provider import (
    BaseSearchProvider,
    SearchResponse,
    SearchResult,
)


class _DuckDuckGoHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[SearchResult] = []
        self._capture: str | None = None
        self._buffer: list[str] = []
        self._pending_href = ""
        self._active_result_index: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name: value or "" for name, value in attrs}
        css_class = attr_map.get("class", "")
        if tag == "a" and "result__a" in css_class:
            self._capture = "title"
            self._buffer = []
            self._pending_href = attr_map.get("href", "")
            return

        if tag in {"a", "div"} and "result__snippet" in css_class:
            self._capture = "snippet"
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._capture is not None:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capture == "title" and tag == "a":
            title = self._clean_text("".join(self._buffer))
            url = _normalize_result_url(self._pending_href)
            if title and url:
                self.results.append(
                    SearchResult(
                        title=title,
                        url=url,
                        snippet="",
                        source=_source_from_url(url),
                    )
                )
                self._active_result_index = len(self.results) - 1
            self._reset_capture()
            return

        if self._capture == "snippet" and tag in {"a", "div"}:
            snippet = self._clean_text("".join(self._buffer))
            if snippet and self._active_result_index is not None:
                previous = self.results[self._active_result_index]
                self.results[self._active_result_index] = SearchResult(
                    title=previous.title,
                    url=previous.url,
                    snippet=snippet,
                    source=previous.source,
                )
            self._reset_capture()

    def _reset_capture(self) -> None:
        self._capture = None
        self._buffer = []
        self._pending_href = ""

    def _clean_text(self, text: str) -> str:
        return " ".join(text.split())


class DuckDuckGoSearchProvider(BaseSearchProvider):
    provider_name = "duckduckgo"

    def __init__(
        self,
        search_url: str = "https://html.duckduckgo.com/html/",
        timeout_seconds: int = 10,
    ) -> None:
        self.search_url = search_url
        self.timeout_seconds = timeout_seconds

    def search(self, query: str, max_results: int = 5) -> SearchResponse:
        normalized_query = query.strip() or "UTA Agent"
        url = f"{self.search_url}?{urlencode({'q': normalized_query})}"
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                html = response.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"联网搜索失败：{exc}") from exc

        parser = _DuckDuckGoHTMLParser()
        parser.feed(html)
        limit = max(0, max_results)
        return SearchResponse(
            query=normalized_query,
            provider=self.provider_name,
            results=parser.results[:limit],
        )


def _normalize_result_url(href: str) -> str:
    if not href:
        return ""
    absolute = urljoin("https://duckduckgo.com", href)
    parsed = urlparse(absolute)
    query = parse_qs(parsed.query)
    redirected = query.get("uddg", [""])[0]
    if redirected:
        return unquote(redirected)
    return absolute


def _source_from_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.removeprefix("www.")

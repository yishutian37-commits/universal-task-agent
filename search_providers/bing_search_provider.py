from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urlencode, urlparse
import shutil
import subprocess
import urllib.error
import urllib.request

from search_providers.base_search_provider import (
    BaseSearchProvider,
    SearchResponse,
    SearchResult,
)


class _BingHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[SearchResult] = []
        self._current: dict[str, str] | None = None
        self._in_heading = False
        self._in_caption = False
        self._capture: str | None = None
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name: value or "" for name, value in attrs}
        css_class = attr_map.get("class", "")

        if tag == "li" and "b_algo" in css_class:
            self._finish_current()
            self._current = {"title": "", "url": "", "snippet": ""}
            return

        if self._current is None:
            return

        if tag == "h2":
            self._in_heading = True
            return

        if self._in_heading and tag == "a":
            self._current["url"] = attr_map.get("href", "")
            self._capture = "title"
            self._buffer = []
            return

        if tag == "div" and "b_caption" in css_class:
            self._in_caption = True
            return

        if self._in_caption and tag == "p":
            self._capture = "snippet"
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._capture is not None:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._current is None:
            return

        if self._capture == "title" and tag == "a":
            self._current["title"] = self._clean_text("".join(self._buffer))
            self._reset_capture()
            return

        if tag == "h2":
            self._in_heading = False
            return

        if self._capture == "snippet" and tag == "p":
            self._current["snippet"] = self._clean_text("".join(self._buffer))
            self._reset_capture()
            return

        if tag == "div" and self._in_caption:
            self._in_caption = False
            return

        if tag == "li":
            self._finish_current()

    def close(self) -> None:
        super().close()
        self._finish_current()

    def _finish_current(self) -> None:
        if self._current is None:
            return
        title = self._current.get("title", "")
        url = self._current.get("url", "")
        if title and url:
            self.results.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=self._current.get("snippet", ""),
                    source=_source_from_url(url),
                )
            )
        self._current = None
        self._in_heading = False
        self._in_caption = False
        self._reset_capture()

    def _reset_capture(self) -> None:
        self._capture = None
        self._buffer = []

    def _clean_text(self, text: str) -> str:
        return " ".join(text.split())


class BingSearchProvider(BaseSearchProvider):
    provider_name = "bing"

    def __init__(
        self,
        search_url: str = "https://www.bing.com/search",
        timeout_seconds: int = 10,
    ) -> None:
        self.search_url = search_url
        self.timeout_seconds = timeout_seconds

    def search(self, query: str, max_results: int = 5) -> SearchResponse:
        normalized_query = query.strip() or "UTA Agent"
        url = f"{self.search_url}?{urlencode({'q': normalized_query})}"

        try:
            html = self._fetch_with_urllib(url)
        except RuntimeError:
            html = self._fetch_with_curl(url)

        parser = _BingHTMLParser()
        parser.feed(html)
        parser.close()
        limit = max(0, max_results)
        return SearchResponse(
            query=normalized_query,
            provider=self.provider_name,
            results=parser.results[:limit],
        )

    def _fetch_with_urllib(self, url: str) -> str:
        request = urllib.request.Request(
            url,
            headers=self._headers(),
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return response.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"联网搜索 urllib 失败：{exc}") from exc

    def _fetch_with_curl(self, url: str) -> str:
        curl_path = shutil.which("curl")
        if curl_path is None:
            raise RuntimeError("联网搜索失败：curl 不可用")

        config = self._curl_config(url)
        try:
            completed = subprocess.run(
                [curl_path, "--config", "-"],
                input=config,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds + 5,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"联网搜索 curl 超时：{self.timeout_seconds} 秒") from exc

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(f"联网搜索 curl 失败：{detail}")

        body, status_code = self._split_curl_response(completed.stdout)
        if status_code >= 400:
            raise RuntimeError(f"联网搜索 HTTP {status_code}: {body[:200]}")
        return body

    def _curl_config(self, url: str) -> str:
        lines = [
            "silent",
            "show-error",
            "location",
            "http1.1",
            f"max-time = {self.timeout_seconds}",
            "url = " + self._curl_config_value(url),
            "header = " + self._curl_config_value(f"User-Agent: {self._headers()['User-Agent']}"),
            "header = " + self._curl_config_value(f"Accept: {self._headers()['Accept']}"),
            "header = " + self._curl_config_value(
                f"Accept-Language: {self._headers()['Accept-Language']}"
            ),
            "write-out = " + self._curl_config_value("\n%{http_code}"),
        ]
        return "\n".join(lines) + "\n"

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
        }

    @staticmethod
    def _curl_config_value(value: str) -> str:
        escaped = (
            str(value)
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\r", "\\r")
            .replace("\n", "\\n")
        )
        return f'"{escaped}"'

    @staticmethod
    def _split_curl_response(output: str) -> tuple[str, int]:
        body, separator, status_text = output.rpartition("\n")
        if not separator or not status_text.isdigit():
            raise RuntimeError("联网搜索 curl 响应无 HTTP 状态码")
        return body, int(status_text)


def _source_from_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.removeprefix("www.")

# UTA V1.1 Research Search API Implementation Plan

> **For agentic workers / 给执行 Agent 的说明：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐步执行本计划。步骤使用 checkbox（`- [ ]`）记录进度。

**Goal / 目标：** 实现 UTA V1.1：新增 research 调研任务、可插拔 Search Provider、`search_tool`、带来源调研报告、同步 FastAPI 接口、文档/demo/tag。

**Architecture / 架构：** 搜索能力放在 `search_providers/` 和 `tools/search_tool.py`，核心 Parser/Planner/Router 只负责识别和编排 research 任务。报告和校验沿用现有 `ReportTool` / `Verifier` 边界。FastAPI 通过 `api/server.py` 调用同一条 `main.run_task()` 核心链路，并把运行记录读取逻辑迁移到 `core/history_store.py` 供 desktop 和 API 共用。

**Tech Stack / 技术栈：** Python 3.12、pytest、dataclass、urllib 标准库 HTTP、FastAPI、Uvicorn、Git tag。

---

## 文件结构

新增：

- `search_providers/__init__.py`：导出 Search Provider 类型和 factory。
- `search_providers/base_search_provider.py`：定义 `SearchResult`、`SearchResponse`、`BaseSearchProvider`、`response_to_dict()`。
- `search_providers/fixture_search_provider.py`：离线测试和 demo 用 fixture 搜索。
- `search_providers/http_search_provider.py`：通过环境变量配置的 HTTP 搜索 Provider。
- `search_providers/factory.py`：根据 `SEARCH_PROVIDER` 创建 Provider。
- `tools/search_tool.py`：核心搜索工具。
- `core/history_store.py`：运行记录读取逻辑，从 desktop 抽到核心层。
- `api/__init__.py`：API 包标记。
- `api/server.py`：FastAPI 同步接口。
- `requirements-api.txt`：FastAPI 运行和测试依赖。
- `tests/test_search_provider.py`：Search Provider 测试。
- `tests/test_search_tool.py`：SearchTool 测试。
- `tests/test_api_server.py`：FastAPI 测试。

修改：

- `core/task_parser.py`：支持 `research`。
- `core/planner.py`：生成 research 两步计划。
- `core/router.py`：把搜索类 step 路由到 `search_tool`。
- `tools/report_tool.py`：把搜索结果生成带来源调研报告。
- `core/verifier.py`：校验调研报告结构和来源 URL。
- `tools/registry.py`：注册 `search_tool`。
- `desktop/runner.py`：桌面 runner 的 registry 注册 `search_tool`，但不改桌面 UI。
- `desktop/history_store.py`：改成从 `core.history_store` 兼容导入。
- `tests/test_task_parser.py`：补 research fallback。
- `tests/test_planner.py`：补 research plan。
- `tests/test_router.py`：补 search routing。
- `tests/test_report_tool.py`：补 research report。
- `tests/test_verifier.py`：补 research verifier。
- `tests/test_main.py`：补 CLI research 跑通 state/log。
- `tests/test_desktop_history_store.py`：继续验证 desktop 兼容导入后行为不变。
- `README.md`：新增 V1.1 research / search / FastAPI 说明。
- `CHANGELOG.md`：新增 `v1.1-research-search-api`。

不修改：

- 不新增桌面端页面或设置项。
- 不接 TAM。
- 不做异步队列。
- 不做网页全文抓取。

---

## Task 0：确认分支、安装 API 依赖、跑基线

**文件：**
- 新建：`requirements-api.txt`

- [ ] **Step 1：确认当前分支和状态**

运行：

```bash
git branch --show-current
git status -sb
```

预期：

```text
codex/v1.1-research-search-api
## codex/v1.1-research-search-api
```

- [ ] **Step 2：新增 API 依赖文件**

新建 `requirements-api.txt`：

```text
fastapi
uvicorn
httpx
```

- [ ] **Step 3：安装 API 依赖**

运行：

```bash
.venv/bin/python -m pip install -r requirements-api.txt
```

预期：

```text
Successfully installed ...
```

如果本机已安装，输出可以是 `Requirement already satisfied`。

- [ ] **Step 4：跑基线测试**

运行：

```bash
.venv/bin/python -m pytest -q
```

预期：

```text
171 passed
```

- [ ] **Step 5：提交依赖文件**

运行：

```bash
git add requirements-api.txt
git commit -m "chore: add api requirements"
```

---

## Task 1：Search Provider 抽象与实现

**文件：**
- 新建：`search_providers/__init__.py`
- 新建：`search_providers/base_search_provider.py`
- 新建：`search_providers/fixture_search_provider.py`
- 新建：`search_providers/http_search_provider.py`
- 新建：`search_providers/factory.py`
- 新建：`tests/test_search_provider.py`

- [ ] **Step 1：写 Search Provider 失败测试**

新建 `tests/test_search_provider.py`：

```python
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
```

- [ ] **Step 2：确认测试失败**

运行：

```bash
.venv/bin/python -m pytest tests/test_search_provider.py -q
```

预期：

```text
ModuleNotFoundError: No module named 'search_providers'
```

- [ ] **Step 3：实现 base search provider**

新建 `search_providers/base_search_provider.py`：

```python
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
```

- [ ] **Step 4：实现 fixture provider**

新建 `search_providers/fixture_search_provider.py`：

```python
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
```

- [ ] **Step 5：实现 HTTP provider**

新建 `search_providers/http_search_provider.py`：

```python
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
```

- [ ] **Step 6：实现 factory 和导出**

新建 `search_providers/factory.py`：

```python
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
```

新建 `search_providers/__init__.py`：

```python
from search_providers.base_search_provider import (
    BaseSearchProvider,
    SearchResponse,
    SearchResult,
    response_to_dict,
)
from search_providers.factory import build_search_provider
from search_providers.fixture_search_provider import FixtureSearchProvider
from search_providers.http_search_provider import HttpSearchProvider

__all__ = [
    "BaseSearchProvider",
    "FixtureSearchProvider",
    "HttpSearchProvider",
    "SearchResponse",
    "SearchResult",
    "build_search_provider",
    "response_to_dict",
]
```

- [ ] **Step 7：跑 provider 测试**

运行：

```bash
.venv/bin/python -m pytest tests/test_search_provider.py -q
```

预期：

```text
7 passed
```

- [ ] **Step 8：提交 Search Provider**

运行：

```bash
git add search_providers tests/test_search_provider.py
git commit -m "feat: add search providers"
```

---

## Task 2：SearchTool 与工具注册

**文件：**
- 新建：`tools/search_tool.py`
- 新建：`tests/test_search_tool.py`
- 修改：`tools/registry.py`
- 修改：`desktop/runner.py`

- [ ] **Step 1：写 SearchTool 失败测试**

新建 `tests/test_search_tool.py`：

```python
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
```

- [ ] **Step 2：确认测试失败**

运行：

```bash
.venv/bin/python -m pytest tests/test_search_tool.py -q
```

预期：

```text
ModuleNotFoundError: No module named 'tools.search_tool'
```

- [ ] **Step 3：实现 SearchTool**

新建 `tools/search_tool.py`：

```python
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
        text = re.sub(r"^(请|帮我|请帮我|麻烦)?(调研|搜索|查找|研究)", "", text).strip()
        return text or "UTA Agent"
```

- [ ] **Step 4：注册工具**

修改 `tools/registry.py`：

```python
from tools.file_tool import FileTool
from tools.mock_tool import MockTool
from tools.report_tool import ReportTool
from tools.search_tool import SearchTool
from tools.table_tool import TableTool
from tools.text_tool import TextTool


TOOL_REGISTRY = {
    "mock_tool": MockTool(),
    "file_tool": FileTool(),
    "text_tool": TextTool(),
    "table_tool": TableTool(),
    "report_tool": ReportTool(),
    "search_tool": SearchTool(),
}
```

修改 `desktop/runner.py` 的 `build_tool_registry()`：

```python
def build_tool_registry() -> dict[str, Any]:
    from tools.file_tool import FileTool
    from tools.mock_tool import MockTool
    from tools.report_tool import ReportTool
    from tools.search_tool import SearchTool
    from tools.table_tool import TableTool
    from tools.text_tool import TextTool

    return {
        "mock_tool": MockTool(),
        "file_tool": FileTool(),
        "text_tool": TextTool(),
        "table_tool": TableTool(),
        "report_tool": ReportTool(),
        "search_tool": SearchTool(),
    }
```

- [ ] **Step 5：跑 SearchTool 测试**

运行：

```bash
.venv/bin/python -m pytest tests/test_search_tool.py tests/test_executor.py -q
```

预期：

```text
pass
```

- [ ] **Step 6：提交 SearchTool**

运行：

```bash
git add tools/search_tool.py tools/registry.py desktop/runner.py tests/test_search_tool.py
git commit -m "feat: add search tool"
```

---

## Task 3：核心 research 任务编排

**文件：**
- 修改：`core/task_parser.py`
- 修改：`core/planner.py`
- 修改：`core/router.py`
- 修改：`tests/test_task_parser.py`
- 修改：`tests/test_planner.py`
- 修改：`tests/test_router.py`

- [ ] **Step 1：写 Parser research 测试**

在 `tests/test_task_parser.py` 增加：

```python
def test_task_parser_fallback_detects_research_when_llm_fails():
    parser = TaskParser(llm_client=FailingLLMClient())

    task = parser.parse("task_test", "请帮我调研 UTA Agent 框架下一步路线")

    assert task.task_type == "research"
    assert task.intent == "research_topic"
    assert task.input_type == "text"
    assert task.expected_output == "research_report"
```

如果文件中没有 `FailingLLMClient`，增加：

```python
class FailingLLMClient:
    def chat_json(self, system_prompt, user_prompt, schema=None):
        raise RuntimeError("LLM unavailable")
```

- [ ] **Step 2：写 Planner research 测试**

在 `tests/test_planner.py` 增加：

```python
def test_planner_creates_research_plan():
    task = Task(
        task_id="task_test",
        user_input="调研 UTA Agent 框架",
        task_type="research",
        intent="research_topic",
        input_type="text",
        expected_output="research_report",
    )

    plan = Planner().create_plan(task)

    assert [step.goal for step in plan.steps] == [
        "搜索相关资料",
        "生成带来源的调研报告",
    ]
```

- [ ] **Step 3：写 Router search 测试**

在 `tests/test_router.py` 增加：

```python
def test_router_routes_search_goal_to_search_tool():
    state = AgentState(task_id="task_test", user_input="调研 UTA Agent 框架")
    step = PlanStep(step_id=1, goal="搜索相关资料")

    action = Router().choose_tool(state, step)

    assert action.tool_name == "search_tool"
    assert action.action_name == "search"
```

- [ ] **Step 4：确认目标测试失败**

运行：

```bash
.venv/bin/python -m pytest tests/test_task_parser.py tests/test_planner.py tests/test_router.py -q
```

预期：

```text
FAIL
```

失败原因应包含 `research` 尚未识别、计划不匹配或路由仍使用 `mock_tool`。

- [ ] **Step 5：实现 TaskParser research**

修改 `core/task_parser.py`：

```python
ALLOWED_TASK_TYPES = {"summarize", "data_analysis", "research", "unknown"}
```

修改 `_system_prompt()` 中允许类型为：

```python
"task_type 只能是 summarize、data_analysis、research、unknown。"
```

在 `_fallback_task()` 中，在 `summarize` 分支前增加：

```python
if guessed_type == "research":
    return Task(
        task_id=task_id,
        user_input=user_input,
        task_type="research",
        intent="research_topic",
        input_type="text",
        expected_output="research_report",
        constraints=[],
        missing_info=[],
    )
```

修改 `_guess_task_type()`：

```python
if any(marker in user_input for marker in ["调研", "搜索", "查找", "资料", "来源", "研究", "竞品", "趋势"]):
    return "research"
```

- [ ] **Step 6：实现 Planner research**

修改 `core/planner.py` 的 `_goals_for()`：

```python
if task_type == "research":
    return ["搜索相关资料", "生成带来源的调研报告"]
```

- [ ] **Step 7：实现 Router search 规则**

修改 `core/router.py` 的 `RULES`，把搜索规则放在报告规则前：

```python
(("搜索", "调研", "查找", "资料", "来源", "研究", "竞品", "趋势"), "search_tool", "search"),
```

- [ ] **Step 8：跑目标测试**

运行：

```bash
.venv/bin/python -m pytest tests/test_task_parser.py tests/test_planner.py tests/test_router.py -q
```

预期：

```text
pass
```

- [ ] **Step 9：提交 research 编排**

运行：

```bash
git add core/task_parser.py core/planner.py core/router.py tests/test_task_parser.py tests/test_planner.py tests/test_router.py
git commit -m "feat: add research task routing"
```

---

## Task 4：调研报告生成与校验

**文件：**
- 修改：`tools/report_tool.py`
- 修改：`core/verifier.py`
- 修改：`tests/test_report_tool.py`
- 修改：`tests/test_verifier.py`

- [ ] **Step 1：写 ReportTool research 测试**

在 `tests/test_report_tool.py` 增加：

```python
def test_report_tool_generates_research_report_with_sources():
    result = ReportTool().run(
        "generate",
        {
            "previous_result": {
                "query": "UTA Agent",
                "search_results": [
                    {
                        "title": "UTA 路线",
                        "url": "https://example.com/uta",
                        "snippet": "UTA 应先跑通核心 Agent Loop。",
                        "source": "fixture",
                    }
                ],
            }
        },
    )

    report = result["report_markdown"]

    assert "## 结论" in report
    assert "## 关键发现" in report
    assert "## 来源" in report
    assert "## 注意事项" in report
    assert "[UTA 路线](https://example.com/uta)" in report
    assert result["source_search_results"][0]["url"] == "https://example.com/uta"


def test_report_tool_handles_empty_research_results():
    result = ReportTool().run(
        "generate",
        {"previous_result": {"query": "不存在的主题", "search_results": []}},
    )

    assert "未找到可用来源" in result["report_markdown"]
    assert result["source_search_results"] == []
```

- [ ] **Step 2：写 Verifier research 测试**

在 `tests/test_verifier.py` 增加：

```python
def test_verifier_accepts_research_report_with_sources():
    state = AgentState(
        task_id="task_test",
        user_input="调研 UTA",
        task_type="research",
        intent="research_topic",
    )
    result = ToolResult(
        success=True,
        tool_name="report_tool",
        action_name="generate",
        result={
            "message": (
                "## 结论\n初步结论。\n\n"
                "## 关键发现\n- 发现一。\n\n"
                "## 来源\n- [来源](https://example.com/uta)：摘要\n\n"
                "## 注意事项\n当前报告只基于搜索摘要。"
            ),
            "source_search_results": [{"url": "https://example.com/uta"}],
        },
    )

    check = Verifier().check(state, PlanStep(step_id=2, goal="生成带来源的调研报告"), result)

    assert check.passed is True


def test_verifier_rejects_research_report_missing_source_url():
    state = AgentState(
        task_id="task_test",
        user_input="调研 UTA",
        task_type="research",
        intent="research_topic",
    )
    result = ToolResult(
        success=True,
        tool_name="report_tool",
        action_name="generate",
        result={
            "message": (
                "## 结论\n初步结论。\n\n"
                "## 关键发现\n- 发现一。\n\n"
                "## 来源\n- 来源缺少链接\n\n"
                "## 注意事项\n当前报告只基于搜索摘要。"
            ),
            "source_search_results": [{"url": "https://example.com/uta"}],
        },
    )

    check = Verifier().check(state, PlanStep(step_id=2, goal="生成带来源的调研报告"), result)

    assert check.passed is False
    assert "来源缺少 URL：https://example.com/uta" in check.failed_reasons


def test_verifier_accepts_empty_research_report_when_no_sources_available():
    state = AgentState(
        task_id="task_test",
        user_input="调研 不存在的主题",
        task_type="research",
        intent="research_topic",
    )
    result = ToolResult(
        success=True,
        tool_name="report_tool",
        action_name="generate",
        result={
            "message": (
                "## 结论\n未找到可用来源。\n\n"
                "## 关键发现\n- 未找到可用来源。\n\n"
                "## 来源\n未找到可用来源。\n\n"
                "## 注意事项\n当前报告只基于搜索摘要。"
            ),
            "source_search_results": [],
        },
    )

    check = Verifier().check(state, PlanStep(step_id=2, goal="生成带来源的调研报告"), result)

    assert check.passed is True
```

- [ ] **Step 3：确认目标测试失败**

运行：

```bash
.venv/bin/python -m pytest tests/test_report_tool.py tests/test_verifier.py -q
```

预期：

```text
FAIL
```

- [ ] **Step 4：实现 ReportTool research 分支**

修改 `tools/report_tool.py`，在 table 分支前增加：

```python
if isinstance(previous, dict) and "search_results" in previous:
    report = self._research_report(previous)
    return {
        "message": report,
        "report_markdown": report,
        "source_search_results": previous.get("search_results", []),
    }
```

在 `ReportTool` 中增加：

```python
def _research_report(self, search_payload: dict[str, Any]) -> str:
    query = str(search_payload.get("query") or "调研主题")
    results = search_payload.get("search_results") or []
    if not results:
        return "\n\n".join(
            [
                "## 结论\n未找到可用来源。",
                "## 关键发现\n- 未找到可用来源。",
                "## 来源\n未找到可用来源。",
                "## 注意事项\n当前报告只基于搜索摘要，不等同于阅读全文后的事实核验。",
            ]
        )

    findings = "\n".join(
        f"- {item.get('snippet') or item.get('title') or '搜索结果未提供摘要'}"
        for item in results
    )
    sources = "\n".join(
        f"- [{item.get('title') or item.get('url')}]({item.get('url')}): {item.get('snippet') or '无摘要'}"
        for item in results
        if item.get("url")
    )
    return "\n\n".join(
        [
            f"## 结论\n基于当前搜索结果，{query} 可以先形成一份初步调研结论。",
            f"## 关键发现\n{findings}",
            f"## 来源\n{sources}",
            "## 注意事项\n当前报告只基于搜索摘要，不等同于阅读全文后的事实核验。",
        ]
    )
```

- [ ] **Step 5：实现 Verifier research 校验**

修改 `core/verifier.py`：

```python
RESEARCH_REQUIRED_SECTIONS = ["结论", "关键发现", "来源", "注意事项"]
```

在 `check()` 中 table 检查前增加：

```python
if self._should_check_research_report(state, result):
    return self._check_research_report(result)
```

增加方法：

```python
def _should_check_research_report(self, state: AgentState | None, result: ToolResult) -> bool:
    return (
        state is not None
        and state.task_type == "research"
        and result.tool_name == "report_tool"
    )

def _check_research_report(self, result: ToolResult) -> CheckResult:
    report_text = str(result.result.get("message") or result.result.get("report_markdown") or "")
    failed_reasons = []
    suggested_fix = []

    for section in RESEARCH_REQUIRED_SECTIONS:
        content = self._section_content(report_text, section, RESEARCH_REQUIRED_SECTIONS)
        if content is None:
            failed_reasons.append(f"缺少必要小节：{section}")
            suggested_fix.append(f"补齐{section}小节")
        elif not content.strip():
            failed_reasons.append(f"小节内容为空：{section}")
            suggested_fix.append(f"补充{section}小节内容")

    source_results = result.result.get("source_search_results") or []
    if source_results:
        for item in source_results:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if url and url not in report_text:
                failed_reasons.append(f"来源缺少 URL：{url}")
                suggested_fix.append(f"在来源小节补充 URL：{url}")
    elif "未找到可用来源" not in report_text:
        failed_reasons.append("无搜索结果时必须写明：未找到可用来源")
        suggested_fix.append("在结论或来源小节写明：未找到可用来源")

    return CheckResult(
        passed=not failed_reasons,
        failed_reasons=failed_reasons,
        suggested_fix=suggested_fix,
    )
```

- [ ] **Step 6：跑目标测试**

运行：

```bash
.venv/bin/python -m pytest tests/test_report_tool.py tests/test_verifier.py -q
```

预期：

```text
pass
```

- [ ] **Step 7：提交报告与校验**

运行：

```bash
git add tools/report_tool.py core/verifier.py tests/test_report_tool.py tests/test_verifier.py
git commit -m "feat: add research report verification"
```

---

## Task 5：完整 CLI research 跑通

**文件：**
- 修改：`tests/test_loop.py`
- 修改：`tests/test_main.py`
- 修改：`main.py`

- [ ] **Step 1：写 Loop research 测试**

在 `tests/test_loop.py` 增加：

```python
def test_loop_executes_research_flow():
    registry = {
        "search_tool": EchoTool(
            {
                "query": "UTA Agent",
                "search_results": [
                    {
                        "title": "UTA 路线",
                        "url": "https://example.com/uta",
                        "snippet": "UTA 应先跑通核心 Agent Loop。",
                        "source": "fixture",
                    }
                ],
                "sources": ["https://example.com/uta"],
                "provider": "fixture",
            }
        ),
        "report_tool": ReportTool(),
    }
    state = AgentState(
        task_id="task_test",
        user_input="调研 UTA Agent 框架",
        task_type="research",
        intent="research_topic",
    )

    updated = run_minimal_loop(state, tool_registry=registry)

    assert updated.status == "completed"
    assert updated.results[0].tool_name == "search_tool"
    assert updated.results[1].tool_name == "report_tool"
    assert "## 来源" in updated.final_output
```

如果 `tests/test_loop.py` 没有导入 `ReportTool`，加：

```python
from tools.report_tool import ReportTool
```

并让 `EchoTool.run()` 支持 dict message：

```python
return {
    "message": self.message if isinstance(self.message, str) else str(self.message),
    "previous_result": params.get("previous_result"),
    **(self.message if isinstance(self.message, dict) else {}),
}
```

- [ ] **Step 2：写 main research 测试**

在 `tests/test_main.py` 增加：

```python
def test_run_task_outputs_research_report_with_fixture_search(tmp_path, monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDER", "fixture")

    state = run_task(
        "调研 UTA Agent 框架下一步路线",
        output_root=tmp_path,
        task_id="task_test",
        memory_provider=False,
        skill_loader=False,
    )

    state_path = tmp_path / "states" / "task_test_state.json"
    log_path = tmp_path / "logs" / "task_test.log"

    assert state.status == "completed"
    assert state.task_type == "research"
    assert "## 结论" in state.final_output
    assert "## 来源" in state.final_output
    assert state_path.exists()
    assert log_path.exists()
```

- [ ] **Step 3：确认目标测试失败**

运行：

```bash
.venv/bin/python -m pytest tests/test_loop.py tests/test_main.py -q
```

预期：

```text
FAIL
```

失败点如果只剩 `main.py` CLI 描述未更新，可以继续 Step 4。

- [ ] **Step 4：更新 CLI 描述**

修改 `main.py`：

```python
parser = argparse.ArgumentParser(description="Universal Task Agent V1.1 Research Search API")
```

- [ ] **Step 5：跑目标测试**

运行：

```bash
.venv/bin/python -m pytest tests/test_loop.py tests/test_main.py -q
```

预期：

```text
pass
```

- [ ] **Step 6：跑全量测试**

运行：

```bash
.venv/bin/python -m pytest -q
```

预期：

```text
all tests pass
```

- [ ] **Step 7：提交 CLI research**

运行：

```bash
git add tests/test_loop.py tests/test_main.py main.py
git commit -m "feat: run research tasks from cli"
```

---

## Task 6：核心 HistoryStore 迁移

**文件：**
- 新建：`core/history_store.py`
- 修改：`desktop/history_store.py`
- 修改：`tests/test_desktop_history_store.py`

- [ ] **Step 1：写核心 HistoryStore 导入测试**

在 `tests/test_desktop_history_store.py` 顶部 import 后增加：

```python
from core.history_store import HistoryStore as CoreHistoryStore
```

新增测试：

```python
def test_desktop_history_store_uses_core_history_store():
    from desktop.history_store import HistoryStore

    assert HistoryStore is CoreHistoryStore
```

- [ ] **Step 2：确认测试失败**

运行：

```bash
.venv/bin/python -m pytest tests/test_desktop_history_store.py -q
```

预期：

```text
ModuleNotFoundError: No module named 'core.history_store'
```

- [ ] **Step 3：迁移实现到 core**

新建 `core/history_store.py`，内容复制当前 `desktop/history_store.py` 的完整实现：

```python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class HistoryStore:
    def __init__(self, output_root: Path | str):
        self.output_root = Path(output_root)
        self.states_dir = self.output_root / "states"
        self.logs_dir = self.output_root / "logs"

    def list_runs(self) -> dict[str, Any]:
        runs: list[dict[str, Any]] = []
        for path in self._state_paths():
            state = self._read_state(path)
            if not isinstance(state, dict):
                continue
            task_id = self._task_id_from_path(path)
            runs.append(self._summary(task_id, path, state))

        runs.sort(key=lambda item: item["modified_at"], reverse=True)
        return {"ok": True, "runs": runs}

    def get_run(self, task_id: str) -> dict[str, Any]:
        path = self._state_path_for_task(task_id)
        if path is None or not path.exists():
            return {"ok": False, "error": "任务不存在"}

        state = self._read_state(path)
        if not isinstance(state, dict):
            return {"ok": False, "error": "state JSON 无效"}

        log_path = self._log_path_for_task(task_id)
        log = self._read_log(log_path) if log_path is not None else ""
        return {
            "ok": True,
            "task_id": task_id,
            "state": state,
            "log": log,
            "final_output": str(state.get("final_output") or ""),
        }

    def _state_paths(self) -> list[Path]:
        if not self.states_dir.exists():
            return []
        return sorted(
            path
            for path in self.states_dir.glob("*_state.json")
            if self._is_contained(path, self.states_dir)
        )

    def _state_path_for_task(self, task_id: str) -> Path | None:
        if not task_id or "/" in task_id or "\\" in task_id:
            return None
        candidate = self.states_dir / f"{task_id}_state.json"
        return candidate if self._is_contained(candidate, self.states_dir) else None

    def _log_path_for_task(self, task_id: str) -> Path | None:
        if not task_id or "/" in task_id or "\\" in task_id:
            return None
        candidate = self.logs_dir / f"{task_id}.log"
        if not candidate.exists():
            return candidate
        return candidate if self._is_contained(candidate, self.logs_dir) else None

    def _is_contained(self, path: Path, root: Path) -> bool:
        try:
            path.resolve().relative_to(root.resolve())
        except (OSError, RuntimeError, ValueError):
            return False
        return True

    def _task_id_from_path(self, path: Path) -> str:
        return path.name.removesuffix("_state.json")

    def _read_state(self, path: Path) -> dict[str, Any] | None:
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        return parsed if isinstance(parsed, dict) else None

    def _read_log(self, path: Path) -> str:
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ""

    def _summary(self, task_id: str, path: Path, state: dict[str, Any]) -> dict[str, Any]:
        final_output = str(state.get("final_output") or "")
        intent = str(state.get("intent") or "")
        preview = self._preview(final_output or intent)
        return {
            "task_id": task_id,
            "status": str(state.get("status") or "unknown"),
            "task_type": str(state.get("task_type") or "unknown"),
            "intent": intent,
            "updated_at": str(state.get("updated_at") or ""),
            "modified_at": self._modified_at(path),
            "preview": preview,
        }

    def _preview(self, text: str, limit: int = 120) -> str:
        normalized = " ".join(str(text).split())
        if len(normalized) <= limit:
            return normalized
        return normalized[:limit] + "..."

    def _modified_at(self, path: Path) -> str:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
```

- [ ] **Step 4：改 desktop/history_store.py 为兼容导入**

把 `desktop/history_store.py` 替换为：

```python
from core.history_store import HistoryStore

__all__ = ["HistoryStore"]
```

- [ ] **Step 5：跑 history tests**

运行：

```bash
.venv/bin/python -m pytest tests/test_desktop_history_store.py -q
```

预期：

```text
pass
```

- [ ] **Step 6：提交 HistoryStore 迁移**

运行：

```bash
git add core/history_store.py desktop/history_store.py tests/test_desktop_history_store.py
git commit -m "refactor: share history store with api"
```

---

## Task 7：FastAPI 同步接口

**文件：**
- 新建：`api/__init__.py`
- 新建：`api/server.py`
- 新建：`tests/test_api_server.py`

- [ ] **Step 1：写 API 失败测试**

新建 `tests/test_api_server.py`：

```python
from fastapi.testclient import TestClient

from api.server import app


def test_health_returns_ok():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_run_task_endpoint_runs_research_task(tmp_path, monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDER", "fixture")
    client = TestClient(app)

    response = client.post(
        "/v1/tasks/run",
        json={
            "task": "调研 UTA Agent 框架下一步路线",
            "task_id": "task_api_demo",
            "output_root": str(tmp_path),
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["task_id"] == "task_api_demo"
    assert payload["status"] == "completed"
    assert payload["task_type"] == "research"
    assert "## 来源" in payload["final_output"]
    assert (tmp_path / "states" / "task_api_demo_state.json").exists()


def test_list_and_get_runs_endpoints(tmp_path, monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDER", "fixture")
    client = TestClient(app)
    client.post(
        "/v1/tasks/run",
        json={
            "task": "调研 UTA Agent 框架下一步路线",
            "task_id": "task_api_demo",
            "output_root": str(tmp_path),
        },
    )

    listed = client.get("/v1/runs", params={"output_root": str(tmp_path)}).json()
    detail = client.get("/v1/runs/task_api_demo", params={"output_root": str(tmp_path)}).json()

    assert listed["ok"] is True
    assert listed["runs"][0]["task_id"] == "task_api_demo"
    assert detail["ok"] is True
    assert detail["task_id"] == "task_api_demo"
    assert "## 来源" in detail["final_output"]
```

- [ ] **Step 2：确认测试失败**

运行：

```bash
.venv/bin/python -m pytest tests/test_api_server.py -q
```

预期：

```text
ModuleNotFoundError: No module named 'api'
```

- [ ] **Step 3：实现 api 包**

新建 `api/__init__.py`：

```python
"""FastAPI entrypoints for UTA."""
```

新建 `api/server.py`：

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query
from pydantic import BaseModel

from core.history_store import HistoryStore
from main import run_task


app = FastAPI(title="Universal Task Agent API", version="1.1")


class RunTaskRequest(BaseModel):
    task: str
    task_id: str | None = None
    output_root: str = "outputs"


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/v1/tasks/run")
def run_task_endpoint(request: RunTaskRequest) -> dict[str, Any]:
    state = run_task(
        request.task,
        output_root=request.output_root,
        task_id=request.task_id,
    )
    return {
        "ok": state.status == "completed",
        "task_id": state.task_id,
        "status": state.status,
        "task_type": state.task_type,
        "intent": state.intent,
        "final_output": state.final_output,
        "state": state.to_dict(),
    }


@app.get("/v1/runs")
def list_runs(output_root: str = Query("outputs")) -> dict[str, Any]:
    return HistoryStore(Path(output_root)).list_runs()


@app.get("/v1/runs/{task_id}")
def get_run(task_id: str, output_root: str = Query("outputs")) -> dict[str, Any]:
    return HistoryStore(Path(output_root)).get_run(task_id)
```

- [ ] **Step 4：跑 API 测试**

运行：

```bash
.venv/bin/python -m pytest tests/test_api_server.py -q
```

预期：

```text
3 passed
```

- [ ] **Step 5：提交 FastAPI**

运行：

```bash
git add api tests/test_api_server.py
git commit -m "feat: add synchronous fastapi endpoints"
```

---

## Task 8：文档、demo、全量验收和 tag

**文件：**
- 修改：`README.md`
- 修改：`CHANGELOG.md`

- [ ] **Step 1：更新 README**

在 `README.md` 的 V1.0 demo 后新增：

```markdown
## V1.1 调研任务与搜索

V1.1 新增 `research` 调研任务类型和可插拔 Search Provider。默认 `SEARCH_PROVIDER=fixture`，用于离线测试和本地 demo；真实搜索可配置 HTTP Provider。

```bash
SEARCH_PROVIDER=fixture .venv/bin/python main.py --task "调研 UTA Agent 框架下一步路线"
```

真实 HTTP Provider 配置：

```bash
export SEARCH_PROVIDER=http
export SEARCH_API_URL="https://example.com/search"
export SEARCH_API_KEY="your-search-key"
export SEARCH_TIMEOUT_SECONDS=10
```

FastAPI 启动：

```bash
.venv/bin/python -m uvicorn api.server:app --host 127.0.0.1 --port 8000
```

API demo：

```bash
curl -s http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/v1/tasks/run \
  -H "Content-Type: application/json" \
  -d '{"task":"调研 UTA Agent 框架下一步路线","task_id":"task_api_demo","output_root":"/private/tmp/uta-api-demo"}'
```
```

在“当前状态”列表新增：

```markdown
- `v1.1-research-search-api`: 新增 research 调研任务、可插拔 Search Provider、search_tool 和同步 FastAPI 接口。
```

- [ ] **Step 2：更新 CHANGELOG**

在 `CHANGELOG.md` 顶部新增：

```markdown
## v1.1-research-search-api

- 新增 research 调研任务类型。
- 新增可插拔 Search Provider 和 search_tool。
- 新增带来源的调研报告生成与校验。
- 新增同步 FastAPI 接口。
- 使用 fixture search 支持离线测试和 demo。
```

- [ ] **Step 3：跑全量测试**

运行：

```bash
.venv/bin/python -m pytest -q
```

预期：

```text
all tests pass
```

- [ ] **Step 4：跑 CLI demo**

运行：

```bash
SEARCH_PROVIDER=fixture .venv/bin/python main.py \
  --output-root /private/tmp/uta-v1-1-cli-demo \
  --task "调研 UTA Agent 框架下一步路线"
```

预期：

```text
任务已完成：
```

输出包含：

```text
## 结论
## 来源
```

并确认：

```bash
test -f /private/tmp/uta-v1-1-cli-demo/states/*_state.json
test -f /private/tmp/uta-v1-1-cli-demo/logs/*.log
```

- [ ] **Step 5：跑 API demo**

启动服务：

```bash
SEARCH_PROVIDER=fixture .venv/bin/python -m uvicorn api.server:app --host 127.0.0.1 --port 8000
```

另一个 shell 验证：

```bash
curl -s http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/v1/tasks/run \
  -H "Content-Type: application/json" \
  -d '{"task":"调研 UTA Agent 框架下一步路线","task_id":"task_api_demo","output_root":"/private/tmp/uta-api-demo"}'
```

预期：

```text
health 返回 {"ok":true}
run 返回 "ok":true 和 "task_type":"research"
```

验证文件：

```bash
test -f /private/tmp/uta-api-demo/states/task_api_demo_state.json
```

停止 uvicorn 后继续。

- [ ] **Step 6：提交文档**

运行：

```bash
git add README.md CHANGELOG.md
git commit -m "docs: document v1.1 research api"
```

- [ ] **Step 7：打 tag**

运行：

```bash
git tag v1.1-research-search-api
git tag --list v1.1-research-search-api
```

预期：

```text
v1.1-research-search-api
```

- [ ] **Step 8：最终状态检查**

运行：

```bash
git status -sb
git log --oneline -8
git tag --list "v1.1*"
```

预期：

```text
工作树干净
v1.1-research-search-api 存在
```


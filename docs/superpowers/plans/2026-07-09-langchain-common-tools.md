# LangChain Common Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 UTA 接入一批安全常用的 LangChain 风格工具，并继续复用现有 agent 主循环、状态、日志和桌面展示。

**Architecture:** 新增 `tools/langchain_common_tools.py`，里面放一组只读或纯计算的 LangChain-like 工具，每个工具暴露 `name`、`description`、`invoke(tool_input)`。注册表继续通过 `LangChainToolAdapter` 包装它们，parser/planner/router 只把明确匹配的任务路由到这些工具。

**Tech Stack:** Python 3.10+、现有 `LangChainToolAdapter`、现有 `SearchTool`、`httpx`、pytest。

## Global Constraints

- 不加入 Shell、Python REPL、文件写入/删除/移动、浏览器点击/填表、本地应用控制工具。
- HTTP 工具只允许 `http` 和 `https`，拒绝 localhost、内网地址、链路本地地址和无主机 URL。
- 计算器不使用 `eval`。
- LangChain 依赖保持可选，第一批工具不要求安装真实 `langchain` 包。
- 工具失败必须给出清晰错误，不允许伪完成。

---

### Task 1: Safe Common Tool Implementations

**Files:**
- Create: `tools/langchain_common_tools.py`
- Test: `tests/test_langchain_common_tools.py`

**Interfaces:**
- Produces: `CalculatorLangChainTool.invoke(tool_input) -> dict`
- Produces: `DateTimeLangChainTool.invoke(tool_input) -> dict`
- Produces: `JsonLangChainTool.invoke(tool_input) -> dict`
- Produces: `HttpGetLangChainTool.invoke(tool_input) -> dict`
- Produces: `SearchLangChainTool.invoke(tool_input) -> dict`
- Produces: `WeatherLangChainTool.invoke(tool_input) -> dict`
- Produces: `build_common_langchain_tools(search_tool=None) -> tuple`

- [ ] **Step 1: Write failing tests**

Write tests for calculator, datetime, JSON, safe HTTP validation, search wrapper, weather wrapper and common builder names.

- [ ] **Step 2: Run tests and verify failure**

Run: `.venv/bin/python -m pytest tests/test_langchain_common_tools.py -q`
Expected: fail because `tools.langchain_common_tools` does not exist.

- [ ] **Step 3: Implement minimal safe tools**

Implement pure Python tools and wrapper tools. Do not import real `langchain`.

- [ ] **Step 4: Verify tests pass**

Run: `.venv/bin/python -m pytest tests/test_langchain_common_tools.py -q`
Expected: pass.

### Task 2: Registry Integration

**Files:**
- Modify: `tools/registry.py`
- Test: `tests/test_langchain_adapter.py`

**Interfaces:**
- Consumes: `build_common_langchain_tools(search_tool=search_tool)`
- Produces default registry entries:
  - `langchain_calculator_tool`
  - `langchain_datetime_tool`
  - `langchain_http_get_tool`
  - `langchain_search_tool`
  - `langchain_weather_tool`
  - `langchain_json_tool`

- [ ] **Step 1: Write failing registry test**

Assert default registry includes all safe common LangChain tools and `enable_langchain_tools=False` excludes them.

- [ ] **Step 2: Run registry tests and verify failure**

Run: `.venv/bin/python -m pytest tests/test_langchain_adapter.py -q`
Expected: fail because the registry only includes echo.

- [ ] **Step 3: Register common tools**

Use the existing `LangChainToolAdapter` for each common tool.

- [ ] **Step 4: Verify registry tests pass**

Run: `.venv/bin/python -m pytest tests/test_langchain_adapter.py -q`
Expected: pass.

### Task 3: Parser, Planner and Router Wiring

**Files:**
- Modify: `core/task_parser.py`
- Modify: `core/planner.py`
- Modify: `core/router.py`
- Test: `tests/test_task_parser.py`
- Test: `tests/test_planner.py`
- Test: `tests/test_router.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Produces: `task_type="langchain_tool"` for safe tool requests.
- Produces: planner step `调用 LangChain 工具处理请求`.
- Router maps safe requests to matching LangChain tool names.

- [ ] **Step 1: Write failing parser/router/end-to-end tests**

Cover calculator, datetime, JSON, HTTP GET, search and weather routing.

- [ ] **Step 2: Run focused tests and verify failure**

Run relevant parser/router/main tests and confirm missing behavior.

- [ ] **Step 3: Implement route selection**

Add narrow safe matching. Preserve existing research/search/weather behavior unless the request explicitly asks for LangChain tool or belongs to a new pure-tool class.

- [ ] **Step 4: Verify focused tests pass**

Run focused parser/router/main tests.

### Task 4: Full Verification

**Files:**
- Test suite only.

- [ ] **Step 1: Run focused tests**

Run:
- `.venv/bin/python -m pytest tests/test_langchain_common_tools.py tests/test_langchain_adapter.py tests/test_task_parser.py tests/test_planner.py tests/test_router.py tests/test_main.py::test_run_task_executes_safe_langchain_calculator_tool -q`

- [ ] **Step 2: Run full tests**

Run:
- `.venv/bin/python -m pytest -q`

- [ ] **Step 3: Report status**

Report exact command results and mention that desktop packaging is still a separate step unless explicitly requested.

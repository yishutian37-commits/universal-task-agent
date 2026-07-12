# LangChain Tools Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 UTA 可以接入 LangChain Tools，同时保留现有 planner、router、executor、verifier、memory 和桌面状态展示。

**Architecture:** 新增一个轻量适配层，把 LangChain tool 包装成 UTA 的 `BaseTool.run(action_name, params) -> dict`。默认运行不强依赖 LangChain；只有安装并显式开启时，才把示例 LangChain 工具注册进 `build_tool_registry()`。

**Tech Stack:** Python 3.10+、现有 UTA `BaseTool`、可选 `langchain-core`/`langchain`、pytest。

## Global Constraints

- 不重写现有 agent 主循环。
- 不引入本地电脑控制、鼠标键盘控制、打开应用等能力。
- LangChain 依赖必须是可选依赖，未安装时 UTA 仍能运行。
- 所有新行为先写测试，再实现。
- 工具失败必须返回清晰错误，不能伪完成。

---

### Task 1: LangChain Tool Adapter

**Files:**
- Create: `tools/langchain_adapter.py`
- Test: `tests/test_langchain_adapter.py`

**Interfaces:**
- Consumes: `tools.base_tool.BaseTool`
- Produces: `LangChainToolAdapter(langchain_tool, name=None, description=None)` with `run(action_name, params) -> dict[str, Any]`

- [ ] **Step 1: Write failing tests**

Create tests proving:
- adapter invokes a LangChain-like object through `.invoke()`
- input is derived from `tool_input`, `query`, `user_input`, or `goal`
- dict outputs are preserved under `output`
- exceptions become `RuntimeError` with a readable message

- [ ] **Step 2: Run tests and verify failure**

Run: `.venv/bin/python -m pytest tests/test_langchain_adapter.py -q`
Expected: fail because `tools.langchain_adapter` does not exist.

- [ ] **Step 3: Implement minimal adapter**

Create `tools/langchain_adapter.py` with a focused wrapper and no hard import of LangChain.

- [ ] **Step 4: Verify adapter tests pass**

Run: `.venv/bin/python -m pytest tests/test_langchain_adapter.py -q`
Expected: pass.

### Task 2: Optional Registry Integration

**Files:**
- Modify: `tools/registry.py`
- Test: `tests/test_langchain_adapter.py`

**Interfaces:**
- Produces: `build_langchain_tool_registry(enabled: bool | None = None) -> dict[str, BaseTool]`
- Produces: optional tool name `langchain_echo_tool`

- [ ] **Step 1: Write failing registry tests**

Tests should prove:
- default registry does not include LangChain tools
- `build_tool_registry(enable_langchain_tools=True)` includes `langchain_echo_tool`
- missing LangChain packages do not break default registry

- [ ] **Step 2: Run tests and verify failure**

Run: `.venv/bin/python -m pytest tests/test_langchain_adapter.py -q`
Expected: fail because registry support is missing.

- [ ] **Step 3: Implement optional registration**

Add `enable_langchain_tools` parameter to `build_tool_registry()`. Register a built-in echo tool through the adapter only when enabled.

- [ ] **Step 4: Verify registry tests pass**

Run: `.venv/bin/python -m pytest tests/test_langchain_adapter.py -q`
Expected: pass.

### Task 3: Router Wiring for Safe Demo Tool

**Files:**
- Modify: `core/router.py`
- Test: `tests/test_router.py`

**Interfaces:**
- Consumes: tool name `langchain_echo_tool`

- [ ] **Step 1: Write failing router test**

Add a test proving a clear phrase such as `用 LangChain 工具回显 hello` routes to `langchain_echo_tool`.

- [ ] **Step 2: Run router test and verify failure**

Run: `.venv/bin/python -m pytest tests/test_router.py::test_router_can_select_langchain_echo_tool -q`
Expected: fail because no routing rule exists.

- [ ] **Step 3: Add minimal routing rule**

Add a narrow rule for `LangChain 工具` / `langchain 工具` / `回显`.

- [ ] **Step 4: Verify router test passes**

Run: `.venv/bin/python -m pytest tests/test_router.py::test_router_can_select_langchain_echo_tool -q`
Expected: pass.

### Task 4: Full Verification

**Files:**
- Test suite only.

- [ ] **Step 1: Run focused tests**

Run:
- `.venv/bin/python -m pytest tests/test_langchain_adapter.py tests/test_router.py tests/test_executor.py -q`

- [ ] **Step 2: Run full tests**

Run:
- `.venv/bin/python -m pytest -q`

- [ ] **Step 3: Report status**

Report exact command results. If tests pass, recommend rebuilding the desktop app as the next separate step.

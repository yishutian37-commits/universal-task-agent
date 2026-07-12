# Dangerous Tools Manual Authorization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 UTA 增加高风险工具的手动授权闭环，第一阶段支持 Shell 和文件写入，未授权时绝不执行。

**Architecture:** 新增授权管理器，工具执行时先生成 `authorization_required` 请求并阻塞等待桌面端确认。`TaskRunner` 持有授权管理器，注入工具注册表；前端收到授权事件后展示确认面板，调用 `authorize_operation()` 或 `reject_authorization()`，后台再继续或失败。

**Tech Stack:** Python 3.10+、现有 UTA tool registry、threading.Event、pywebview JS bridge、pytest。

## Global Constraints

- 第一阶段只实现 Shell 和文件写入；Python REPL 与文件删除放到下一阶段。
- 高风险工具必须同时满足全局开关开启和单次授权通过。
- 未授权、拒绝或超时都不能执行实际操作。
- Shell 限制工作目录在允许目录内，禁止明显危险命令，限制超时和输出长度。
- 文件写入限制目标路径在允许目录内，支持 create/overwrite/append。
- 所有授权请求和授权结果进入任务事件日志。

---

### Task 1: Authorization Manager

**Files:**
- Create: `tools/authorization.py`
- Test: `tests/test_authorization.py`

**Interfaces:**
- Produces: `AuthorizationManager.request(operation: dict, timeout: float | None = None) -> AuthorizationDecision`
- Produces: `AuthorizationManager.approve(request_id: str, approved_by: str = "user") -> dict`
- Produces: `AuthorizationManager.reject(request_id: str, reason: str = "") -> dict`

- [ ] **Step 1: Write failing tests**
- [ ] **Step 2: Run tests and verify failure**
- [ ] **Step 3: Implement manager**
- [ ] **Step 4: Verify tests pass**

### Task 2: Dangerous LangChain Tools

**Files:**
- Modify: `tools/langchain_common_tools.py`
- Test: `tests/test_langchain_dangerous_tools.py`

**Interfaces:**
- Produces: `ShellLangChainTool.invoke(tool_input) -> dict`
- Produces: `FileWriteLangChainTool.invoke(tool_input) -> dict`

- [ ] **Step 1: Write failing tests**
- [ ] **Step 2: Run tests and verify failure**
- [ ] **Step 3: Implement Shell and file write tools**
- [ ] **Step 4: Verify tests pass**

### Task 3: Registry, Parser, Planner, Router

**Files:**
- Modify: `tools/registry.py`
- Modify: `core/task_parser.py`
- Modify: `core/router.py`
- Test: `tests/test_langchain_adapter.py`
- Test: `tests/test_task_parser.py`
- Test: `tests/test_router.py`

**Interfaces:**
- Add registry entries `langchain_shell_tool` and `langchain_file_write_tool`.
- Route explicit shell/file-write requests to those tools.

- [ ] **Step 1: Write failing tests**
- [ ] **Step 2: Run focused tests and verify failure**
- [ ] **Step 3: Implement routing and registry**
- [ ] **Step 4: Verify focused tests pass**

### Task 4: Desktop Authorization Bridge

**Files:**
- Modify: `desktop/runner.py`
- Modify: `desktop/api.py`
- Modify: `desktop/settings_store.py`
- Modify: `desktop/frontend/index.html`
- Modify: `desktop/frontend/app.js`
- Modify: `desktop/frontend/style.css`
- Test: `tests/test_runner.py`
- Test: `tests/test_desktop_api.py`
- Test: `tests/test_desktop_settings_store.py`

**Interfaces:**
- Produces: `DesktopAPI.authorize_operation(request_id: str) -> dict`
- Produces: `DesktopAPI.reject_authorization(request_id: str, reason: str = "") -> dict`
- Emits frontend event type `authorization_required`.

- [ ] **Step 1: Write backend failing tests**
- [ ] **Step 2: Implement backend bridge**
- [ ] **Step 3: Implement frontend confirmation panel**
- [ ] **Step 4: Verify focused tests pass**

### Task 5: Full Verification

**Files:**
- Test suite only.

- [ ] **Step 1: Run focused tests**
- [ ] **Step 2: Run full tests**
- [ ] **Step 3: Report exact results**

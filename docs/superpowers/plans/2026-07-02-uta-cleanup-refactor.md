# UTA 清理与重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成项目工程化（pyproject.toml）、仓库清理（重复文档）、工具注册表统一、LLMClient 迁移到 httpx，以及 desktop/api.py 与 core/loop.py 的拆分重构。

**Architecture:** 通过 `pyproject.toml` 统一依赖与脚本入口；将分散的工具注册逻辑合并到 `tools/registry.py`；用 `httpx` 替换手写 urllib/curl 传输层；将 `desktop/api.py` 按领域拆分为多个 Handler，将 `core/loop.py` 的循环、重试、replan、进度事件拆分为独立类。

**Tech Stack:** Python 3.12, pytest, FastAPI, uvicorn, httpx, pywebview, pyinstaller

## Global Constraints

- 保持现有 441 个测试全部通过（除新增测试外）。
- 不修改已发布的外部接口（`main.run_task` 签名、API endpoint 路径、桌面 JS API 方法名）。
- 所有新增/修改的 Python 代码保持 type hints。
- 中文业务提示文本可保留，但路由/校验的硬编码规则应可配置化。
- 每次任务完成后运行 `pytest tests/ -q`。

---

## File Structure

| 文件 | 责任 |
|---|---|
| `pyproject.toml` | 项目元数据、依赖、脚本入口、pytest 配置 |
| `requirements.txt` | 保留为 `-e .` 或删除（待决定） |
| `requirements-desktop.txt` | 保留为 `[desktop]` optional 的替代 |
| `tools/registry.py` | 唯一工具注册表构造器，支持参数化根目录 |
| `desktop/runner.py` | 调用 `tools.registry.build_tool_registry` 而非自建 |
| `llm/llm_client.py` | 用 httpx 实现默认 transport，保留 curl fallback 但可选 |
| `desktop/api_handlers/` | 拆分出的 Handler 包 |
| `desktop/api.py` | 保留为 facade，组合各 Handler |
| `core/loop.py` | 保留为 facade，组合新的子组件 |
| `core/loop_components.py` | 新增：StepExecutor、RetryController、ReplanController、ProgressEmitter |

---

## Task 1: 增加 pyproject.toml 并统一项目配置

**Files:**
- Create: `pyproject.toml`
- Delete/Move: `pytest.ini`（配置移入 pyproject.toml）
- Modify: `requirements.txt`, `requirements-desktop.txt`
- Test: `tests/test_config.py`, 运行 `pytest tests/ -q`

**Interfaces:**
- Consumes: 当前 `requirements.txt` 中的 8 个包
- Produces: 可 `pip install -e .` 安装，保留 `pytest -m "not integration"` 行为

- [ ] **Step 1: 编写 pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "uta"
version = "1.2.0"
description = "Universal Task Agent - 本地学习型 Agent 框架"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
authors = [
    {name = "UTA Team"},
]
keywords = ["agent", "llm", "rag", "desktop"]
classifiers = [
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]
dependencies = [
    "pytest>=8.0.0",
    "pandas>=2.0.0",
    "openpyxl>=3.1.0",
    "numpy>=2.0.0",
    "certifi>=2024.0.0",
    "fastapi>=0.115.0",
    "uvicorn>=0.30.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
desktop = [
    "pywebview>=5.0.0",
    "pyinstaller>=6.0.0",
]
dev = [
    "ruff>=0.5.0",
    "pytest-cov>=5.0.0",
]

[project.scripts]
uta = "main:main"
uta-api = "api.server:main"
uta-desktop = "desktop.app:main"

[tool.setuptools.packages.find]
include = ["api*", "core*", "desktop*", "llm*", "memory_providers*", "rag*", "search_providers*", "skills*", "tools*", "weather_providers*"]

[tool.pytest.ini_options]
markers = [
    "integration: 需要真实模型或网络的集成测试（默认跳过，手动 -m integration 运行）",
]
addopts = "-m 'not integration'"

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "W"]

[tool.ruff.lint.pydocstyle]
convention = "google"
```

- [ ] **Step 2: 删除 pytest.ini**

```bash
rm pytest.ini
```

- [ ] **Step 3: 更新 requirements.txt 为可编辑安装**

```text
-e .
```

- [ ] **Step 4: 更新 requirements-desktop.txt**

```text
-r requirements.txt
-e .[desktop]
```

- [ ] **Step 5: 运行测试确认无回归**

Run: `pytest tests/ -q`
Expected: `441 passed, 5 deselected`

- [ ] **Step 6: 验证可编辑安装**

Run: `.venv/bin/python -m pip install -e .`
Expected: 安装成功，无错误。

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml requirements.txt requirements-desktop.txt pytest.ini
git commit -m "chore: add pyproject.toml and unify project configuration"
```

---

## Task 2: 清理根目录重复设计文档

**Files:**
- Delete: `mqmhzojl-2026-06-20-desktop-app-design.md`, `mqmi5wkc-2026-06-20-desktop-app-design.md`, `mqmid6ez-2026-06-20-desktop-app-design.md`
- Keep: 如需归档，保留一份到 `docs/superpowers/designs/desktop-app-design.md`

**Interfaces:**
- 无代码接口变更。

- [ ] **Step 1: 检查三份文件是否确实相同**

Run:
```bash
diff -q mqmhzojl-2026-06-20-desktop-app-design.md mqmi5wkc-2026-06-20-desktop-app-design.md
diff -q mqmi5wkc-2026-06-20-desktop-app-design.md mqmid6ez-2026-06-20-desktop-app-design.md
```
Expected: 无输出（表示相同）。

- [ ] **Step 2: 归档一份到 docs**

```bash
mkdir -p docs/superpowers/designs
cp mqmhzojl-2026-06-20-desktop-app-design.md docs/superpowers/designs/desktop-app-design.md
```

- [ ] **Step 3: 删除根目录三份重复文件**

```bash
rm mqmhzojl-2026-06-20-desktop-app-design.md mqmi5wkc-2026-06-20-desktop-app-design.md mqmid6ez-2026-06-20-desktop-app-design.md
```

- [ ] **Step 4: 确认 git status**

Run: `git status --short`
Expected: 显示 `D` 删除三文件，`A` 新增归档文件。

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/designs/desktop-app-design.md mqmhzojl-2026-06-20-desktop-app-design.md mqmi5wkc-2026-06-20-desktop-app-design.md mqmid6ez-2026-06-20-desktop-app-design.md
git commit -m "chore: deduplicate and archive desktop design docs"
```

---

## Task 3: 统一工具注册表

**Files:**
- Modify: `tools/registry.py`
- Modify: `desktop/runner.py`
- Test: `tests/test_desktop_api.py`（现有测试覆盖 `runner_module.build_tool_registry`）

**Interfaces:**
- `tools.registry.build_tool_registry(project_root: Path | None = None) -> dict[str, BaseTool]`
- `desktop/runner.py` 不再定义 `build_tool_registry`，改为 `from tools.registry import build_tool_registry`

- [ ] **Step 1: 修改 tools/registry.py 支持参数化根目录**

当前 `tools/registry.py` 全部代码：

```python
from tools.code_tool import CodeTool
from tools.file_tool import FileTool
from tools.geo_tool import GeoTool
from tools.history_tool import HistoryTool
from tools.mock_tool import MockTool
from tools.report_tool import ReportTool
from tools.search_tool import SearchTool
from tools.table_tool import TableTool
from tools.text_tool import TextTool


def build_tool_registry():
    return {
        "mock_tool": MockTool(),
        "code_tool": CodeTool(),
        "file_tool": FileTool(),
        "geo_tool": GeoTool(),
        "history_tool": HistoryTool(),
        "text_tool": TextTool(),
        "table_tool": TableTool(),
        "report_tool": ReportTool(),
        "search_tool": SearchTool(),
    }


TOOL_REGISTRY = build_tool_registry()
```

替换为：

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from desktop.paths import resource_path, uta_home
from tools.base_tool import BaseTool
from tools.code_tool import CodeTool
from tools.file_tool import FileTool
from tools.geo_tool import GeoTool
from tools.history_tool import HistoryTool
from tools.mock_tool import MockTool
from tools.report_tool import ReportTool
from tools.search_tool import SearchTool
from tools.table_tool import TableTool
from tools.text_tool import TextTool


def build_tool_registry(
    project_root: Path | str | None = None,
    skills_root: Path | str | None = None,
    output_root: Path | str | None = None,
    memory_root: Path | str | None = None,
) -> dict[str, BaseTool]:
    """构造工具注册表。

    参数用于桌面端等需要指定资源根目录的场景；CLI/默认场景不传参即可。
    """
    if project_root is not None:
        project_root = Path(project_root)
    else:
        project_root = Path.cwd()

    if skills_root is not None:
        skills_root = Path(skills_root)
    else:
        skills_root = project_root / "skills"

    if output_root is None:
        output_root = uta_home() / "outputs"

    if memory_root is None:
        memory_root = uta_home() / "memory"

    geo_vendor_root = skills_root / "vendor" / "geo-agent-marketing-optimized"

    return {
        "mock_tool": MockTool(),
        "code_tool": CodeTool(project_root=project_root),
        "file_tool": FileTool(),
        "geo_tool": GeoTool(geo_vendor_root),
        "history_tool": HistoryTool(output_root=output_root, memory_root=memory_root),
        "text_tool": TextTool(),
        "table_tool": TableTool(),
        "report_tool": ReportTool(),
        "search_tool": SearchTool(),
    }


TOOL_REGISTRY = build_tool_registry()
```

- [ ] **Step 2: 修改 desktop/runner.py 使用统一注册表**

删除 `desktop/runner.py` 中第 18-39 行的 `build_tool_registry` 定义及对应 imports。

在文件顶部增加：

```python
from tools.registry import build_tool_registry
```

修改 `_run` 中的调用：

```python
state = run_task_func(
    user_input,
    output_root=self.output_root,
    task_id=task_id,
    tool_registry=build_tool_registry(
        project_root=resource_path("."),
        skills_root=resource_path("skills"),
        output_root=self.output_root,
        memory_root=self.memory_root,
    ),
    memory_provider=JsonMemoryProvider(self.memory_root),
    skill_loader=SkillLoader(resource_path("skills")),
    on_progress=self._emit_progress,
)
```

- [ ] **Step 3: 运行桌面相关测试**

Run: `pytest tests/test_desktop_api.py tests/test_api_server.py -q`
Expected: 全部通过。

- [ ] **Step 4: Commit**

```bash
git add tools/registry.py desktop/runner.py
git commit -m "refactor: unify tool registry in tools.registry"
```

---

## Task 4: 迁移 LLMClient 到 httpx

**Files:**
- Modify: `llm/llm_client.py`
- Modify: `requirements.txt`（已通过 pyproject.toml 引入 httpx）
- Test: `tests/test_llm_client.py`

**Interfaces:**
- `LLMClient.__init__` 签名不变，新增 `use_curl_fallback: bool = False`
- `LLMClient.chat` / `LLMClient.chat_json` 行为不变
- 默认 transport 改为同步 `httpx.Client`

- [ ] **Step 1: 阅读当前 test_llm_client.py**

Run: `cat tests/test_llm_client.py`
确认注入 `transport` 和 `fallback_transport` callable 的接口仍被测试依赖。

- [ ] **Step 2: 重写 LLMClient 默认 transport**

将 `llm/llm_client.py` 中的 `_default_transport` 替换为 httpx 实现：

```python
def _default_transport(
    self,
    endpoint: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    import httpx

    verify: str | bool = certifi.where() if self.ssl_verify else False
    try:
        with httpx.Client(timeout=timeout, verify=verify) as client:
            response = client.post(endpoint, headers=headers, json=payload)
    except httpx.HTTPStatusError as exc:
        raise LLMClientError(f"LLM HTTP error {exc.response.status_code}: {exc.response.text}") from exc
    except httpx.RequestError as exc:
        raise LLMClientError(f"LLM network error: {exc}") from exc

    try:
        parsed = response.json()
    except ValueError as exc:
        raise LLMClientError(f"Invalid LLM HTTP JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise LLMClientError("Invalid LLM HTTP JSON: expected object")
    return parsed
```

并在 `__init__` 中增加 `use_curl_fallback: bool = False` 参数，默认不启用 curl fallback。

- [ ] **Step 3: 保留 transport 注入能力**

确保测试仍可通过 `transport=` 参数注入 fake transport。

- [ ] **Step 4: 运行 LLMClient 测试**

Run: `pytest tests/test_llm_client.py -q`
Expected: 全部通过。

- [ ] **Step 5: Commit**

```bash
git add llm/llm_client.py
git commit -m "refactor: migrate LLMClient default transport to httpx"
```

---

## Task 5: 拆分 desktop/api.py 为 Handlers

**Files:**
- Create: `desktop/api_handlers/__init__.py`
- Create: `desktop/api_handlers/base.py`
- Create: `desktop/api_handlers/task_handler.py`
- Create: `desktop/api_handlers/conversation_handler.py`
- Create: `desktop/api_handlers/memory_handler.py`
- Create: `desktop/api_handlers/rag_handler.py`
- Create: `desktop/api_handlers/settings_handler.py`
- Create: `desktop/api_handlers/skill_handler.py`
- Modify: `desktop/api.py`
- Test: `tests/test_desktop_api.py`

**Interfaces:**
- `DesktopAPI` 类保留，所有公开方法名不变，仅内部委托给 Handler。
- 每个 Handler 接收构造函数注入的 store/client。

- [ ] **Step 1: 创建 desktop/api_handlers/__init__.py**

```python
from desktop.api_handlers.conversation_handler import ConversationHandler
from desktop.api_handlers.memory_handler import MemoryHandler
from desktop.api_handlers.rag_handler import RAGHandler
from desktop.api_handlers.settings_handler import SettingsHandler
from desktop.api_handlers.skill_handler import SkillHandler
from desktop.api_handlers.task_handler import TaskHandler

__all__ = [
    "ConversationHandler",
    "MemoryHandler",
    "RAGHandler",
    "SettingsHandler",
    "SkillHandler",
    "TaskHandler",
]
```

- [ ] **Step 2: 创建 desktop/api_handlers/base.py**

```python
from __future__ import annotations

from typing import Any


class BaseHandler:
    """桌面 API Handler 基类，统一异常包装。"""

    def _ok(self, **data: Any) -> dict[str, Any]:
        return {"ok": True, **data}

    def _error(self, message: str) -> dict[str, Any]:
        return {"ok": False, "error": message}

    def _try(self, fn, *args, **kwargs) -> dict[str, Any]:
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            return self._error(str(exc))
```

- [ ] **Step 3: 拆分 TaskHandler**

从 `desktop/api.py` 中提取 `run_task`、`list_runs`、`get_run`、`get_result`、`cancel_task` 到 `desktop/api_handlers/task_handler.py`。

方法签名示例：

```python
class TaskHandler(BaseHandler):
    def __init__(self, runner, history_store, settings_store):
        self.runner = runner
        self.history_store = history_store
        self.settings_store = settings_store

    def run_task(self, user_input: str) -> dict[str, Any]:
        ...

    def list_runs(self) -> dict[str, Any]:
        ...

    def get_run(self, task_id: str) -> dict[str, Any]:
        ...

    def get_result(self, task_id: str) -> dict[str, Any]:
        ...

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        ...
```

- [ ] **Step 4: 拆分 SettingsHandler**

提取 `get_settings`、`save_settings`、`load_example`。

- [ ] **Step 5: 拆分 ConversationHandler**

提取 `list_conversations`、`new_conversation`、`get_conversation`、`compress_conversation`、`run_chat_message`、`sync_chat_result` 及相关私有方法 `_ensure_conversation_id`、`_run_general_chat`、`_maybe_auto_compress`、`_record_compression_error`。

- [ ] **Step 6: 拆分 MemoryHandler**

提取 `get_memory_overview`。

- [ ] **Step 7: 拆分 SkillHandler**

提取 `get_skill_overview`。

- [ ] **Step 8: 拆分 RAGHandler**

提取 `rag_stats`、`rag_list_docs`、`rag_ingest`、`rag_query`、`rag_ask`、`rag_delete`。

- [ ] **Step 9: 重写 desktop/api.py 为 facade**

`DesktopAPI` 类保留所有公开方法，内部调用各 Handler。

示例：

```python
from desktop.api_handlers import (
    ConversationHandler,
    MemoryHandler,
    RAGHandler,
    SettingsHandler,
    SkillHandler,
    TaskHandler,
)


class DesktopAPI:
    def __init__(self, ...):
        ...
        self._task = TaskHandler(self.runner, self.history_store, self.settings_store)
        self._settings = SettingsHandler(self.settings_store)
        self._conversation = ConversationHandler(
            self.settings_store,
            self.runner,
            self.conversation_store,
            self.memory_store,
            self.chat_client,
        )
        self._memory = MemoryHandler(self.memory_store)
        self._skill = SkillHandler(self.skill_store)
        self._rag = RAGHandler(self.rag_client)

    def run_task(self, user_input: str) -> dict[str, Any]:
        return self._task.run_task(user_input)

    # ... 其他方法同理
```

- [ ] **Step 10: 运行桌面 API 测试**

Run: `pytest tests/test_desktop_api.py -q`
Expected: 全部通过。

- [ ] **Step 11: Commit**

```bash
git add desktop/api.py desktop/api_handlers/
git commit -m "refactor: split desktop/api.py into domain handlers"
```

---

## Task 6: 拆分 core/loop.py

**Files:**
- Create: `core/loop_components.py`
- Modify: `core/loop.py`
- Test: `tests/test_loop.py`, `tests/test_main.py`

**Interfaces:**
- `run_minimal_loop(state, tool_registry, on_progress)` 签名不变。
- 新增 `StepExecutor`, `RetryController`, `ReplanController`, `ProgressEmitter`。

- [ ] **Step 1: 创建 ProgressEmitter**

```python
from __future__ import annotations

from typing import Any, Callable

from core.state import AgentState


class ProgressEmitter:
    def __init__(self, callback: Callable[[dict[str, Any]], None] | None = None):
        self.callback = callback

    def emit(self, event_type: str, state: AgentState, data: dict[str, Any]) -> None:
        if self.callback is None:
            return
        self.callback({"type": event_type, "task_id": state.task_id, "data": data})
```

- [ ] **Step 2: 创建 StepExecutor**

```python
from __future__ import annotations

from typing import Any

from core.executor import Executor
from core.router import Router
from core.state import Action, AgentState, PlanStep, ToolResult


class StepExecutor:
    def __init__(self, tool_registry: dict[str, Any] | None = None):
        self.router = Router()
        self.executor = Executor(tool_registry)

    def run_step(
        self,
        state: AgentState,
        step: PlanStep,
        previous_result: Any,
        feedback: Any,
    ) -> Action:
        action = self.router.choose_tool(state, step)
        action.params["previous_result"] = previous_result
        if feedback is not None:
            action.params["feedback"] = feedback
        return action

    def execute(self, action: Action) -> ToolResult:
        return self.executor.run(action)
```

- [ ] **Step 3: 创建 RetryController**

```python
from __future__ import annotations

from core.state import CheckResult, Feedback, PlanStep, ToolResult
from core.reflection import Reflection
from core.verifier import Verifier


class RetryController:
    def __init__(self):
        self.verifier = Verifier()
        self.reflection = Reflection()

    def attempt(
        self,
        state,
        step: PlanStep,
        action_factory,
        result_factory,
        progress,
    ):
        """返回 (completed: bool, result, check, feedback)。"""
        ...
```

- [ ] **Step 4: 创建 ReplanController**

```python
from __future__ import annotations

from core.planner import Planner
from core.state import AgentState, Feedback, Plan, PlanStep


class ReplanController:
    def __init__(self):
        self.planner = Planner()

    def maybe_replan(
        self,
        state: AgentState,
        failed_step: PlanStep,
        feedback: Feedback,
        old_plan: Plan,
        step_index: int,
    ) -> tuple[Plan | None, int]:
        ...
```

- [ ] **Step 5: 重写 core/loop.py**

`run_minimal_loop` 保持签名，内部组合上述组件。

- [ ] **Step 6: 运行 Loop 测试**

Run: `pytest tests/test_loop.py tests/test_main.py -q`
Expected: 全部通过。

- [ ] **Step 7: Commit**

```bash
git add core/loop.py core/loop_components.py
git commit -m "refactor: decompose core loop into step/retry/replan/emit components"
```

---

## Task 7: 全量回归测试

**Files:**
- 全部源码与测试

- [ ] **Step 1: 运行全部测试**

Run: `pytest tests/ -q`
Expected: `441 passed, 5 deselected`

- [ ] **Step 2: 检查 lint（若已安装 ruff）**

Run: `ruff check .`
Expected: 无错误（先修复新增问题）。

- [ ] **Step 3: Commit 最终调整**

```bash
git commit -m "chore: final regression fixes after refactor"
```

---

## Self-Review

**1. Spec coverage:**
- ✅ pyproject.toml：Task 1
- ✅ 重复文档清理：Task 2
- ✅ 统一工具注册表：Task 3
- ✅ LLMClient httpx 迁移：Task 4
- ✅ desktop/api.py 拆分：Task 5
- ✅ core/loop.py 拆分：Task 6
- ⚠️ API Key 钥匙串加密：未在本次计划内（P1 中较复杂、平台相关，建议单独计划）

**2. Placeholder scan:**
- 无 TBD/TODO/implement later。
- 代码块已给出关键实现片段。

**3. Type consistency:**
- `build_tool_registry` 参数与调用方一致。
- Handler 类构造函数与 `DesktopAPI.__init__` 注入一致。

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-07-02-uta-cleanup-refactor.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**

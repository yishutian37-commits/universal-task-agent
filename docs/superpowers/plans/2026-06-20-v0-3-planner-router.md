# UTA V0.3 Planner Router 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标:** 完成 `v0.3-planner-router`：新增 Planner 和 Router，让 Agent 根据 task_type 生成多步 plan，并按 step.goal 选择工具执行。

**架构:** `core/planner.py` 只负责把 `Task` 转成 `Plan`，不输出工具名。`core/router.py` 只负责把 `PlanStep.goal` 转成 `Action`，不执行工具。`core/loop.py` 执行完整 plan：Planner 生成步骤，Router 逐步选择工具，Executor 执行，Verifier 校验。

**技术栈:** Python 3.12，现有 dataclass 模型，pytest。

---

## 文件结构

- Create: `core/planner.py`
- Create: `core/router.py`
- Create: `tools/placeholder_tool.py`
- Create: `tests/test_planner.py`
- Create: `tests/test_router.py`
- Modify: `tools/registry.py`
- Modify: `core/loop.py`
- Modify: `tests/test_loop.py`
- Modify: `main.py`
- Modify: `tests/test_main.py`
- Modify: `README.md`
- Modify: `CHANGELOG.md`

---

### 任务 1：Planner

**Files:**
- Create: `core/planner.py`
- Create: `tests/test_planner.py`

- [ ] **步骤 1：写失败测试**

`tests/test_planner.py`：

```python
from core.planner import Planner
from core.state import Task


def make_task(task_type: str) -> Task:
    return Task(
        task_id="task_test",
        user_input="测试任务",
        task_type=task_type,
        intent="test",
        input_type="text",
        expected_output="report",
    )


def test_planner_creates_summary_plan_without_tools():
    plan = Planner().create_plan(make_task("summarize"))
    assert len(plan.steps) == 3
    assert [step.goal for step in plan.steps] == ["读取输入内容", "提取核心信息", "生成结构化报告"]
    assert not hasattr(plan.steps[0], "tool_name")


def test_planner_creates_data_analysis_plan():
    plan = Planner().create_plan(make_task("data_analysis"))
    assert [step.goal for step in plan.steps] == ["读取表格文件", "分析字段、行数、列数和缺失值", "生成表格分析报告"]


def test_planner_creates_unknown_fallback_plan():
    plan = Planner().create_plan(make_task("unknown"))
    assert len(plan.steps) == 1
    assert plan.steps[0].goal == "执行 V0.3 mock 工具"
```

- [ ] **步骤 2：运行红灯测试**

```bash
.venv/bin/python -m pytest tests/test_planner.py -v
```

Expected: FAIL because `core.planner` does not exist.

- [ ] **步骤 3：实现 Planner**

`core/planner.py`：

```python
from core.state import Plan, PlanStep, Task


class Planner:
    def create_plan(self, task: Task) -> Plan:
        goals = self._goals_for(task.task_type)
        return Plan(
            plan_id=f"plan_{task.task_id}",
            task_id=task.task_id,
            steps=[PlanStep(step_id=index, goal=goal) for index, goal in enumerate(goals, start=1)],
        )

    def _goals_for(self, task_type: str) -> list[str]:
        if task_type == "summarize":
            return ["读取输入内容", "提取核心信息", "生成结构化报告"]
        if task_type == "data_analysis":
            return ["读取表格文件", "分析字段、行数、列数和缺失值", "生成表格分析报告"]
        return ["执行 V0.3 mock 工具"]
```

- [ ] **步骤 4：运行绿灯测试**

```bash
.venv/bin/python -m pytest tests/test_planner.py -v
```

Expected: PASS.

- [ ] **步骤 5：提交**

```bash
git add core/planner.py tests/test_planner.py
git commit -m "feat: add planner"
```

---

### 任务 2：Router

**Files:**
- Create: `core/router.py`
- Create: `tests/test_router.py`

- [ ] **步骤 1：写失败测试**

`tests/test_router.py`：

```python
from core.router import Router
from core.state import AgentState, PlanStep


def route(goal: str):
    state = AgentState(task_id="task_test", user_input="测试")
    return Router().choose_tool(state, PlanStep(step_id=1, goal=goal))


def test_router_routes_reading_goal_to_file_tool():
    action = route("读取输入内容")
    assert action.tool_name == "file_tool"
    assert action.action_name == "read"
    assert action.reason


def test_router_routes_text_goal_to_text_tool():
    action = route("提取核心信息")
    assert action.tool_name == "text_tool"
    assert action.action_name == "process"


def test_router_routes_table_goal_to_table_tool():
    action = route("分析字段、行数、列数和缺失值")
    assert action.tool_name == "table_tool"
    assert action.action_name == "analyze"


def test_router_routes_report_goal_to_report_tool():
    action = route("生成结构化报告")
    assert action.tool_name == "report_tool"
    assert action.action_name == "generate"


def test_router_falls_back_to_mock_tool():
    action = route("执行 V0.3 mock 工具")
    assert action.tool_name == "mock_tool"
    assert action.action_name == "run"
```

- [ ] **步骤 2：运行红灯测试**

```bash
.venv/bin/python -m pytest tests/test_router.py -v
```

Expected: FAIL because `core.router` does not exist.

- [ ] **步骤 3：实现 Router**

`core/router.py`：

```python
from core.state import Action, AgentState, PlanStep


class Router:
    RULES = [
        (("读取", "文件", "txt", "md", "csv", "excel", "表格文件"), "file_tool", "read"),
        (("文本", "摘要", "提取", "核心信息", "核心观点", "风险"), "text_tool", "process"),
        (("表格", "字段", "行数", "列数", "缺失值", "异常值"), "table_tool", "analyze"),
        (("报告", "Markdown", "输出"), "report_tool", "generate"),
    ]

    def choose_tool(self, state: AgentState, step: PlanStep) -> Action:
        goal_lower = step.goal.lower()
        for keywords, tool_name, action_name in self.RULES:
            if any(keyword.lower() in goal_lower for keyword in keywords):
                return self._action(state, step, tool_name, action_name, f"规则命中：{step.goal}")
        return self._action(state, step, "mock_tool", "run", "规则未命中，使用 mock_tool 兜底")

    def _action(self, state: AgentState, step: PlanStep, tool_name: str, action_name: str, reason: str) -> Action:
        return Action(
            action_id=f"action_{state.task_id}_{step.step_id}",
            step_id=step.step_id,
            tool_name=tool_name,
            action_name=action_name,
            params={"user_input": state.user_input, "goal": step.goal},
            reason=reason,
        )
```

- [ ] **步骤 4：运行绿灯测试**

```bash
.venv/bin/python -m pytest tests/test_router.py -v
```

Expected: PASS.

- [ ] **步骤 5：提交**

```bash
git add core/router.py tests/test_router.py
git commit -m "feat: add router"
```

---

### 任务 3：占位工具注册

**Files:**
- Create: `tools/placeholder_tool.py`
- Modify: `tools/registry.py`
- Modify: `tests/test_mock_tool.py`

- [ ] **步骤 1：写失败测试**

在 `tests/test_mock_tool.py` 增加：

```python
def test_registry_contains_v0_3_placeholder_tools():
    for name in ["file_tool", "text_tool", "table_tool", "report_tool"]:
        assert name in TOOL_REGISTRY
        assert TOOL_REGISTRY[name].run("any", {"goal": "test"})["message"] == "mock result"
```

- [ ] **步骤 2：运行红灯测试**

```bash
.venv/bin/python -m pytest tests/test_mock_tool.py -v
```

Expected: FAIL because placeholder tools are not registered.

- [ ] **步骤 3：实现占位工具和注册表**

`tools/placeholder_tool.py`：

```python
from typing import Any

from tools.base_tool import BaseTool


class PlaceholderTool(BaseTool):
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    def run(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        return {"message": "mock result", "action_name": action_name, "tool_name": self.name, "echo": params}
```

`tools/registry.py` 注册 `file_tool`、`text_tool`、`table_tool`、`report_tool`。

- [ ] **步骤 4：运行绿灯测试**

```bash
.venv/bin/python -m pytest tests/test_mock_tool.py -v
```

Expected: PASS.

- [ ] **步骤 5：提交**

```bash
git add tools/placeholder_tool.py tools/registry.py tests/test_mock_tool.py
git commit -m "feat: register placeholder tools"
```

---

### 任务 4：Loop 接入 Planner + Router

**Files:**
- Modify: `core/loop.py`
- Modify: `tests/test_loop.py`

- [ ] **步骤 1：写失败测试**

更新 `tests/test_loop.py`：保留 v0.1 兼容测试，新增：

```python
from core.planner import Planner


def test_loop_executes_full_planned_summary_flow():
    state = AgentState(task_id="task_test", user_input="帮我总结", task_type="summarize", intent="summarize_article")
    updated = run_minimal_loop(state)
    assert updated.status == "completed"
    assert len(updated.plan.steps) == 3
    assert len(updated.results) == 3
    assert len(updated.checks) == 3
    assert [step.status for step in updated.plan.steps] == ["completed", "completed", "completed"]
    assert updated.results[0].tool_name == "file_tool"
    assert updated.results[1].tool_name == "text_tool"
    assert updated.results[2].tool_name == "report_tool"
```

- [ ] **步骤 2：运行红灯测试**

```bash
.venv/bin/python -m pytest tests/test_loop.py -v
```

Expected: FAIL because loop still hard-codes one step.

- [ ] **步骤 3：改造 `run_minimal_loop`**

实现要求：

- 用 `Task` 从 state 构造 Planner 输入；
- `Planner().create_plan(task)` 生成 plan；
- 遍历 plan.steps；
- 每步 `Router().choose_tool(state, step)`；
- 每步执行 Executor 和 Verifier；
- 任一步失败则 state failed 并停止；
- 全部完成则 state completed；
- `final_output` 使用最后一个 result 的 `message`。

- [ ] **步骤 4：运行绿灯测试**

```bash
.venv/bin/python -m pytest tests/test_loop.py -v
```

Expected: PASS.

- [ ] **步骤 5：提交**

```bash
git add core/loop.py tests/test_loop.py
git commit -m "feat: execute planned routed steps"
```

---

### 任务 5：Main 日志和文档

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main.py`
- Modify: `README.md`
- Modify: `CHANGELOG.md`

- [ ] **步骤 1：写失败测试**

在 `tests/test_main.py` 增加断言：

```python
assert len(saved["plan"]["steps"]) == 3
assert "[Planner] created 3 steps" in log_text
assert "[Router] selected tool = file_tool" in log_text
```

- [ ] **步骤 2：运行红灯测试**

```bash
.venv/bin/python -m pytest tests/test_main.py -v
```

Expected: FAIL because log does not include Planner/Router lines yet.

- [ ] **步骤 3：更新日志和文档**

`build_log_lines()` 增加 Planner 和每步 Router 信息。

README 当前状态增加：

```markdown
- `v0.3-planner-router`: 新增 Planner 和 Router，执行多步计划，但仍使用占位工具。
```

CHANGELOG 增加：

```markdown
- Add `v0.3-planner-router` with Planner and Router.
```

- [ ] **步骤 4：运行绿灯测试**

```bash
.venv/bin/python -m pytest tests/test_main.py -v
```

Expected: PASS.

- [ ] **步骤 5：提交**

```bash
git add main.py tests/test_main.py README.md CHANGELOG.md
git commit -m "docs: document v0.3 planner router flow"
```

---

### 任务 6：验证和 tag

**Files:**
- No source changes expected.

- [ ] **步骤 1：运行完整测试**

```bash
.venv/bin/python -m pytest -v
```

Expected: all tests PASS.

- [ ] **步骤 2：运行 demo**

```bash
.venv/bin/python main.py --task "帮我总结一段文本"
```

Expected:

```text
任务已完成：mock result
```

- [ ] **步骤 3：检查工作区和密钥**

```bash
git status --short
git grep -n -E 'tp-[[:alnum:]]{20,}' || true
```

Expected: clean status and no tracked key.

- [ ] **步骤 4：打 tag**

```bash
git tag v0.3-planner-router
git tag --list "v0.3-planner-router"
```

Expected:

```text
v0.3-planner-router
```

---

## 自查

- Spec 覆盖：计划覆盖 Planner、Router、占位工具、Loop/Main 接入、日志、文档、测试、tag。
- 范围检查：计划不做真实总结、真实文件读取、真实表格分析、Reflection、retry/replan、Memory、Skill、TAM。
- 类型一致性：使用现有 `Task`、`Plan`、`PlanStep`、`Action`、`ToolResult`、`CheckResult`。

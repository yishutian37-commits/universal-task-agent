# UTA V1.0 与桌面记忆可视化实施计划

> **For agentic workers / 给执行 Agent 的说明：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐步执行本计划。步骤使用 checkbox（`- [ ]`）记录进度。

**Goal / 目标：** 补齐 PRD V1.0 的 A11 replan、完成 V1.0 文档/demo/tag，并把 replan 状态和短期/长期记忆可视化打包进当前桌面端。

**Architecture / 架构：** 分两条线交付。核心主线从 `main` 建临时 worktree，在干净线完成 replan、文档、demo 和 `v1.0-learning-agent` tag；随后当前 `codex/v2-desktop-app` 桌面分支吸收核心改动，新增只读 memory store/API 和前端“记忆”页面，最后重新打包 `.app`。

**Tech Stack / 技术栈：** Python 3.12、pytest、dataclass JSON state、vanilla HTML/CSS/JS、pywebview、PyInstaller、Git tag。

---

## 文件结构

核心主线会修改：

- `core/state.py`：给 `AgentState` 增加 `replan_count` 和 `replan_events`。
- `core/loop.py`：实现 retry exhausted 后的一次 replan、进度事件、replan state 记录。
- `main.py`：更新 CLI 版本描述，并在 log 中记录 replan。
- `tests/test_loop.py`：增加 A11 replan 行为测试。
- `tests/test_state.py`：覆盖 replan 字段导出。
- `tests/test_main.py`：覆盖 log 中的 replan 信息。
- `README.md`：更新 V1.0 状态、demo、短期/长期记忆说明。
- `CHANGELOG.md`：新增 V1.0 条目。

桌面分支会额外修改：

- `desktop/memory_store.py`：新增只读 JSON Memory 读取器。
- `desktop/api.py`：新增 `get_memory_overview()`。
- `tests/test_desktop_memory_store.py`：覆盖 memory store。
- `tests/test_desktop_api.py`：覆盖 DesktopAPI memory 方法。
- `desktop/frontend/index.html`：新增“记忆”导航和记忆页面容器。
- `desktop/frontend/app.js`：新增记忆加载、渲染、replan 事件显示。
- `desktop/frontend/style.css`：新增记忆页面样式。
- `tests/test_desktop_frontend_assets.py`：覆盖前端入口、bridge 调用和布局标记。
- `desktop/README.md`：说明桌面端可查看状态和只读记忆。

不要处理这些既有脏文件，除非用户单独要求：

- `memory/lessons.json`
- `memory/skill_candidates.json`
- `memory/task_history.json`
- `.od-skills/`
- `critique.json`
- 原型 HTML / artifact 文件

---

## Task 0：创建核心 V1.0 临时 worktree

**文件：**
- 不修改源码。

- [ ] **Step 1：确认当前分支和脏文件**

运行：

```bash
git status -sb
git branch --show-current
```

预期：

```text
## codex/v2-desktop-app
```

且只看到已有 memory/原型脏文件，不要 stage 它们。

- [ ] **Step 2：创建临时 worktree**

运行：

```bash
git worktree add /private/tmp/uta-v1-learning-agent -b codex/v1-learning-agent main
```

预期：

```text
Preparing worktree (new branch 'codex/v1-learning-agent')
HEAD is now at ...
```

说明：使用 `/private/tmp`，不需要修改 `.gitignore`，也不会把 worktree 目录放进项目里。

- [ ] **Step 3：在 worktree 跑基线测试**

运行：

```bash
cd /private/tmp/uta-v1-learning-agent
.venv/bin/python -m pytest -q
```

如果 `.venv/bin/python` 不存在，使用主仓库解释器：

```bash
PYTHON=/Users/tianjiashu/项目/.venv/bin/python
$PYTHON -m pytest -q
```

预期：

```text
all tests pass
```

如果基线失败，先停下来记录失败，不进入 Task 1。

---

## Task 1：核心 A11 replan

**文件：**
- 修改： `/private/tmp/uta-v1-learning-agent/core/state.py`
- 修改： `/private/tmp/uta-v1-learning-agent/core/loop.py`
- 修改： `/private/tmp/uta-v1-learning-agent/main.py`
- 测试： `/private/tmp/uta-v1-learning-agent/tests/test_loop.py`
- 测试： `/private/tmp/uta-v1-learning-agent/tests/test_state.py`
- 测试： `/private/tmp/uta-v1-learning-agent/tests/test_main.py`

- [ ] **Step 1：写失败测试：replan 后不重跑前置 step**

在 `tests/test_loop.py` 增加测试工具：

```python
class CountingTool(BaseTool):
    name = "counting_tool"
    description = "counts calls"

    def __init__(self, message):
        self.message = message
        self.calls = 0

    def run(self, action_name, params):
        self.calls += 1
        return {"message": self.message, "call": self.calls}
```

增加测试：

```python
def test_loop_replans_once_without_rerunning_completed_steps():
    file_tool = CountingTool("file")
    text_tool = SequenceTextTool([
        "## 摘要\n缺少小节。",
        "## 摘要\n还是缺少。",
        "## 摘要\n继续缺少。",
        VALID_SUMMARY_REPORT,
    ])
    report_tool = EchoTool(VALID_SUMMARY_REPORT)
    registry = {
        "file_tool": file_tool,
        "text_tool": text_tool,
        "report_tool": report_tool,
    }
    state = AgentState(
        task_id="task_test",
        user_input="帮我总结",
        task_type="summarize",
        intent="summarize_article",
        max_replans=1,
    )

    updated = run_minimal_loop(state, tool_registry=registry)

    assert updated.status == "completed"
    assert updated.replan_count == 1
    assert len(updated.replan_events) == 1
    assert updated.replan_events[0]["failed_step_id"] == 2
    assert updated.replan_events[0]["resume_step_id"] == 2
    assert file_tool.calls == 1
    assert len(text_tool.params_seen) == 4
    assert updated.final_output == VALID_SUMMARY_REPORT
```

- [ ] **Step 2：写失败测试：replan 用完后仍失败**

在 `tests/test_loop.py` 增加：

```python
def test_loop_fails_when_replan_budget_is_exhausted():
    text_tool = SequenceTextTool([
        "## 摘要\n缺少小节。",
        "## 摘要\n还是缺少。",
        "## 摘要\n继续缺少。",
    ])
    registry = {
        "file_tool": EchoTool("file"),
        "text_tool": text_tool,
        "report_tool": EchoTool(VALID_SUMMARY_REPORT),
    }
    state = AgentState(
        task_id="task_test",
        user_input="帮我总结",
        task_type="summarize",
        intent="summarize_article",
        max_replans=0,
    )

    updated = run_minimal_loop(state, tool_registry=registry)

    assert updated.status == "failed"
    assert updated.replan_count == 0
    assert updated.replan_events == []
```

- [ ] **Step 3：写失败测试：progress 包含 replanned**

在 `tests/test_loop.py` 增加：

```python
def test_loop_emits_replanned_progress_event():
    text_tool = SequenceTextTool([
        "## 摘要\n缺少小节。",
        "## 摘要\n还是缺少。",
        "## 摘要\n继续缺少。",
        VALID_SUMMARY_REPORT,
    ])
    registry = {
        "file_tool": EchoTool("file"),
        "text_tool": text_tool,
        "report_tool": EchoTool(VALID_SUMMARY_REPORT),
    }
    state = AgentState(
        task_id="task_test",
        user_input="帮我总结",
        task_type="summarize",
        intent="summarize_article",
        max_replans=1,
    )
    events = []

    run_minimal_loop(state, tool_registry=registry, on_progress=events.append)

    replanned = [event for event in events if event["type"] == "replanned"]
    assert len(replanned) == 1
    assert replanned[0]["data"]["failed_step_id"] == 2
    assert replanned[0]["data"]["resume_step_id"] == 2
```

- [ ] **Step 4：写失败测试：state 导出包含 replan 字段**

在 `tests/test_state.py` 增加：

```python
def test_agent_state_exports_replan_tracking_fields():
    state = AgentState(task_id="task_test", user_input="测试")
    state.replan_count = 1
    state.replan_events.append({"failed_step_id": 2, "resume_step_id": 2})

    exported = state.to_dict()

    assert exported["replan_count"] == 1
    assert exported["replan_events"] == [{"failed_step_id": 2, "resume_step_id": 2}]
```

- [ ] **Step 5：写失败测试：log 包含 replan**

在 `tests/test_main.py` 增加：

```python
def test_build_log_lines_includes_replan_events():
    state = AgentState(task_id="task_test", user_input="测试", task_type="summarize")
    state.replan_count = 1
    state.replan_events.append(
        {
            "failed_step_id": 2,
            "failed_goal": "提取核心信息",
            "resume_step_id": 2,
            "root_cause": "缺少必要小节：风险点",
        }
    )

    lines = build_log_lines(state)

    assert "[Replan] count = 1" in lines
    assert "[Replan] failed_step = 2, resume_step = 2" in lines
```

- [ ] **Step 6：确认目标测试失败**

运行：

```bash
cd /private/tmp/uta-v1-learning-agent
PYTHON=/Users/tianjiashu/项目/.venv/bin/python
$PYTHON -m pytest tests/test_loop.py tests/test_state.py tests/test_main.py -q
```

预期：

```text
FAIL
```

失败原因应为 `AgentState` 没有 `replan_count` / `replan_events`，loop 没有 replan。

- [ ] **Step 7：实现 AgentState 字段**

在 `core/state.py` 的 `AgentState` 中加：

```python
replan_count: int = 0
replan_events: list[dict[str, Any]] = field(default_factory=list)
```

- [ ] **Step 8：实现 replan helper**

在 `core/loop.py` 增加 helper：

```python
def _plan_goals(plan):
    if plan is None:
        return []
    return [step.goal for step in plan.steps]


def _record_replan(state, failed_step, feedback, old_plan, new_plan, resume_step_id):
    event = {
        "failed_step_id": failed_step.step_id,
        "failed_goal": failed_step.goal,
        "root_cause": feedback.root_cause,
        "repair_strategy": feedback.repair_strategy,
        "old_plan_goals": _plan_goals(old_plan),
        "new_plan_goals": _plan_goals(new_plan),
        "resume_step_id": resume_step_id,
        "created_at": state.updated_at,
    }
    state.replan_count += 1
    state.replan_events.append(event)
    return event
```

- [ ] **Step 9：改写 loop 为 while index 模式**

把 `for step in state.plan.steps:` 改成 `step_index = 0` 的 while 循环。核心逻辑：

```python
step_index = 0
while step_index < len(state.plan.steps):
    step = state.plan.steps[step_index]
    ...
    if step.status == "completed":
        step_index += 1
        continue
    if state.replan_count < state.max_replans:
        old_plan = state.plan
        new_plan = planner.create_plan(_task_from_state(state), matched_skill=state.matched_skill)
        new_plan.status = "running"
        resume_index = step_index
        if resume_index >= len(new_plan.steps):
            # fail with clear output
        for completed_index in range(resume_index):
            new_plan.steps[completed_index].status = "completed"
        state.plan = new_plan
        state.current_step_id = new_plan.steps[resume_index].step_id
        event = _record_replan(state, step, feedback, old_plan, new_plan, resume_index + 1)
        _emit_progress(on_progress, "replanned", state, event)
        step_index = resume_index
        continue
    # fail as before
```

实现时保持现有 retry 行为、`previous_step_result` 传递和 `final_output` 行为不变。

- [ ] **Step 10：更新 main log**

在 `main.py` 的 `build_log_lines()` 中，在 Reflection 后或 Memory 前加入：

```python
lines.append(f"[Replan] count = {state.replan_count}")
for event in state.replan_events:
    lines.append(
        "[Replan] failed_step = "
        f"{event.get('failed_step_id')}, resume_step = {event.get('resume_step_id')}"
    )
```

- [ ] **Step 11：跑目标测试**

运行：

```bash
cd /private/tmp/uta-v1-learning-agent
PYTHON=/Users/tianjiashu/项目/.venv/bin/python
$PYTHON -m pytest tests/test_loop.py tests/test_state.py tests/test_main.py -q
```

预期：

```text
all selected tests pass
```

- [ ] **Step 12：跑全量核心测试**

运行：

```bash
cd /private/tmp/uta-v1-learning-agent
PYTHON=/Users/tianjiashu/项目/.venv/bin/python
$PYTHON -m pytest -q
```

预期：

```text
all tests pass
```

- [ ] **Step 13：提交核心 replan**

运行：

```bash
cd /private/tmp/uta-v1-learning-agent
git add core/state.py core/loop.py main.py tests/test_loop.py tests/test_state.py tests/test_main.py
git commit -m "feat: add v1 replan support"
```

---

## Task 2：核心 V1.0 文档、demo 与 tag

**文件：**
- 修改： `/private/tmp/uta-v1-learning-agent/README.md`
- 修改： `/private/tmp/uta-v1-learning-agent/CHANGELOG.md`
- 修改： `/private/tmp/uta-v1-learning-agent/main.py`

- [ ] **Step 1：更新 README**

把 README 开头改为：

```markdown
# Universal Task Agent

UTA 是一个学习型 Agent 框架。当前核心里程碑是 `v1.0-learning-agent`：支持文本总结和表格分析两类任务，跑通 Task Parser、Planner、Agent Loop、Router、Executor、Verifier、Reflection、Replan、JSON Memory 和 Skill Loader。
```

新增“短期记忆与长期记忆”小节：

```markdown
## 短期记忆与长期记忆

- 短期记忆：单次任务内的 `AgentState`，保存到 `outputs/states/<task_id>_state.json`，日志保存到 `outputs/logs/<task_id>.log`。
- 长期记忆：跨任务 JSON Memory，保存在 `memory/*.json`。
- `memory/task_history.json`：任务历史。
- `memory/lessons.json`：成功任务沉淀出的可复用经验。
- `memory/negative_rules.json`：失败任务沉淀出的负向规则。
- `memory/skill_candidates.json`：可能值得人工确认成 Skill 的候选。
```

新增“V1.0 Demo”小节，包含 summary 和 table 命令。

- [ ] **Step 2：更新 CHANGELOG**

在顶部新增：

```markdown
## v1.0-learning-agent

- 补齐 UTA 学习型 Agent 核心闭环，覆盖文本总结和表格分析两类任务。
- 在单个 step 重试耗尽后增加一次 replan，并把 replan 事件保存到 state/log。
- 补充短期 State 记忆和长期 JSON Memory 的说明。
- 使用文本总结 demo 和表格分析 demo 完成 V1.0 验收。
```

说明：CHANGELOG 本轮统一写中文，避免交付文档对用户不可读。

- [ ] **Step 3：更新 main.py CLI 描述**

把：

```python
argparse.ArgumentParser(description="Universal Task Agent V0.6")
```

改为：

```python
argparse.ArgumentParser(description="Universal Task Agent V1.0 Learning Agent")
```

- [ ] **Step 4：跑文档相关测试**

运行：

```bash
cd /private/tmp/uta-v1-learning-agent
PYTHON=/Users/tianjiashu/项目/.venv/bin/python
$PYTHON -m pytest tests/test_main.py -q
```

预期：

```text
pass
```

- [ ] **Step 5：跑文本总结 demo**

运行：

```bash
cd /private/tmp/uta-v1-learning-agent
PYTHON=/Users/tianjiashu/项目/.venv/bin/python
$PYTHON main.py --output-root /private/tmp/uta-v1-summary --task "帮我总结一段文本：UTA V1.0 要跑通 Agent Loop、Verifier、Memory 和 Skill。"
```

预期：

```text
命令退出 0
输出包含 任务已完成 或 任务失败 但不能 crash
/private/tmp/uta-v1-summary/states/ 下有 state JSON
/private/tmp/uta-v1-summary/logs/ 下有 log
```

- [ ] **Step 6：跑表格分析 demo**

运行：

```bash
cd /private/tmp/uta-v1-learning-agent
PYTHON=/Users/tianjiashu/项目/.venv/bin/python
$PYTHON main.py --output-root /private/tmp/uta-v1-table --task "分析 examples/orders.csv"
```

预期：

```text
命令退出 0
输出包含 字段说明 或 基础统计
/private/tmp/uta-v1-table/states/ 下有 state JSON
/private/tmp/uta-v1-table/logs/ 下有 log
```

- [ ] **Step 7：跑全量测试**

运行：

```bash
cd /private/tmp/uta-v1-learning-agent
PYTHON=/Users/tianjiashu/项目/.venv/bin/python
$PYTHON -m pytest -q
```

预期：

```text
all tests pass
```

- [ ] **Step 8：提交 V1.0 文档**

运行：

```bash
cd /private/tmp/uta-v1-learning-agent
git add README.md CHANGELOG.md main.py
git commit -m "docs: document v1 learning agent"
```

- [ ] **Step 9：打核心 tag**

运行：

```bash
cd /private/tmp/uta-v1-learning-agent
git tag v1.0-learning-agent
```

预期：

```text
git tag --list v1.0-learning-agent
```

显示 `v1.0-learning-agent`。

---

## Task 3：把核心 V1.0 改动同步到桌面分支

**文件：**
- Modify in `/Users/tianjiashu/项目`: same core files changed in Tasks 1-2.

- [ ] **Step 1：回到当前桌面分支**

运行：

```bash
cd /Users/tianjiashu/项目
git branch --show-current
```

预期：

```text
codex/v2-desktop-app
```

- [ ] **Step 2：cherry-pick 核心分支改动**

运行：

```bash
git cherry-pick codex/v1-learning-agent
```

如果核心分支有两个提交，使用：

```bash
git cherry-pick main..codex/v1-learning-agent
```

预期：

```text
core/state.py、core/loop.py、main.py、README.md、CHANGELOG.md、tests/* 被同步
```

不要 stage 或修改既有 memory/原型脏文件。

- [ ] **Step 3：跑桌面分支全量测试**

运行：

```bash
cd /Users/tianjiashu/项目
.venv/bin/python -m pytest -q
```

预期：

```text
all tests pass
```

---

## Task 4：桌面 memory store 与 API

**文件：**
- 新建： `desktop/memory_store.py`
- 修改： `desktop/api.py`
- 测试： `tests/test_desktop_memory_store.py`
- 测试： `tests/test_desktop_api.py`

- [ ] **Step 1：写 failing memory store tests**

新增 `tests/test_desktop_memory_store.py`：

```python
import json

from desktop.memory_store import MemoryStore


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_memory_store_returns_empty_defaults_when_files_are_missing(tmp_path):
    result = MemoryStore(tmp_path).overview()

    assert result["ok"] is True
    assert result["task_history"] == []
    assert result["lessons"] == []
    assert result["negative_rules"] == []
    assert result["skill_candidates"] == []
    assert result["user_profile"] == {}
    assert result["counts"] == {
        "tasks": 0,
        "lessons": 0,
        "negative_rules": 0,
        "skill_candidates": 0,
    }


def test_memory_store_reads_all_memory_files(tmp_path):
    write_json(tmp_path / "task_history.json", {"version": 1, "tasks": [{"task_id": "task_1"}]})
    write_json(tmp_path / "lessons.json", {"version": 1, "lessons": [{"lesson_id": "lesson_1"}]})
    write_json(tmp_path / "negative_rules.json", {"version": 1, "negative_rules": [{"rule_id": "rule_1"}]})
    write_json(tmp_path / "skill_candidates.json", {"version": 1, "candidates": [{"task_type": "summarize"}]})
    write_json(tmp_path / "user_profile.json", {"version": 1, "profile": {"name": "UTA"}})

    result = MemoryStore(tmp_path).overview()

    assert result["ok"] is True
    assert result["task_history"] == [{"task_id": "task_1"}]
    assert result["lessons"] == [{"lesson_id": "lesson_1"}]
    assert result["negative_rules"] == [{"rule_id": "rule_1"}]
    assert result["skill_candidates"] == [{"task_type": "summarize"}]
    assert result["user_profile"] == {"name": "UTA"}
    assert result["counts"]["tasks"] == 1


def test_memory_store_reports_invalid_json(tmp_path):
    (tmp_path / "task_history.json").write_text("{bad json", encoding="utf-8")

    result = MemoryStore(tmp_path).overview()

    assert result["ok"] is False
    assert "task_history.json" in result["error"]
```

- [ ] **Step 2：确认测试失败**

运行：

```bash
.venv/bin/python -m pytest tests/test_desktop_memory_store.py -q
```

预期：

```text
ModuleNotFoundError: No module named 'desktop.memory_store'
```

- [ ] **Step 3：实现 MemoryStore**

新增 `desktop/memory_store.py`：

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MemoryStore:
    def __init__(self, memory_root: Path | str):
        self.memory_root = Path(memory_root)

    def overview(self) -> dict[str, Any]:
        try:
            task_history = self._list_from_file("task_history.json", "tasks")
            lessons = self._list_from_file("lessons.json", "lessons")
            negative_rules = self._list_from_file("negative_rules.json", "negative_rules")
            skill_candidates = self._list_from_file("skill_candidates.json", "candidates")
            user_profile = self._dict_from_file("user_profile.json", "profile")
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        return {
            "ok": True,
            "task_history": task_history,
            "lessons": lessons,
            "negative_rules": negative_rules,
            "skill_candidates": skill_candidates,
            "user_profile": user_profile,
            "counts": {
                "tasks": len(task_history),
                "lessons": len(lessons),
                "negative_rules": len(negative_rules),
                "skill_candidates": len(skill_candidates),
            },
        }

    def _list_from_file(self, filename: str, key: str) -> list[dict[str, Any]]:
        payload = self._read_payload(filename)
        value = payload.get(key, [])
        return value if isinstance(value, list) else []

    def _dict_from_file(self, filename: str, key: str) -> dict[str, Any]:
        payload = self._read_payload(filename)
        value = payload.get(key, {})
        return value if isinstance(value, dict) else {}

    def _read_payload(self, filename: str) -> dict[str, Any]:
        path = self.memory_root / filename
        if not path.exists():
            return {}
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"{filename} 无法读取或 JSON 无效") from exc
        return parsed if isinstance(parsed, dict) else {}
```

- [ ] **Step 4：扩展 DesktopAPI tests**

在 `tests/test_desktop_api.py` 增加 fake：

```python
class FakeMemoryStore:
    def __init__(self):
        self.called = False

    def overview(self):
        self.called = True
        return {"ok": True, "task_history": [], "lessons": [], "negative_rules": [], "skill_candidates": [], "user_profile": {}, "counts": {"tasks": 0, "lessons": 0, "negative_rules": 0, "skill_candidates": 0}}
```

更新 `DesktopAPI(...)` 构造支持 `memory_store=...`，并新增测试：

```python
def test_desktop_api_gets_memory_overview(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    memory_store = FakeMemoryStore()
    api = DesktopAPI(settings_store=SettingsStore(), runner=FakeRunner(), memory_store=memory_store)

    result = api.get_memory_overview()

    assert result["ok"] is True
    assert memory_store.called is True
```

- [ ] **Step 5：实现 DesktopAPI memory 方法**

在 `desktop/api.py`：

```python
from desktop.memory_store import MemoryStore
```

构造函数增加：

```python
memory_store: MemoryStore | None = None,
```

初始化：

```python
self.memory_store = memory_store if memory_store is not None else MemoryStore(uta_home() / "memory")
```

新增方法：

```python
def get_memory_overview(self) -> dict[str, Any]:
    try:
        return self.memory_store.overview()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
```

- [ ] **Step 6：跑桌面 API tests**

运行：

```bash
.venv/bin/python -m pytest tests/test_desktop_memory_store.py tests/test_desktop_api.py -q
```

预期：

```text
pass
```

- [ ] **Step 7：提交 memory API**

运行：

```bash
git add desktop/memory_store.py desktop/api.py tests/test_desktop_memory_store.py tests/test_desktop_api.py
git commit -m "feat: expose desktop memory overview"
```

---

## Task 5：桌面前端状态与记忆页面

**文件：**
- 修改： `desktop/frontend/index.html`
- 修改： `desktop/frontend/app.js`
- 修改： `desktop/frontend/style.css`
- 测试： `tests/test_desktop_frontend_assets.py`

- [ ] **Step 1：写前端 asset tests**

在 `tests/test_desktop_frontend_assets.py` 增加：

```python
def test_frontend_includes_memory_view():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    assert 'id="openMemory"' in html
    assert "记忆" in html
    assert 'id="memoryView"' in html
    assert 'id="memoryShortTerm"' in html
    assert 'id="memoryTaskHistory"' in html
    assert 'id="memoryLessons"' in html
    assert 'id="memoryNegativeRules"' in html
    assert 'id="memorySkillCandidates"' in html


def test_frontend_calls_memory_bridge_method():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'callApi("get_memory_overview")' in js
    assert "function showMemoryView" in js
    assert "function renderMemoryOverview" in js


def test_frontend_handles_replanned_progress_event():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'event.type === "replanned"' in js
    assert "replan" in js.lower()
```

- [ ] **Step 2：确认测试失败**

运行：

```bash
.venv/bin/python -m pytest tests/test_desktop_frontend_assets.py -q
```

预期：

```text
FAIL
```

- [ ] **Step 3：修改 HTML**

在 sidebar 加：

```html
<button class="nav" type="button" id="openMemory">记忆</button>
```

在 `historyView` 后新增：

```html
<section class="workspace memoryWorkspace hidden" id="memoryView">
  <div class="memoryColumn">
    <section class="panel memoryPanel">
      <div class="panelHead">
        <h3>短期记忆</h3>
        <button class="button secondary compact" type="button" id="refreshMemory">刷新</button>
      </div>
      <div class="memoryBlock" id="memoryShortTerm"></div>
    </section>
    <section class="panel memoryPanel">
      <div class="panelHead"><h3>任务历史</h3></div>
      <div class="memoryBlock" id="memoryTaskHistory"></div>
    </section>
  </div>
  <div class="memoryColumn">
    <section class="panel memoryPanel">
      <div class="panelHead"><h3>经验</h3></div>
      <div class="memoryBlock" id="memoryLessons"></div>
    </section>
    <section class="panel memoryPanel">
      <div class="panelHead"><h3>负向规则</h3></div>
      <div class="memoryBlock" id="memoryNegativeRules"></div>
    </section>
    <section class="panel memoryPanel">
      <div class="panelHead"><h3>Skill 候选</h3></div>
      <div class="memoryBlock" id="memorySkillCandidates"></div>
    </section>
  </div>
</section>
```

- [ ] **Step 4：修改 JS 元素映射与导航**

在 `els` 增加：

```javascript
openMemory: document.getElementById("openMemory"),
memoryView: document.getElementById("memoryView"),
refreshMemory: document.getElementById("refreshMemory"),
memoryShortTerm: document.getElementById("memoryShortTerm"),
memoryTaskHistory: document.getElementById("memoryTaskHistory"),
memoryLessons: document.getElementById("memoryLessons"),
memoryNegativeRules: document.getElementById("memoryNegativeRules"),
memorySkillCandidates: document.getElementById("memorySkillCandidates"),
```

新增：

```javascript
async function showMemoryView() {
  els.taskView.classList.add("hidden");
  els.historyView.classList.add("hidden");
  els.memoryView.classList.remove("hidden");
  setActiveNav(els.openMemory);
  await loadMemoryOverview();
}
```

更新 `showTaskView()` 和 `showHistoryView()`：都要把 `memoryView` 加上 hidden。

- [ ] **Step 5：实现 memory 渲染**

在 `app.js` 增加：

```javascript
async function loadMemoryOverview() {
  try {
    const result = await callApi("get_memory_overview");
    if (!result.ok) {
      showToast("读取记忆失败", result.error || "未知错误");
      return;
    }
    renderMemoryOverview(result);
  } catch (error) {
    showToast("读取记忆失败", error.message);
  }
}

function renderMemoryOverview(memory) {
  els.memoryShortTerm.innerHTML = renderShortTermMemory();
  els.memoryTaskHistory.innerHTML = renderMemoryCards(memory.task_history, "task_id", "暂无任务历史");
  els.memoryLessons.innerHTML = renderMemoryCards(memory.lessons, "lesson_id", "暂无经验");
  els.memoryNegativeRules.innerHTML = renderMemoryCards(memory.negative_rules, "rule_id", "暂无负向规则");
  els.memorySkillCandidates.innerHTML = renderMemoryCards(memory.skill_candidates, "task_type", "暂无 Skill 候选");
}

function renderShortTermMemory() {
  if (!state.taskId) {
    return '<div class="emptyState">当前没有运行中的任务，可从运行记录查看历史 state。</div>';
  }
  return `<div class="memoryCard"><strong>${escapeHtml(state.taskId)}</strong><small>当前任务 state 会在右侧 state.json 和运行记录中保存。</small></div>`;
}

function renderMemoryCards(items, titleKey, emptyText) {
  if (!items || !items.length) {
    return `<div class="emptyState">${escapeHtml(emptyText)}</div>`;
  }
  return items.slice(-20).reverse().map((item) => {
    const title = item[titleKey] || item.task_id || item.status || "memory";
    const body = item.content || item.reason || item.final_output_preview || JSON.stringify(item);
    return `<article class="memoryCard"><strong>${escapeHtml(String(title))}</strong><small>${escapeHtml(String(body))}</small></article>`;
  }).join("");
}
```

- [ ] **Step 6：显示 replanned progress**

在 `eventLabel()` 的 mapping 增加：

```javascript
replanned: "Replan",
```

在 `eventSummary()` 增加：

```javascript
if (event.type === "replanned") return `从步骤 ${data.resume_step_id} 继续`;
```

`handleProgress()` 不需要复杂 UI，现有 log 会显示事件；如果 state JSON poll 正常，replan_events 会进入 state。

- [ ] **Step 7：添加 CSS**

在 `style.css` 增加：

```css
.memoryWorkspace {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  min-height: 0;
}

.memoryColumn {
  display: grid;
  gap: 12px;
  min-height: 0;
}

.memoryPanel {
  min-height: 0;
}

.memoryBlock {
  display: grid;
  gap: 8px;
  overflow: auto;
  min-height: 0;
}

.memoryCard {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px;
  display: grid;
  gap: 4px;
  background: var(--panel-soft);
}

.memoryCard strong,
.memoryCard small {
  min-width: 0;
  overflow-wrap: anywhere;
}
```

使用现有颜色变量；如果 `--panel-soft` 不存在，改用当前 CSS 已有的浅背景变量。

- [ ] **Step 8：绑定事件**

在事件绑定区增加：

```javascript
els.openMemory.addEventListener("click", showMemoryView);
els.refreshMemory.addEventListener("click", loadMemoryOverview);
```

- [ ] **Step 9：跑前端 tests**

运行：

```bash
.venv/bin/python -m pytest tests/test_desktop_frontend_assets.py -q
```

预期：

```text
pass
```

- [ ] **Step 10：提交前端记忆视图**

运行：

```bash
git add desktop/frontend/index.html desktop/frontend/app.js desktop/frontend/style.css tests/test_desktop_frontend_assets.py
git commit -m "feat: add desktop memory view"
```

---

## Task 6：桌面文档、打包与最终验证

**文件：**
- 修改： `desktop/README.md`
- 生成但不提交： `dist/UTA Desktop.app`
- 生成但不提交： `dist/UTA Desktop-macos.zip`

- [ ] **Step 1：更新 desktop README**

在 `desktop/README.md` 加：

```markdown
## 状态与记忆

桌面端可以查看实时任务状态、运行记录、历史 state/log，以及只读 JSON Memory。

- 短期记忆：当前任务或历史任务的 `state.json` 和 log。
- 长期记忆：`~/.uta/memory/*.json`，包括任务历史、经验、负向规则和 Skill 候选。
- 当前版本只读展示记忆，不支持编辑或删除。
```

- [ ] **Step 2：跑全量测试**

运行：

```bash
.venv/bin/python -m pytest -q
```

预期：

```text
all tests pass
```

- [ ] **Step 3：打包桌面端**

运行：

```bash
bash desktop/build/build_macos.sh
```

预期：

```text
构建完成：dist/UTA Desktop.app
压缩包：dist/UTA Desktop-macos.zip
```

- [ ] **Step 4：验证 zip**

运行：

```bash
unzip -t "dist/UTA Desktop-macos.zip"
```

预期：

```text
No errors detected in compressed data of dist/UTA Desktop-macos.zip.
```

- [ ] **Step 5：验证 codesign**

运行：

```bash
codesign --verify --deep --strict "dist/UTA Desktop.app"
```

预期：

```text
exit 0，无输出
```

- [ ] **Step 6：确认包内包含 memory view 前端资源**

运行：

```bash
rg -n "openMemory|get_memory_overview|memoryView|replanned" "dist/UTA Desktop.app/Contents/Resources/frontend"
```

预期：

```text
能搜到 openMemory、get_memory_overview、memoryView、replanned
```

- [ ] **Step 7：提交桌面 README**

运行：

```bash
git add desktop/README.md
git commit -m "docs: document desktop memory visibility"
```

注意：`dist/` 被 `.gitignore` 忽略，不提交打包产物。

---

## Task 7：最终状态汇报

**文件：**
- 不修改源码。

- [ ] **Step 1：确认 tag 和最新提交**

运行：

```bash
git tag --list v1.0-learning-agent
git log --oneline -5
git status -sb
```

预期：

```text
v1.0-learning-agent 存在
当前桌面分支有桌面记忆可视化提交
只有原本 memory/原型脏文件残留
```

- [ ] **Step 2：汇报给用户**

汇报必须包括：

- 核心 V1.0 tag 是否成功。
- 桌面端是否已重新打包。
- 新 `.app` 和 zip 路径。
- 测试结果。
- demo 结果。
- 哪些文件仍然是原本脏文件，没有被处理。

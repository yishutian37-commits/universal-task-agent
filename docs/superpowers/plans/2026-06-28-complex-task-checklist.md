# Complex Task Checklist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `complex_task` support so UTA can split complex user requests into checklist steps and show `[ ]/[x]` progress in both desktop execution and final output.

**Architecture:** Reuse the existing Planner and Agent Loop instead of adding a separate task engine. `TaskParser` identifies complex tasks, `Planner` splits the user input into `PlanStep` records, `core/loop.py` formats final checklist output, and the desktop frontend maps step events to checklist markers.

**Tech Stack:** Python dataclasses, pytest, existing UTA Planner/Loop/Router/Verifier, vanilla JavaScript/CSS desktop frontend.

---

### Task 1: Recognize `complex_task`

**Files:**
- Modify: `core/task_parser.py`
- Test: `tests/test_task_parser.py`

- [ ] **Step 1: Write failing parser tests**

Add tests like:

```python
def test_task_parser_fallback_detects_complex_task_when_user_requests_steps():
    parser = TaskParser(llm_client=FailingLLMClient())

    task = parser.parse("task_test", "请分步骤执行：先分析项目，再列出计划，最后总结风险")

    assert task.task_type == "complex_task"
    assert task.intent == "execute_complex_task"
    assert task.input_type == "text"
    assert task.expected_output == "step_checklist"


def test_task_parser_system_prompt_allows_complex_task():
    assert "complex_task" in TaskParser._system_prompt()
```

- [ ] **Step 2: Verify the tests fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_task_parser.py::test_task_parser_fallback_detects_complex_task_when_user_requests_steps tests/test_task_parser.py::test_task_parser_system_prompt_allows_complex_task -q
```

Expected: failure because `complex_task` is not allowed or detected.

- [ ] **Step 3: Implement parser support**

Update `ALLOWED_TASK_TYPES`, `_system_prompt()`, `_fallback_task()`, and `_guess_task_type()` with `complex_task`. Keep existing specialized task detection before complex detection.

- [ ] **Step 4: Verify parser tests pass**

Run the same pytest command. Expected: pass.

---

### Task 2: Split Complex Tasks Into Plan Steps

**Files:**
- Modify: `core/planner.py`
- Test: `tests/test_planner.py`

- [ ] **Step 1: Write failing planner tests**

Add tests like:

```python
def test_planner_splits_complex_task_numbered_brackets():
    task = Task(
        task_id="task_test",
        user_input="帮我执行复杂任务：[1]分析当前项目状态 [2]列出下一步计划 [3]总结风险点",
        task_type="complex_task",
        intent="execute_complex_task",
        input_type="text",
        expected_output="step_checklist",
    )

    plan = Planner().create_plan(task)

    assert [step.goal for step in plan.steps] == [
        "分析当前项目状态",
        "列出下一步计划",
        "总结风险点",
    ]


def test_planner_splits_complex_task_connectors():
    task = Task(
        task_id="task_test",
        user_input="请分步骤执行：先分析项目，然后列出计划，最后总结风险",
        task_type="complex_task",
        intent="execute_complex_task",
        input_type="text",
        expected_output="step_checklist",
    )

    plan = Planner().create_plan(task)

    assert [step.goal for step in plan.steps] == [
        "分析项目",
        "列出计划",
        "总结风险",
    ]
```

- [ ] **Step 2: Verify planner tests fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_planner.py::test_planner_splits_complex_task_numbered_brackets tests/test_planner.py::test_planner_splits_complex_task_connectors -q
```

Expected: failure because planner returns fallback mock goal.

- [ ] **Step 3: Implement split helpers**

Add helper methods in `Planner`:

```python
def _goals_for_task(self, task: Task) -> list[str]:
    if task.task_type == "complex_task":
        return self._complex_task_goals(task.user_input)
    return self._goals_for(task.task_type)
```

Use it from `create_plan()`. Add `_complex_task_goals`, `_numbered_goals`, `_connector_goals`, and `_clean_complex_goal`, clamping to 2-8 goals.

- [ ] **Step 4: Verify planner tests pass**

Run the same pytest command. Expected: pass.

---

### Task 3: Generate Checklist Final Output

**Files:**
- Modify: `core/loop.py`
- Test: `tests/test_loop.py` or `tests/test_main.py`

- [ ] **Step 1: Write failing loop/main test**

Add a test that runs a `complex_task` with mock tools and expects final output:

```python
def test_run_task_outputs_completed_checklist_for_complex_task(tmp_path):
    state = run_task(
        "帮我执行复杂任务：[1]分析当前项目状态 [2]列出下一步计划 [3]总结风险点",
        output_root=tmp_path,
        task_id="task_complex",
        task_parser=FakeParser(task_type="complex_task", intent="execute_complex_task"),
        tool_registry={"mock_tool": StaticSummaryTool("done")},
        memory_provider=False,
        skill_loader=False,
    )

    assert state.status == "completed"
    assert "## 复杂任务执行清单" in state.final_output
    assert "[x] 1. 分析当前项目状态" in state.final_output
    assert "[x] 2. 列出下一步计划" in state.final_output
    assert "[x] 3. 总结风险点" in state.final_output
```

- [ ] **Step 2: Verify the test fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_main.py::test_run_task_outputs_completed_checklist_for_complex_task -q
```

Expected: failure because final output is currently the last tool message.

- [ ] **Step 3: Implement checklist formatting**

In `core/loop.py`, add:

```python
def _checklist_marker(status: str) -> str:
    return {"completed": "[x]", "running": "[...]", "failed": "[!]"}.get(status, "[ ]")
```

Add `_complex_task_output(state)` and use it when `state.task_type == "complex_task"` before the default final output assignment.

- [ ] **Step 4: Verify checklist test passes**

Run the same pytest command. Expected: pass.

---

### Task 4: Desktop Checklist UI

**Files:**
- Modify: `desktop/frontend/app.js`
- Modify: `desktop/frontend/style.css`
- Test: `tests/test_desktop_frontend_assets.py` or `tests/test_desktop_frontend.py`

- [ ] **Step 1: Write failing frontend asset test**

Add assertions:

```python
def test_frontend_renders_step_checklist_markers():
    js = (ROOT / "desktop/frontend/app.js").read_text(encoding="utf-8")
    css = (ROOT / "desktop/frontend/style.css").read_text(encoding="utf-8")

    assert "stepMarkerFor" in js
    assert '"[ ]"' in js
    assert '"[x]"' in js
    assert '"[!]"' in js
    assert ".stepIcon" in css
    assert "border-radius: 6px" in css
```

- [ ] **Step 2: Verify frontend test fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_desktop_frontend_assets.py::test_frontend_renders_step_checklist_markers -q
```

Expected: failure because `stepMarkerFor` does not exist.

- [ ] **Step 3: Implement frontend marker mapping**

Add:

```javascript
function stepMarkerFor(kind) {
  if (kind === "done") return "[x]";
  if (kind === "failed") return "[!]";
  if (kind === "active") return "[...]";
  return "[ ]";
}
```

Use `[ ]` in `renderPlan()` and `stepMarkerFor(kind)` in `markStep()`.

- [ ] **Step 4: Update CSS**

Change `.stepIcon` from circular icon to compact monospace marker:

```css
.stepIcon {
  min-width: 42px;
  height: 24px;
  border-radius: 6px;
  font-family: var(--mono);
}
```

- [ ] **Step 5: Verify frontend test passes**

Run the same pytest command. Expected: pass.

---

### Task 5: Docs, Full Tests, Build

**Files:**
- Modify: `README.md`
- Modify: `docs/project-overview.md`
- Modify: `CHANGELOG.md`
- Build: `desktop/build/build_macos.sh`

- [ ] **Step 1: Update docs**

Add a complex task example:

```bash
.venv/bin/python main.py --task "帮我执行复杂任务：[1]分析当前项目状态 [2]列出下一步计划 [3]总结风险点"
```

- [ ] **Step 2: Run full tests**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 3: Run smoke**

Run:

```bash
.venv/bin/python main.py --task "帮我执行复杂任务：[1]分析当前项目状态 [2]列出下一步计划 [3]总结风险点" --output-root /private/tmp/uta-complex-smoke
```

Expected: output contains `## 复杂任务执行清单` and three `[x]` lines.

- [ ] **Step 4: Rebuild desktop app**

Run:

```bash
bash desktop/build/build_macos.sh
```

Expected: `dist/UTA Desktop.app` and `dist/UTA Desktop-macos.zip` are rebuilt.

- [ ] **Step 5: Verify app signature**

Run:

```bash
codesign --verify --deep --strict --verbose=2 "dist/UTA Desktop.app"
```

Expected: valid on disk and satisfies its Designated Requirement.

- [ ] **Step 6: Commit implementation**

Run:

```bash
git add README.md CHANGELOG.md docs/project-overview.md core/task_parser.py core/planner.py core/loop.py desktop/frontend/app.js desktop/frontend/style.css tests
git commit -m "feat: add complex task checklist execution"
```

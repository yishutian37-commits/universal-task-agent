# UTA V0.5 Verifier Reflection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete `v0.5-verifier-reflection` by adding structural verification for summary reports, rule-based reflection, and per-step retry.

**Architecture:** `Verifier` remains Python-rule based and gains task-aware checks. `Reflection` is a new small module that turns failed checks into `Feedback`. `run_minimal_loop()` keeps the existing plan execution shape but adds an inner retry loop and passes feedback into the next retry action.

**Tech Stack:** Python 3.12, dataclasses, pytest, existing `AgentState` / `ToolResult` / `CheckResult` / `Feedback`.

---

## File Structure

- Modify: `core/verifier.py`
- Create: `core/reflection.py`
- Modify: `core/loop.py`
- Modify: `tools/text_tool.py`
- Modify: `main.py`
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `tests/test_verifier.py`
- Create: `tests/test_reflection.py`
- Modify: `tests/test_loop.py`
- Modify: `tests/test_text_tool.py`
- Modify: `tests/test_main.py`

---

### Task 1: Verifier Summary Structure

**Files:**
- Modify: `core/verifier.py`
- Modify: `tests/test_verifier.py`

- [ ] **Step 1: Write failing summary verifier tests**

Add to `tests/test_verifier.py`:

```python
from core.state import AgentState, PlanStep


def test_verifier_passes_complete_summary_report():
    state = AgentState(task_id="task_test", user_input="帮我总结", task_type="summarize")
    step = PlanStep(step_id=3, goal="生成结构化报告")
    result = ToolResult(
        success=True,
        tool_name="report_tool",
        action_name="generate",
        result={
            "message": "## 摘要\n完成联调。\n## 核心观点\n流程清晰。\n## 风险点\n原文未提供明确风险。"
        },
    )

    check = Verifier().check(state, step, result)

    assert check.passed is True
    assert check.failed_reasons == []


def test_verifier_fails_summary_missing_risk_section():
    state = AgentState(task_id="task_test", user_input="帮我总结", task_type="summarize")
    step = PlanStep(step_id=3, goal="生成结构化报告")
    result = ToolResult(
        success=True,
        tool_name="report_tool",
        action_name="generate",
        result={"message": "## 摘要\n完成联调。\n## 核心观点\n流程清晰。"},
    )

    check = Verifier().check(state, step, result)

    assert check.passed is False
    assert "缺少必要小节：风险点" in check.failed_reasons
    assert "补齐风险点小节" in check.suggested_fix


def test_verifier_fails_summary_empty_section():
    state = AgentState(task_id="task_test", user_input="帮我总结", task_type="summarize")
    step = PlanStep(step_id=3, goal="生成结构化报告")
    result = ToolResult(
        success=True,
        tool_name="report_tool",
        action_name="generate",
        result={"message": "## 摘要\n\n## 核心观点\n流程清晰。\n## 风险点\n原文未提供明确风险。"},
    )

    check = Verifier().check(state, step, result)

    assert check.passed is False
    assert "小节内容为空：摘要" in check.failed_reasons
    assert "补充摘要小节内容" in check.suggested_fix
```

- [ ] **Step 2: Run red tests**

```bash
.venv/bin/python -m pytest tests/test_verifier.py::test_verifier_passes_complete_summary_report tests/test_verifier.py::test_verifier_fails_summary_missing_risk_section tests/test_verifier.py::test_verifier_fails_summary_empty_section -v
```

Expected: FAIL because `Verifier.check()` does not accept `(state, step, result)` and does not inspect sections.

- [ ] **Step 3: Implement summary structure verification**

Update `core/verifier.py` with:

```python
import re

from core.state import AgentState, CheckResult, PlanStep, ToolResult


SUMMARY_REQUIRED_SECTIONS = ["摘要", "核心观点", "风险点"]


class Verifier:
    def check(self, *args) -> CheckResult:
        if len(args) == 1:
            state = None
            step = None
            result = args[0]
        elif len(args) == 3:
            state, step, result = args
        else:
            raise TypeError("Verifier.check expects result or state, step, result")

        if not result.success:
            return self._failed_tool_check(result)

        if self._should_check_summary(state, result):
            return self._check_summary(result)

        return CheckResult(passed=True, failed_reasons=[], suggested_fix=[])

    def _failed_tool_check(self, result: ToolResult) -> CheckResult:
        error = result.error or "unknown error"
        return CheckResult(
            passed=False,
            failed_reasons=[f"工具执行失败：{error}"],
            suggested_fix=["检查工具名称或工具实现"],
        )

    def _should_check_summary(self, state: AgentState | None, result: ToolResult) -> bool:
        return (
            state is not None
            and state.task_type == "summarize"
            and result.tool_name == "report_tool"
        )

    def _check_summary(self, result: ToolResult) -> CheckResult:
        report_text = str(result.result.get("message") or result.result.get("report_markdown") or "")
        failed_reasons = []
        suggested_fix = []
        for section in SUMMARY_REQUIRED_SECTIONS:
            content = self._section_content(report_text, section)
            if content is None:
                failed_reasons.append(f"缺少必要小节：{section}")
                suggested_fix.append(f"补齐{section}小节")
            elif not content.strip():
                failed_reasons.append(f"小节内容为空：{section}")
                suggested_fix.append(f"补充{section}小节内容")
        return CheckResult(
            passed=not failed_reasons,
            failed_reasons=failed_reasons,
            suggested_fix=suggested_fix,
        )

    def _section_content(self, report_text: str, section: str) -> str | None:
        pattern = re.compile(
            rf"(?:^|\n)\s*(?:#+\s*)?{re.escape(section)}\s*[：:]?\s*\n?(.*?)(?=\n\s*(?:#+\s*)?(?:摘要|核心观点|风险点|关键事实|待办事项)\s*[：:]?\s*\n?|\Z)",
            re.DOTALL,
        )
        match = pattern.search(report_text)
        if not match:
            return None
        return match.group(1).strip()
```

- [ ] **Step 4: Run green verifier tests**

```bash
.venv/bin/python -m pytest tests/test_verifier.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/verifier.py tests/test_verifier.py
git commit -m "feat: verify summary report structure"
```

---

### Task 2: Verifier L1 Table Number Rule

**Files:**
- Modify: `core/verifier.py`
- Modify: `tests/test_verifier.py`

- [ ] **Step 1: Write failing table number tests**

Add to `tests/test_verifier.py`:

```python
def test_verifier_passes_matching_table_numbers():
    check = Verifier().check_table_numbers(
        "基础统计：行数 10，列数 3，缺失值数量 2，异常值数量 0。",
        {"row_count": 10, "column_count": 3, "missing_count": 2, "anomaly_count": 0},
    )

    assert check.passed is True


def test_verifier_fails_mismatched_table_numbers():
    check = Verifier().check_table_numbers(
        "基础统计：行数 9，列数 3，缺失值数量 2，异常值数量 0。",
        {"row_count": 10, "column_count": 3, "missing_count": 2, "anomaly_count": 0},
    )

    assert check.passed is False
    assert "行数不一致：报告=9，工具=10" in check.failed_reasons
```

- [ ] **Step 2: Run red tests**

```bash
.venv/bin/python -m pytest tests/test_verifier.py::test_verifier_passes_matching_table_numbers tests/test_verifier.py::test_verifier_fails_mismatched_table_numbers -v
```

Expected: FAIL because `check_table_numbers()` does not exist.

- [ ] **Step 3: Implement table number helper**

Add to `Verifier`:

```python
    def check_table_numbers(self, report_text: str, table_stats: dict) -> CheckResult:
        mapping = [
            ("row_count", "行数"),
            ("column_count", "列数"),
            ("missing_count", "缺失值数量"),
            ("anomaly_count", "异常值数量"),
        ]
        failed_reasons = []
        suggested_fix = []
        for key, label in mapping:
            expected = table_stats.get(key)
            actual = self._extract_labeled_number(report_text, label)
            if actual is None:
                failed_reasons.append(f"报告缺少数字：{label}")
                suggested_fix.append(f"补充{label}")
            elif actual != expected:
                failed_reasons.append(f"{label}不一致：报告={actual}，工具={expected}")
                suggested_fix.append(f"把{label}改为 {expected}")
        return CheckResult(
            passed=not failed_reasons,
            failed_reasons=failed_reasons,
            suggested_fix=suggested_fix,
        )

    def _extract_labeled_number(self, text: str, label: str) -> int | None:
        match = re.search(rf"{re.escape(label)}\s*[：:]?\s*(\d+)", text)
        if not match:
            return None
        return int(match.group(1))
```

- [ ] **Step 4: Run green verifier tests**

```bash
.venv/bin/python -m pytest tests/test_verifier.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/verifier.py tests/test_verifier.py
git commit -m "feat: add table number verifier rule"
```

---

### Task 3: Reflection

**Files:**
- Create: `core/reflection.py`
- Create: `tests/test_reflection.py`

- [ ] **Step 1: Write failing reflection tests**

Create `tests/test_reflection.py`:

```python
from core.reflection import Reflection
from core.state import AgentState, CheckResult, PlanStep, ToolResult


def test_reflection_classifies_incomplete_output():
    state = AgentState(task_id="task_test", user_input="帮我总结", task_type="summarize")
    step = PlanStep(step_id=3, goal="生成结构化报告")
    result = ToolResult(True, "report_tool", "generate", {"message": "## 摘要\n完成联调。"})
    check = CheckResult(
        passed=False,
        failed_reasons=["缺少必要小节：风险点"],
        suggested_fix=["补齐风险点小节"],
    )

    feedback = Reflection().analyze(state, step, result, check)

    assert feedback.failure_type == "incomplete_output"
    assert feedback.root_cause == "缺少必要小节：风险点"
    assert feedback.repair_strategy == "补齐风险点小节"
    assert feedback.need_replan is False
    assert feedback.need_user_input is False


def test_reflection_classifies_tool_error():
    state = AgentState(task_id="task_test", user_input="帮我总结", task_type="summarize")
    step = PlanStep(step_id=2, goal="提取核心信息")
    result = ToolResult(False, "text_tool", "process", {}, error="tool_error: boom")
    check = CheckResult(
        passed=False,
        failed_reasons=["工具执行失败：tool_error: boom"],
        suggested_fix=["检查工具名称或工具实现"],
    )

    feedback = Reflection().analyze(state, step, result, check)

    assert feedback.failure_type == "tool_error"
    assert "tool_error: boom" in feedback.root_cause
```

- [ ] **Step 2: Run red tests**

```bash
.venv/bin/python -m pytest tests/test_reflection.py -v
```

Expected: FAIL because `core.reflection` does not exist.

- [ ] **Step 3: Implement Reflection**

Create `core/reflection.py`:

```python
from core.state import AgentState, CheckResult, Feedback, PlanStep, ToolResult


class Reflection:
    def analyze(
        self,
        state: AgentState,
        step: PlanStep,
        result: ToolResult,
        check: CheckResult,
    ) -> Feedback:
        del state, step
        root_cause = "；".join(check.failed_reasons) or result.error or "未知失败"
        repair_strategy = "；".join(check.suggested_fix) or "重新执行当前步骤"
        return Feedback(
            failure_type=self._failure_type(result, check),
            root_cause=root_cause,
            repair_strategy=repair_strategy,
            need_replan=False,
            need_user_input=False,
        )

    def _failure_type(self, result: ToolResult, check: CheckResult) -> str:
        if not result.success:
            return "tool_error"
        joined = "；".join(check.failed_reasons)
        if "缺少必要小节" in joined or "小节内容为空" in joined:
            return "incomplete_output"
        if "不一致" in joined:
            return "violated_constraint"
        return "format_error"
```

- [ ] **Step 4: Run green tests**

```bash
.venv/bin/python -m pytest tests/test_reflection.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/reflection.py tests/test_reflection.py
git commit -m "feat: add reflection feedback"
```

---

### Task 4: Loop Retry

**Files:**
- Modify: `core/loop.py`
- Modify: `tests/test_loop.py`

- [ ] **Step 1: Write failing retry success test**

Add to `tests/test_loop.py`:

```python
class SequenceReportTool(BaseTool):
    name = "sequence_report_tool"
    description = "test report sequence"

    def __init__(self, messages):
        self.messages = list(messages)
        self.params_seen = []

    def run(self, action_name, params):
        self.params_seen.append(params)
        return {"message": self.messages.pop(0), "report_markdown": self.params_seen[-1].get("message", "")}


def test_loop_retries_failed_report_step_and_then_completes():
    report_tool = SequenceReportTool(
        [
            "## 摘要\n完成联调。\n## 核心观点\n流程清晰。",
            "## 摘要\n完成联调。\n## 核心观点\n流程清晰。\n## 风险点\n原文未提供明确风险。",
        ]
    )
    registry = {
        "file_tool": EchoTool("file"),
        "text_tool": EchoTool("text"),
        "report_tool": report_tool,
    }
    state = AgentState(
        task_id="task_test",
        user_input="帮我总结",
        task_type="summarize",
        intent="summarize_article",
    )

    updated = run_minimal_loop(state, tool_registry=registry)

    assert updated.status == "completed"
    assert len(updated.feedbacks) == 1
    assert updated.feedbacks[0].failure_type == "incomplete_output"
    assert report_tool.params_seen[1]["feedback"].failure_type == "incomplete_output"
```

- [ ] **Step 2: Write failing retry exhausted test**

Add to `tests/test_loop.py`:

```python
def test_loop_fails_after_report_step_retries_are_exhausted():
    report_tool = SequenceReportTool(
        [
            "## 摘要\n完成联调。",
            "## 摘要\n完成联调。",
            "## 摘要\n完成联调。",
        ]
    )
    registry = {
        "file_tool": EchoTool("file"),
        "text_tool": EchoTool("text"),
        "report_tool": report_tool,
    }
    state = AgentState(
        task_id="task_test",
        user_input="帮我总结",
        task_type="summarize",
        intent="summarize_article",
    )

    updated = run_minimal_loop(state, tool_registry=registry)

    assert updated.status == "failed"
    assert updated.plan.status == "failed"
    assert len(updated.feedbacks) == 3
    assert "缺少必要小节：核心观点" in updated.final_output
```

- [ ] **Step 3: Run red loop tests**

```bash
.venv/bin/python -m pytest tests/test_loop.py::test_loop_retries_failed_report_step_and_then_completes tests/test_loop.py::test_loop_fails_after_report_step_retries_are_exhausted -v
```

Expected: FAIL because loop does not retry and does not attach feedback.

- [ ] **Step 4: Implement loop retry**

Update `core/loop.py`:

```python
from core.reflection import Reflection

# Inside run_minimal_loop(), after verifier is created:
reflection = Reflection()

# Replace the old single-attempt step execution block with:
for step in state.plan.steps:
    feedback = None
    attempt = 0
    while attempt <= step.max_retries:
        state.current_step_id = step.step_id
        step.status = "running"
        action = router.choose_tool(state, step)
        if feedback is not None:
            action.params["feedback"] = feedback
        state.current_action = action
        result = executor.run(action)
        state.results.append(result)
        check = verifier.check(state, step, result)
        state.checks.append(check)
        if check.passed:
            step.status = "completed"
            break
        feedback = reflection.analyze(state, step, result, check)
        state.feedbacks.append(feedback)
        attempt += 1
    if step.status != "completed":
        step.status = "failed"
        state.plan.status = "failed"
        state.status = "failed"
        state.final_output = "；".join(state.checks[-1].failed_reasons)
        state.touch()
        return state
```

- [ ] **Step 5: Run green loop tests**

```bash
.venv/bin/python -m pytest tests/test_loop.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add core/loop.py tests/test_loop.py
git commit -m "feat: retry failed steps with reflection"
```

---

### Task 5: TextTool Feedback Prompt

**Files:**
- Modify: `tools/text_tool.py`
- Modify: `tests/test_text_tool.py`

- [ ] **Step 1: Write failing TextTool feedback test**

Add to `tests/test_text_tool.py`:

```python
from core.state import Feedback


def test_text_tool_includes_feedback_in_retry_prompt():
    client = FakeLLMClient()
    feedback = Feedback(
        failure_type="incomplete_output",
        root_cause="缺少必要小节：风险点",
        repair_strategy="补齐风险点小节",
    )

    TextTool(llm_client=client).run(
        "process",
        {
            "user_input": "帮我总结",
            "previous_result": {"content": "会议记录：库存接口已完成联调。"},
            "feedback": feedback,
        },
    )

    assert "上一次输出未通过校验" in client.calls[0][1]
    assert "补齐风险点小节" in client.calls[0][1]
```

- [ ] **Step 2: Run red test**

```bash
.venv/bin/python -m pytest tests/test_text_tool.py::test_text_tool_includes_feedback_in_retry_prompt -v
```

Expected: FAIL because prompt does not include feedback yet.

- [ ] **Step 3: Implement feedback prompt**

Update `tools/text_tool.py`:

```python
    def run(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        del action_name
        source_text = self._source_text(params)
        if not source_text.strip():
            raise ValueError("没有可总结的文本")

        summary = self.llm_client.chat(
            self._system_prompt(),
            self._user_prompt(source_text, params.get("feedback")),
        ).strip()
        if not summary:
            raise ValueError("LLM 返回空总结")

        return {
            "message": summary,
            "summary_markdown": summary,
            "source_text": source_text,
        }

    @staticmethod
    def _user_prompt(source_text: str, feedback=None) -> str:
        feedback_text = ""
        if feedback is not None:
            feedback_text = (
                "\n\n上一次输出未通过校验，请按以下修复建议重新生成：\n"
                f"- {feedback.repair_strategy}\n"
            )
        return (
            "请总结下面文本，输出固定结构：\n"
            "## 摘要\n"
            "## 核心观点\n"
            "## 关键事实\n"
            "## 待办事项\n"
            "## 风险点\n"
            f"{feedback_text}\n"
            f"原文：\n{source_text}"
        )
```

- [ ] **Step 4: Run green TextTool tests**

```bash
.venv/bin/python -m pytest tests/test_text_tool.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/text_tool.py tests/test_text_tool.py
git commit -m "feat: include reflection feedback in summary prompt"
```

---

### Task 6: Logs and Docs

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main.py`
- Modify: `README.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Write failing log test**

Add to `tests/test_main.py`:

```python
from core.state import Feedback


def test_log_lines_include_reflection_feedback():
    state = create_initial_state("task_test", "帮我总结")
    state.feedbacks.append(
        Feedback(
            failure_type="incomplete_output",
            root_cause="缺少必要小节：风险点",
            repair_strategy="补齐风险点小节",
        )
    )

    log_text = "\n".join(build_log_lines(state))

    assert "[Reflection] failure_type = incomplete_output" in log_text
    assert "[Reflection] repair_strategy = 补齐风险点小节" in log_text
```

Also import `build_log_lines` from `main`.

- [ ] **Step 2: Run red main test**

```bash
.venv/bin/python -m pytest tests/test_main.py::test_log_lines_include_reflection_feedback -v
```

Expected: FAIL because reflection lines are not logged.

- [ ] **Step 3: Implement reflection log lines**

Update `main.py` inside `build_log_lines()` before result/status:

```python
    for feedback in state.feedbacks:
        lines.append(f"[Reflection] failure_type = {feedback.failure_type}")
        lines.append(f"[Reflection] repair_strategy = {feedback.repair_strategy}")
```

- [ ] **Step 4: Update docs**

README current status:

```markdown
- `v0.5-verifier-reflection`: `Verifier` 做总结结构硬校验，`Reflection` 分类失败并驱动单步重试。
```

CHANGELOG:

```markdown
- Add `v0.5-verifier-reflection` with summary verification and reflection retry.
```

- [ ] **Step 5: Run green main tests**

```bash
.venv/bin/python -m pytest tests/test_main.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_main.py README.md CHANGELOG.md
git commit -m "docs: document verifier reflection flow"
```

---

### Task 7: Verification and Tag

**Files:**
- No source changes expected.

- [ ] **Step 1: Run full tests**

```bash
.venv/bin/python -m pytest -v
```

Expected: all tests PASS.

- [ ] **Step 2: Run real CLI smoke test**

```bash
LLM_SSL_VERIFY=0 .venv/bin/python main.py --task "帮我总结 examples/summarize_example.txt"
```

Expected: command exits 0 and prints `任务已完成：` followed by Markdown summary text.

- [ ] **Step 3: Check status and secrets**

```bash
git status --short
git grep -n -E 'tp-[[:alnum:]]{20,}'
```

Expected: clean status and no tracked key. `git grep` exits 1 when no matches exist.

- [ ] **Step 4: Tag**

```bash
git tag v0.5-verifier-reflection
git tag --list "v0.5-verifier-reflection"
```

Expected:

```text
v0.5-verifier-reflection
```

---

## Self-Review

- Spec coverage: covers summary structural verification, Reflection, retry, feedback prompt, logs, docs, table number rule interface, tests, tag.
- Scope check: excludes full replan, real table analysis, semantic LLM verifier, Memory, Skill, TAM.
- Type consistency: uses existing `AgentState`, `PlanStep`, `ToolResult`, `CheckResult`, `Feedback`, `BaseTool.run()`, and `run_minimal_loop()`.

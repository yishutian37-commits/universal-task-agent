# UTA V0.4 Summary Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `v0.4-summary-demo` so summary tasks produce a real Chinese Markdown summary instead of `mock result`.

**Architecture:** Keep the v0.3 `Planner -> Router -> Executor -> Verifier` loop. Add a thin result-passing contract through `Action.params["previous_result"]`, then replace the v0.3 placeholders with `FileTool`, `TextTool`, and `ReportTool` for the summary path.

**Tech Stack:** Python 3.12, dataclasses, existing `LLMClient`, pytest.

---

## File Structure

- Modify: `core/router.py` — include `previous_result` in action params.
- Modify: `core/loop.py` — accept optional `tool_registry` for tests and controlled execution.
- Create: `tools/file_tool.py` — read `.txt` / `.md` files or fall back to inline user input.
- Create: `tools/text_tool.py` — call `LLMClient` to produce Chinese Markdown summaries.
- Create: `tools/report_tool.py` — turn the summary into the final report/message.
- Modify: `tools/registry.py` — register the real v0.4 summary tools.
- Create: `tests/test_file_tool.py`
- Create: `tests/test_text_tool.py`
- Create: `tests/test_report_tool.py`
- Modify: `tests/test_router.py`
- Modify: `tests/test_loop.py`
- Modify: `tests/test_main.py`
- Modify: `README.md`
- Modify: `CHANGELOG.md`

---

### Task 1: Pass Previous Result Between Steps

**Files:**
- Modify: `core/router.py`
- Modify: `core/loop.py`
- Modify: `tests/test_router.py`
- Modify: `tests/test_loop.py`

- [ ] **Step 1: Write failing Router test**

Add to `tests/test_router.py`:

```python
from core.state import ToolResult


def test_router_passes_previous_tool_result_to_next_action():
    state = AgentState(task_id="task_test", user_input="测试")
    state.results.append(
        ToolResult(
            success=True,
            tool_name="file_tool",
            action_name="read",
            result={"content": "上一段文本"},
        )
    )

    action = Router().choose_tool(state, PlanStep(step_id=2, goal="提取核心信息"))

    assert action.params["previous_result"] == {"content": "上一段文本"}
```

- [ ] **Step 2: Run red test**

```bash
.venv/bin/python -m pytest tests/test_router.py::test_router_passes_previous_tool_result_to_next_action -v
```

Expected: FAIL with `KeyError: 'previous_result'`.

- [ ] **Step 3: Implement Router param**

In `core/router.py`, change `_action()` params:

```python
previous_result = state.results[-1].result if state.results else None
return Action(
    action_id=f"action_{state.task_id}_{step.step_id}",
    step_id=step.step_id,
    tool_name=tool_name,
    action_name=action_name,
    params={
        "user_input": state.user_input,
        "goal": step.goal,
        "previous_result": previous_result,
    },
    reason=reason,
)
```

- [ ] **Step 4: Write failing loop injection test**

Add to `tests/test_loop.py`:

```python
from tools.base_tool import BaseTool


def test_loop_accepts_injected_tool_registry_for_summary_flow():
    class EchoTool(BaseTool):
        name = "echo_tool"
        description = "test tool"

        def __init__(self, message):
            self.message = message

        def run(self, action_name, params):
            return {"message": self.message, "previous_result": params.get("previous_result")}

    state = AgentState(
        task_id="task_test",
        user_input="帮我总结",
        task_type="summarize",
        intent="summarize_article",
    )
    registry = {
        "file_tool": EchoTool("file"),
        "text_tool": EchoTool("text"),
        "report_tool": EchoTool("report"),
    }

    updated = run_minimal_loop(state, tool_registry=registry)

    assert updated.final_output == "report"
    assert updated.results[1].result["previous_result"]["message"] == "file"
    assert updated.results[2].result["previous_result"]["message"] == "text"
```

- [ ] **Step 5: Run red loop test**

```bash
.venv/bin/python -m pytest tests/test_loop.py::test_loop_accepts_injected_tool_registry_for_summary_flow -v
```

Expected: FAIL because `run_minimal_loop()` does not accept `tool_registry`.

- [ ] **Step 6: Implement loop injection**

Change `core/loop.py`:

```python
def run_minimal_loop(state: AgentState, tool_registry=None) -> AgentState:
    planner = Planner()
    router = Router()
    executor = Executor(tool_registry)
    verifier = Verifier()
```

- [ ] **Step 7: Run green tests**

```bash
.venv/bin/python -m pytest tests/test_router.py tests/test_loop.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add core/router.py core/loop.py tests/test_router.py tests/test_loop.py
git commit -m "feat: pass previous tool results"
```

---

### Task 2: FileTool

**Files:**
- Create: `tools/file_tool.py`
- Create: `tests/test_file_tool.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_file_tool.py`:

```python
from tools.file_tool import FileTool


def test_file_tool_reads_text_file_from_task(tmp_path):
    source = tmp_path / "meeting.txt"
    source.write_text("会议记录：上线前检查库存接口。", encoding="utf-8")

    result = FileTool().run("read", {"user_input": f"帮我总结 {source}"})

    assert result["content"] == "会议记录：上线前检查库存接口。"
    assert result["source_type"] == "file"
    assert result["source"] == str(source)
    assert result["message"] == "已读取文本内容"


def test_file_tool_uses_user_input_when_no_existing_path():
    result = FileTool().run("read", {"user_input": "帮我总结：今天完成了接口联调。"})

    assert result["content"] == "帮我总结：今天完成了接口联调。"
    assert result["source_type"] == "inline"
    assert result["source"] == "user_input"
```

- [ ] **Step 2: Run red tests**

```bash
.venv/bin/python -m pytest tests/test_file_tool.py -v
```

Expected: FAIL because `tools.file_tool` does not exist.

- [ ] **Step 3: Implement FileTool**

Create `tools/file_tool.py`:

```python
from pathlib import Path
import re
from typing import Any

from tools.base_tool import BaseTool


class FileTool(BaseTool):
    name = "file_tool"
    description = "Read local .txt or .md text for summary tasks."

    def run(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        del action_name
        user_input = str(params.get("user_input", ""))
        file_path = self._find_existing_text_path(user_input)
        if file_path is None:
            return {
                "message": "已读取文本内容",
                "content": user_input,
                "source_type": "inline",
                "source": "user_input",
            }

        content = file_path.read_text(encoding="utf-8")
        return {
            "message": "已读取文本内容",
            "content": content,
            "source_type": "file",
            "source": str(file_path),
        }

    def _find_existing_text_path(self, text: str) -> Path | None:
        for token in re.findall(r"[^\s，。！？；：、\"'“”‘’]+", text):
            if not token.endswith((".txt", ".md")):
                continue
            path = Path(token).expanduser()
            if path.exists() and path.is_file():
                return path
        return None
```

- [ ] **Step 4: Run green tests**

```bash
.venv/bin/python -m pytest tests/test_file_tool.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/file_tool.py tests/test_file_tool.py
git commit -m "feat: add file tool"
```

---

### Task 3: TextTool

**Files:**
- Create: `tools/text_tool.py`
- Create: `tests/test_text_tool.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_text_tool.py`:

```python
import pytest

from tools.text_tool import TextTool


class FakeLLMClient:
    def __init__(self, response="## 摘要\n库存接口已完成联调。"):
        self.response = response
        self.calls = []

    def chat(self, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        return self.response


def test_text_tool_summarizes_previous_content_with_llm():
    client = FakeLLMClient()
    result = TextTool(llm_client=client).run(
        "process",
        {
            "user_input": "帮我总结",
            "previous_result": {"content": "会议记录：库存接口已完成联调。"},
        },
    )

    assert result["summary_markdown"] == "## 摘要\n库存接口已完成联调。"
    assert result["message"] == "## 摘要\n库存接口已完成联调。"
    assert "会议记录：库存接口已完成联调。" in client.calls[0][1]


def test_text_tool_rejects_empty_text():
    with pytest.raises(ValueError, match="没有可总结的文本"):
        TextTool(llm_client=FakeLLMClient()).run(
            "process",
            {"user_input": "", "previous_result": {"content": ""}},
        )
```

- [ ] **Step 2: Run red tests**

```bash
.venv/bin/python -m pytest tests/test_text_tool.py -v
```

Expected: FAIL because `tools.text_tool` does not exist.

- [ ] **Step 3: Implement TextTool**

Create `tools/text_tool.py`:

```python
from typing import Any

from llm.llm_client import LLMClient
from tools.base_tool import BaseTool


class TextTool(BaseTool):
    name = "text_tool"
    description = "Summarize text with the configured LLM."

    def __init__(self, llm_client=None):
        self.llm_client = llm_client if llm_client is not None else LLMClient.from_config()

    def run(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        del action_name
        source_text = self._source_text(params)
        if not source_text.strip():
            raise ValueError("没有可总结的文本")

        summary = self.llm_client.chat(
            self._system_prompt(),
            self._user_prompt(source_text),
        ).strip()
        if not summary:
            raise ValueError("LLM 返回空总结")

        return {
            "message": summary,
            "summary_markdown": summary,
            "source_text": source_text,
        }

    def _source_text(self, params: dict[str, Any]) -> str:
        previous = params.get("previous_result")
        if isinstance(previous, dict) and isinstance(previous.get("content"), str):
            return previous["content"]
        return str(params.get("user_input", ""))

    @staticmethod
    def _system_prompt() -> str:
        return (
            "你是 UTA 的文本总结工具。只输出中文 Markdown，不要编造原文没有的信息。"
            "如果某类信息没有出现，写“未提及”。"
        )

    @staticmethod
    def _user_prompt(source_text: str) -> str:
        return (
            "请总结下面文本，输出固定结构：\n"
            "## 摘要\n"
            "## 核心观点\n"
            "## 关键事实\n"
            "## 待办事项\n"
            "## 风险点\n\n"
            f"原文：\n{source_text}"
        )
```

- [ ] **Step 4: Run green tests**

```bash
.venv/bin/python -m pytest tests/test_text_tool.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/text_tool.py tests/test_text_tool.py
git commit -m "feat: add text summary tool"
```

---

### Task 4: ReportTool and Registry

**Files:**
- Create: `tools/report_tool.py`
- Modify: `tools/registry.py`
- Create: `tests/test_report_tool.py`
- Modify: `tests/test_mock_tool.py`

- [ ] **Step 1: Write failing ReportTool tests**

Create `tests/test_report_tool.py`:

```python
from tools.report_tool import ReportTool


def test_report_tool_uses_summary_markdown_as_final_message():
    result = ReportTool().run(
        "generate",
        {"previous_result": {"summary_markdown": "## 摘要\n库存接口已完成联调。"}},
    )

    assert result["message"] == "## 摘要\n库存接口已完成联调。"
    assert result["report_markdown"] == "## 摘要\n库存接口已完成联调。"


def test_report_tool_returns_clear_message_without_summary():
    result = ReportTool().run("generate", {"previous_result": {}})

    assert result["message"] == "未生成总结报告"
    assert result["report_markdown"] == "未生成总结报告"
```

- [ ] **Step 2: Update registry test**

In `tests/test_mock_tool.py`, change `test_registry_contains_v0_3_placeholder_tools()` to:

```python
def test_registry_contains_summary_demo_tools():
    for name in ["file_tool", "text_tool", "report_tool"]:
        assert name in TOOL_REGISTRY
        assert TOOL_REGISTRY[name].name == name
    assert "table_tool" in TOOL_REGISTRY
```

- [ ] **Step 3: Run red tests**

```bash
.venv/bin/python -m pytest tests/test_report_tool.py tests/test_mock_tool.py -v
```

Expected: FAIL because `tools.report_tool` does not exist and registry still uses placeholder tools.

- [ ] **Step 4: Implement ReportTool**

Create `tools/report_tool.py`:

```python
from typing import Any

from tools.base_tool import BaseTool


class ReportTool(BaseTool):
    name = "report_tool"
    description = "Return the final Markdown report for summary tasks."

    def run(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        del action_name
        previous = params.get("previous_result")
        summary = ""
        if isinstance(previous, dict) and isinstance(previous.get("summary_markdown"), str):
            summary = previous["summary_markdown"].strip()
        if not summary:
            summary = "未生成总结报告"
        return {
            "message": summary,
            "report_markdown": summary,
        }
```

- [ ] **Step 5: Register real summary tools**

Update `tools/registry.py`:

```python
from tools.file_tool import FileTool
from tools.mock_tool import MockTool
from tools.placeholder_tool import PlaceholderTool
from tools.report_tool import ReportTool
from tools.text_tool import TextTool


TOOL_REGISTRY = {
    "mock_tool": MockTool(),
    "file_tool": FileTool(),
    "text_tool": TextTool(),
    "table_tool": PlaceholderTool(
        name="table_tool",
        description="V0.3 placeholder for table analysis steps.",
    ),
    "report_tool": ReportTool(),
}
```

- [ ] **Step 6: Run green tests**

```bash
.venv/bin/python -m pytest tests/test_report_tool.py tests/test_mock_tool.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add tools/report_tool.py tools/registry.py tests/test_report_tool.py tests/test_mock_tool.py
git commit -m "feat: add report tool"
```

---

### Task 5: CLI Integration and Docs

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main.py`
- Modify: `README.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Write failing main test**

Add to `tests/test_main.py`:

```python
from tools.base_tool import BaseTool


class StaticSummaryTool(BaseTool):
    name = "static_summary_tool"
    description = "test tool"

    def __init__(self, message):
        self.message = message

    def run(self, action_name, params):
        if action_name == "read":
            return {"message": "已读取文本内容", "content": "会议记录：库存接口已完成联调。"}
        if action_name == "process":
            return {"message": self.message, "summary_markdown": self.message}
        return {"message": self.message, "report_markdown": self.message}


def make_static_summary_registry(summary="## 摘要\n库存接口已完成联调。"):
    return {
        "file_tool": StaticSummaryTool("file"),
        "text_tool": StaticSummaryTool(summary),
        "report_tool": StaticSummaryTool(summary),
    }


def test_run_task_outputs_real_summary_with_injected_tools(tmp_path):
    summary = "## 摘要\n库存接口已完成联调。"

    state = run_task(
        "帮我总结一段文本",
        output_root=tmp_path,
        task_id="task_test",
        task_parser=FakeParser(),
        tool_registry=make_static_summary_registry(summary),
    )

    assert state.status == "completed"
    assert state.final_output == summary
```

- [ ] **Step 2: Run red test**

```bash
.venv/bin/python -m pytest tests/test_main.py::test_run_task_outputs_real_summary_with_injected_tools -v
```

Expected: FAIL because `run_task()` does not accept `tool_registry`.

- [ ] **Step 3: Implement main injection**

Change `main.py`:

```python
def run_task(
    task: str,
    output_root: Path | str = "outputs",
    task_id: str | None = None,
    task_parser=None,
    tool_registry=None,
) -> AgentState:
    ...
    state = run_minimal_loop(state, tool_registry=tool_registry)
```

- [ ] **Step 4: Update old main test to avoid real network**

Change `test_run_task_writes_state_and_log()` to pass:

```python
tool_registry=make_static_summary_registry("mock result"),
```

This keeps the existing `mock result` assertion deterministic without calling the real LLM.

- [ ] **Step 5: Update README and CHANGELOG**

README current status:

```markdown
- `v0.4-summary-demo`: `file_tool` 读取文本，`text_tool` 调 LLM 生成中文结构化总结，`report_tool` 输出 Markdown 报告。
```

CHANGELOG:

```markdown
- Add `v0.4-summary-demo` with real summary tools.
```

- [ ] **Step 6: Run green tests**

```bash
.venv/bin/python -m pytest tests/test_main.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add main.py tests/test_main.py README.md CHANGELOG.md
git commit -m "feat: connect summary demo to cli"
```

---

### Task 6: Verification and Tag

**Files:**
- No source changes expected.

- [ ] **Step 1: Run full tests**

```bash
.venv/bin/python -m pytest -v
```

Expected: all tests PASS.

- [ ] **Step 2: Run offline CLI smoke test with injected tests only**

The automated suite covers the non-network path. The manual CLI path may call the real configured LLM, so run it only after confirming `.env` exists locally:

```bash
.venv/bin/python main.py --task "帮我总结 examples/summarize_example.txt"
```

Expected with valid local `.env`: output starts with `任务已完成：` and contains Markdown summary text.

- [ ] **Step 3: Check worktree and secrets**

```bash
git status --short
git grep -n -E 'tp-[[:alnum:]]{20,}'
```

Expected: clean status and no tracked key. `git grep` exits 1 when there are no matches.

- [ ] **Step 4: Tag**

```bash
git tag v0.4-summary-demo
git tag --list "v0.4-summary-demo"
```

Expected:

```text
v0.4-summary-demo
```

---

## Self-Review

- Spec coverage: covers result passing, FileTool, TextTool, ReportTool, registry, CLI integration, docs, tests, verification, tag.
- Scope check: excludes Reflection, retry, replan, v0.5 verifier, CSV/Excel, Memory, Skill, TAM.
- Type consistency: uses existing `Action.params`, `ToolResult.result`, `AgentState.results`, `run_minimal_loop()`, `run_task()`, `BaseTool.run()`.

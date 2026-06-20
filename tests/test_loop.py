from core.loop import run_minimal_loop
from core.state import AgentState
from tools.base_tool import BaseTool


class EchoTool(BaseTool):
    name = "echo_tool"
    description = "test tool"

    def __init__(self, message):
        self.message = message

    def run(self, action_name, params):
        return {
            "message": self.message,
            "previous_result": params.get("previous_result"),
        }


VALID_SUMMARY_REPORT = "## 摘要\n完成联调。\n## 核心观点\n流程清晰。\n## 风险点\n原文未提供明确风险。"


class SequenceReportTool(BaseTool):
    name = "sequence_report_tool"
    description = "test report sequence"

    def __init__(self, messages):
        self.messages = list(messages)
        self.params_seen = []

    def run(self, action_name, params):
        self.params_seen.append(params)
        message = self.messages.pop(0)
        return {"message": message, "report_markdown": message}


def test_minimal_loop_keeps_unknown_task_fallback_with_mock_result():
    state = AgentState(
        task_id="task_test",
        user_input="做一个未知任务",
        task_type="unknown",
        intent="unknown fallback",
    )

    updated = run_minimal_loop(state)

    assert updated.status == "completed"
    assert updated.current_step_id == 1
    assert updated.plan.status == "completed"
    assert updated.plan.steps[0].status == "completed"
    assert updated.current_action.tool_name == "mock_tool"
    assert len(updated.results) == 1
    assert updated.results[0].result["message"] == "mock result"
    assert len(updated.checks) == 1
    assert updated.checks[0].passed is True
    assert updated.final_output == "mock result"


def test_loop_executes_full_planned_summary_flow():
    state = AgentState(
        task_id="task_test",
        user_input="帮我总结",
        task_type="summarize",
        intent="summarize_article",
    )

    registry = {
        "file_tool": EchoTool("file"),
        "text_tool": EchoTool("text"),
        "report_tool": EchoTool(VALID_SUMMARY_REPORT),
    }

    updated = run_minimal_loop(state, tool_registry=registry)

    assert updated.status == "completed"
    assert len(updated.plan.steps) == 3
    assert len(updated.results) == 3
    assert len(updated.checks) == 3
    assert [step.status for step in updated.plan.steps] == [
        "completed",
        "completed",
        "completed",
    ]
    assert updated.results[0].tool_name == "file_tool"
    assert updated.results[1].tool_name == "text_tool"
    assert updated.results[2].tool_name == "report_tool"


def test_loop_accepts_injected_tool_registry_for_summary_flow():
    state = AgentState(
        task_id="task_test",
        user_input="帮我总结",
        task_type="summarize",
        intent="summarize_article",
    )
    registry = {
        "file_tool": EchoTool("file"),
        "text_tool": EchoTool("text"),
        "report_tool": EchoTool(VALID_SUMMARY_REPORT),
    }

    updated = run_minimal_loop(state, tool_registry=registry)

    assert updated.final_output == VALID_SUMMARY_REPORT
    assert updated.results[1].result["previous_result"]["message"] == "file"
    assert updated.results[2].result["previous_result"]["message"] == "text"


def test_loop_retries_failed_report_step_and_then_completes():
    report_tool = SequenceReportTool(
        [
            "## 摘要\n完成联调。\n## 核心观点\n流程清晰。",
            VALID_SUMMARY_REPORT,
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

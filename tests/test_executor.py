from core.executor import Executor
from core.state import Action, ToolResult
from tools.base_tool import BaseTool
from tools.registry import TOOL_REGISTRY


def make_action(tool_name: str = "mock_tool") -> Action:
    return Action(
        action_id="action_test_1",
        step_id=1,
        tool_name=tool_name,
        action_name="run",
        params={"user_input": "帮我总结一段文本"},
        reason="test action",
    )


def test_executor_runs_registered_tool():
    result = Executor(TOOL_REGISTRY).run(make_action())

    assert isinstance(result, ToolResult)
    assert result.success is True
    assert result.step_id == 1
    assert result.tool_name == "mock_tool"
    assert result.result["message"] == "mock result"
    assert result.error is None


def test_executor_returns_tool_unavailable_for_missing_tool():
    result = Executor({}).run(make_action())

    assert result.success is False
    assert result.error == "tool_unavailable: mock_tool"


def test_executor_catches_tool_error():
    class BrokenTool(BaseTool):
        name = "broken_tool"
        description = "Raises an error."

        def run(self, action_name, params):
            raise RuntimeError("boom")

    result = Executor({"broken_tool": BrokenTool()}).run(make_action("broken_tool"))

    assert result.success is False
    assert result.error == "tool_error: boom"

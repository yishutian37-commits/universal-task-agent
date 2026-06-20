from core.state import ToolResult
from core.verifier import Verifier


def test_verifier_passes_successful_tool_result():
    result = ToolResult(
        success=True,
        tool_name="mock_tool",
        action_name="run",
        result={"message": "mock result"},
    )

    check = Verifier().check(result)

    assert check.passed is True
    assert check.failed_reasons == []
    assert check.suggested_fix == []


def test_verifier_fails_unsuccessful_tool_result():
    result = ToolResult(
        success=False,
        tool_name="mock_tool",
        action_name="run",
        result={},
        error="tool_unavailable: mock_tool",
    )

    check = Verifier().check(result)

    assert check.passed is False
    assert check.failed_reasons == ["工具执行失败：tool_unavailable: mock_tool"]
    assert check.suggested_fix == ["检查工具名称或工具实现"]

from tools.mock_tool import MockTool
from tools.registry import TOOL_REGISTRY


def test_mock_tool_returns_fixed_success_result():
    tool = MockTool()

    result = tool.run("run", {"user_input": "帮我总结一段文本"})

    assert result["message"] == "mock result"
    assert result["echo"]["user_input"] == "帮我总结一段文本"


def test_tool_registry_does_not_expose_mock_tool_in_runtime_registry():
    assert "mock_tool" not in TOOL_REGISTRY


def test_registry_contains_summary_demo_tools():
    assert TOOL_REGISTRY["file_tool"].name == "file_tool"
    assert TOOL_REGISTRY["text_tool"].name == "text_tool"
    assert TOOL_REGISTRY["table_tool"].name == "table_tool"
    assert TOOL_REGISTRY["report_tool"].name == "report_tool"

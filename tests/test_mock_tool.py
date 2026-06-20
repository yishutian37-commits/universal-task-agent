from tools.mock_tool import MockTool
from tools.registry import TOOL_REGISTRY


def test_mock_tool_returns_fixed_success_result():
    tool = MockTool()

    result = tool.run("run", {"user_input": "帮我总结一段文本"})

    assert result["message"] == "mock result"
    assert result["echo"]["user_input"] == "帮我总结一段文本"


def test_tool_registry_contains_mock_tool():
    assert "mock_tool" in TOOL_REGISTRY
    assert TOOL_REGISTRY["mock_tool"].name == "mock_tool"


def test_registry_contains_v0_3_placeholder_tools():
    for name in ["file_tool", "text_tool", "table_tool", "report_tool"]:
        assert name in TOOL_REGISTRY
        assert TOOL_REGISTRY[name].run("any", {"goal": "test"})["message"] == "mock result"

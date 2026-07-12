import pytest

from tools.registry import build_tool_registry


class FakeLangChainTool:
    name = "fake_langchain_tool"
    description = "Fake LangChain tool for adapter tests."

    def __init__(self, output=None):
        self.calls = []
        self.output = output if output is not None else "ok"

    def invoke(self, tool_input):
        self.calls.append(tool_input)
        return self.output


class BrokenLangChainTool:
    name = "broken_langchain_tool"
    description = "Fake broken LangChain tool."

    def invoke(self, tool_input):
        raise ValueError("boom")


def test_langchain_adapter_invokes_tool_with_explicit_tool_input():
    from tools.langchain_adapter import LangChainToolAdapter

    langchain_tool = FakeLangChainTool(output={"value": 42})
    adapter = LangChainToolAdapter(langchain_tool)

    result = adapter.run("invoke", {"tool_input": {"text": "hello"}})

    assert langchain_tool.calls == [{"text": "hello"}]
    assert result["message"].startswith("LangChain 工具执行完成")
    assert "42" in result["message"]
    assert result["tool"] == "fake_langchain_tool"
    assert result["output"] == {"value": 42}
    assert result["value"] == 42


def test_langchain_adapter_builds_query_input_from_user_input():
    from tools.langchain_adapter import LangChainToolAdapter

    langchain_tool = FakeLangChainTool(output="received")
    adapter = LangChainToolAdapter(langchain_tool)

    result = adapter.run("invoke", {"user_input": "帮我处理这段话", "goal": "备用目标"})

    assert langchain_tool.calls == [{"query": "帮我处理这段话"}]
    assert result["output"] == "received"


def test_langchain_adapter_prefers_query_over_goal():
    from tools.langchain_adapter import LangChainToolAdapter

    langchain_tool = FakeLangChainTool()
    adapter = LangChainToolAdapter(langchain_tool)

    adapter.run("invoke", {"query": "明确查询", "goal": "步骤目标"})

    assert langchain_tool.calls == [{"query": "明确查询"}]


def test_langchain_adapter_wraps_invoke_errors_with_readable_message():
    from tools.langchain_adapter import LangChainToolAdapter

    adapter = LangChainToolAdapter(BrokenLangChainTool())

    with pytest.raises(RuntimeError, match="LangChain 工具执行失败：boom"):
        adapter.run("invoke", {"query": "hello"})


def test_default_registry_includes_safe_langchain_demo_tool():
    registry = build_tool_registry()

    assert "langchain_echo_tool" in registry
    assert "langchain_calculator_tool" in registry
    assert "langchain_datetime_tool" in registry
    assert "langchain_http_get_tool" in registry
    assert "langchain_search_tool" in registry
    assert "langchain_weather_tool" in registry
    assert "langchain_json_tool" in registry


def test_registry_can_disable_langchain_demo_tool():
    registry = build_tool_registry(enable_langchain_tools=False)

    assert "langchain_echo_tool" not in registry
    assert "langchain_calculator_tool" not in registry
    assert "langchain_datetime_tool" not in registry
    assert "langchain_http_get_tool" not in registry
    assert "langchain_search_tool" not in registry
    assert "langchain_weather_tool" not in registry
    assert "langchain_json_tool" not in registry


def test_registry_configures_file_tool_with_project_root(tmp_path):
    registry = build_tool_registry(project_root=tmp_path)

    assert registry["file_tool"].project_root == tmp_path.resolve()


def test_registry_can_enable_dangerous_langchain_tools(tmp_path):
    registry = build_tool_registry(
        enable_dangerous_tools=True,
        authorization_manager=object(),
        dangerous_allowed_roots=[tmp_path],
    )

    assert "langchain_shell_tool" in registry
    assert "langchain_file_write_tool" in registry
    assert "langchain_python_repl_tool" in registry
    assert "langchain_file_delete_tool" in registry
    assert "langchain_directory_create_tool" in registry


def test_registry_does_not_enable_dangerous_langchain_tools_by_default():
    registry = build_tool_registry()

    assert "langchain_shell_tool" not in registry
    assert "langchain_file_write_tool" not in registry
    assert "langchain_python_repl_tool" not in registry
    assert "langchain_file_delete_tool" not in registry
    assert "langchain_directory_create_tool" not in registry


def test_registry_can_wrap_custom_langchain_tools():
    registry = build_tool_registry(langchain_tools=[FakeLangChainTool(output="custom")])

    tool = registry["fake_langchain_tool"]
    result = tool.run("invoke", {"query": "hello"})

    assert result["tool"] == "fake_langchain_tool"
    assert result["output"] == "custom"

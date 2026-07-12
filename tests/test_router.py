import pytest

from core.router import Router
from core.state import AgentState, PlanStep, ToolResult


def route(goal: str):
    state = AgentState(task_id="task_test", user_input="测试")
    return Router().choose_tool(state, PlanStep(step_id=1, goal=goal))


def test_router_routes_reading_goal_to_file_tool():
    action = route("读取输入内容")

    assert action.tool_name == "file_tool"
    assert action.action_name == "read"
    assert action.reason


def test_router_routes_text_goal_to_text_tool():
    action = route("提取核心信息")

    assert action.tool_name == "text_tool"
    assert action.action_name == "process"


def test_router_routes_table_goal_to_table_tool():
    action = route("分析字段、行数、列数和缺失值")

    assert action.tool_name == "table_tool"
    assert action.action_name == "analyze"


def test_router_routes_report_goal_to_report_tool():
    action = route("生成结构化报告")

    assert action.tool_name == "report_tool"
    assert action.action_name == "generate"


def test_router_routes_table_report_goal_to_report_tool():
    action = route("生成表格分析报告")

    assert action.tool_name == "report_tool"
    assert action.action_name == "generate"


def test_router_falls_back_to_unsupported_task_instead_of_mock_tool():
    action = route("整理我的桌面文件")

    assert action.tool_name == "unsupported_task"
    assert action.action_name == "unsupported"
    assert "不支持" in action.reason


def test_router_routes_complex_summary_risk_step_to_text_tool():
    state = AgentState(
        task_id="task_test",
        user_input="帮我执行复杂任务：[1]分析 [2]计划 [3]总结风险点",
        task_type="complex_task",
    )

    action = Router().choose_tool(state, PlanStep(step_id=3, goal="总结风险点"))

    assert action.tool_name == "text_tool"
    assert action.action_name == "process"


def test_router_routes_complex_text_transform_step_to_text_tool():
    state = AgentState(
        task_id="task_test",
        user_input="帮我执行复杂任务：[1]总结全文核心观点 [2]改写成适合小白看的版本",
        task_type="complex_task",
    )

    action = Router().choose_tool(state, PlanStep(step_id=2, goal="改写成适合小白看的版本"))

    assert action.tool_name == "text_tool"
    assert action.action_name == "process"


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


def test_router_routes_search_goal_to_search_tool():
    state = AgentState(task_id="task_test", user_input="调研 UTA Agent 框架")
    step = PlanStep(step_id=1, goal="搜索相关资料")

    action = Router().choose_tool(state, step)

    assert action.tool_name == "search_tool"
    assert action.action_name == "search"


def test_router_routes_weather_goal_to_search_tool():
    action = route("查询今日天气")

    assert action.tool_name == "search_tool"
    assert action.action_name == "search"


def test_router_routes_code_reading_goal_to_code_tool():
    action = route("扫描 UTA 任务执行链路代码")

    assert action.tool_name == "code_tool"
    assert action.action_name == "scan"


def test_router_routes_geo_goal_to_geo_tool():
    action = route("读取 GEO 规则包并生成问题矩阵")

    assert action.tool_name == "geo_tool"
    assert action.action_name == "analyze"


def test_router_routes_history_goal_to_history_tool():
    action = route("读取历史任务记录")

    assert action.tool_name == "history_tool"
    assert action.action_name == "list"


def test_router_can_select_langchain_echo_tool():
    action = route("用 LangChain 工具回显 hello")

    assert action.tool_name == "langchain_echo_tool"
    assert action.action_name == "invoke"


@pytest.mark.parametrize(
    ("user_input", "expected_tool"),
    [
        ("计算 2 + 3 * 4", "langchain_calculator_tool"),
        ("现在几点", "langchain_datetime_tool"),
        ("格式化 JSON：{\"a\": 1}", "langchain_json_tool"),
        ("HTTP GET https://example.com", "langchain_http_get_tool"),
        ("用 LangChain 工具搜索 UTA Agent", "langchain_search_tool"),
        ("用 LangChain 天气工具查询包头天气", "langchain_weather_tool"),
        ("执行 shell 命令 echo hello", "langchain_shell_tool"),
        ("写入文件 /tmp/uta-note.txt 内容 hello", "langchain_file_write_tool"),
        ("运行 Python 代码 result = 1 + 2", "langchain_python_repl_tool"),
        ("删除文件 /tmp/uta-note.txt", "langchain_file_delete_tool"),
        ("删除本地文件 /tmp/uta-note.txt", "langchain_file_delete_tool"),
        ("帮我在桌面创建一个名叫测试的文件夹", "langchain_directory_create_tool"),
    ],
)
def test_router_selects_common_langchain_tools(user_input, expected_tool):
    state = AgentState(task_id="task_test", user_input=user_input, task_type="langchain_tool")

    action = Router().choose_tool(state, PlanStep(step_id=1, goal="调用 LangChain 工具处理请求"))

    assert action.tool_name == expected_tool
    assert action.action_name == "invoke"


def test_router_uses_current_request_for_dangerous_tool_input():
    current_input = "帮我在桌面创建一个叫测试的文件夹"
    state = AgentState(
        task_id="task_test",
        user_input=current_input,
        execution_input="前文：帮我在桌面创建一个叫一个的文件夹\n\n当前用户输入：\n" + current_input,
        task_type="langchain_tool",
    )

    action = Router().choose_tool(state, PlanStep(step_id=1, goal="调用 LangChain 工具处理请求"))

    assert action.tool_name == "langchain_directory_create_tool"
    assert action.params["tool_input"] == {"query": current_input}


@pytest.mark.parametrize("user_input", ["当前工作区有哪些文件", "读取 README.md 的内容"])
def test_router_selects_workspace_file_tool(user_input):
    state = AgentState(task_id="task_workspace", user_input=user_input, task_type="langchain_tool")

    action = Router().choose_tool(state, PlanStep(step_id=1, goal="调用工具处理工作区文件请求"))

    assert action.tool_name == "file_tool"

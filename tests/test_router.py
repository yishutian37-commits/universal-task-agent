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


def test_router_falls_back_to_mock_tool():
    action = route("执行 V0.3 mock 工具")

    assert action.tool_name == "mock_tool"
    assert action.action_name == "run"


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

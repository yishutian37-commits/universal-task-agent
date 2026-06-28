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


def test_router_falls_back_to_mock_tool():
    action = route("执行 V0.3 mock 工具")

    assert action.tool_name == "mock_tool"
    assert action.action_name == "run"


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

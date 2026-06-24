from core.planner import Planner
from core.state import Task

SUMMARY_GOALS = ["读取输入内容", "提取核心信息", "生成结构化报告"]


def make_task(task_type: str) -> Task:
    return Task(
        task_id="task_test",
        user_input="测试任务",
        task_type=task_type,
        intent="test",
        input_type="text",
        expected_output="report",
    )


def plan_goals(task_type: str, matched_skill=None) -> list[str]:
    plan = Planner().create_plan(make_task(task_type), matched_skill=matched_skill)
    return [step.goal for step in plan.steps]


def test_planner_creates_summary_plan_without_tools():
    plan = Planner().create_plan(make_task("summarize"))

    assert len(plan.steps) == 3
    assert [step.goal for step in plan.steps] == SUMMARY_GOALS
    assert not hasattr(plan.steps[0], "tool_name")


def test_planner_creates_data_analysis_plan():
    plan = Planner().create_plan(make_task("data_analysis"))

    assert [step.goal for step in plan.steps] == ["读取表格文件", "分析字段、行数、列数和缺失值", "生成表格分析报告"]


def test_planner_creates_unknown_fallback_plan():
    plan = Planner().create_plan(make_task("unknown"))

    assert len(plan.steps) == 1
    assert plan.steps[0].goal == "执行 V0.3 mock 工具"


def test_planner_uses_matched_skill_workflow():
    matched_skill = {
        "id": "custom_summary",
        "workflow": ["读取客户文本", "提炼三条要点", "生成客户版报告"],
    }

    plan = Planner().create_plan(make_task("summarize"), matched_skill=matched_skill)

    assert [step.goal for step in plan.steps] == ["读取客户文本", "提炼三条要点", "生成客户版报告"]


def test_planner_falls_back_when_skill_workflow_is_missing():
    assert plan_goals("summarize", matched_skill={"id": "custom_summary"}) == SUMMARY_GOALS


def test_planner_falls_back_when_skill_workflow_is_not_list():
    matched_skill = {"id": "custom_summary", "workflow": "读取客户文本"}

    assert plan_goals("summarize", matched_skill=matched_skill) == SUMMARY_GOALS


def test_planner_falls_back_when_skill_workflow_is_empty():
    matched_skill = {"id": "custom_summary", "workflow": []}

    assert plan_goals("summarize", matched_skill=matched_skill) == SUMMARY_GOALS


def test_planner_falls_back_when_skill_workflow_has_only_blank_strings():
    matched_skill = {"id": "custom_summary", "workflow": ["", "   ", "\n\t"]}

    assert plan_goals("summarize", matched_skill=matched_skill) == SUMMARY_GOALS


def test_planner_falls_back_when_skill_workflow_has_only_non_strings():
    matched_skill = {"id": "custom_summary", "workflow": [None, True, 123]}

    assert plan_goals("summarize", matched_skill=matched_skill) == SUMMARY_GOALS


def test_planner_ignores_non_string_workflow_entries():
    matched_skill = {
        "id": "custom_summary",
        "workflow": [None, "读取客户文本", True, "生成客户版报告", 123],
    }

    assert plan_goals("summarize", matched_skill=matched_skill) == [
        "读取客户文本",
        "生成客户版报告",
    ]


def test_planner_creates_research_plan():
    task = Task(
        task_id="task_test",
        user_input="调研 UTA Agent 框架",
        task_type="research",
        intent="research_topic",
        input_type="text",
        expected_output="research_report",
    )

    plan = Planner().create_plan(task)

    assert [step.goal for step in plan.steps] == [
        "搜索相关资料",
        "生成带来源的调研报告",
    ]


def test_planner_creates_code_reading_plan():
    plan = Planner().create_plan(make_task("code_reading"))

    assert [step.goal for step in plan.steps] == [
        "扫描 UTA 任务执行链路代码",
        "生成代码阅读报告",
    ]


def test_planner_creates_geo_analysis_plan():
    plan = Planner().create_plan(make_task("geo_analysis"))

    assert [step.goal for step in plan.steps] == [
        "读取 GEO 规则包并生成问题矩阵",
        "生成 GEO 分析报告",
    ]

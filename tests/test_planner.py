from core.planner import Planner
from core.state import Task


def make_task(task_type: str) -> Task:
    return Task(
        task_id="task_test",
        user_input="测试任务",
        task_type=task_type,
        intent="test",
        input_type="text",
        expected_output="report",
    )


def test_planner_creates_summary_plan_without_tools():
    plan = Planner().create_plan(make_task("summarize"))

    assert len(plan.steps) == 3
    assert [step.goal for step in plan.steps] == ["读取输入内容", "提取核心信息", "生成结构化报告"]
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

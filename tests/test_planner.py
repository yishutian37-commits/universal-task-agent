from core.planner import Planner
from core.state import Plan, PlanStep, Task

SUMMARY_GOALS = ["读取输入内容", "提取核心信息", "生成结构化报告"]


class FakePlanningClient:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.calls = []

    def chat_json(self, system_prompt, user_prompt, schema=None):
        self.calls.append((system_prompt, user_prompt, schema))
        if self.error is not None:
            raise self.error
        return self.payload


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


def test_model_planner_creates_validated_structured_plan():
    client = FakePlanningClient(
        {
            "steps": [
                {
                    "goal": "读取项目文件",
                    "tool_hint": "file_tool",
                    "action_hint": "read",
                    "inputs": {"path": "README.md"},
                    "depends_on": [],
                    "success_criteria": ["读取到 README 正文"],
                    "requires_authorization": False,
                },
                {
                    "goal": "生成项目总结",
                    "tool_hint": "report_tool",
                    "action_hint": "generate",
                    "inputs": {},
                    "depends_on": [1],
                    "success_criteria": ["总结包含功能和风险"],
                    "requires_authorization": False,
                },
            ],
            "requires_confirmation": True,
            "reason": "需要读文件并生成报告",
        }
    )
    planner = Planner(
        llm_client=client,
        tool_catalog=[
            {
                "name": "file_tool",
                "description": "Read workspace files",
                "default_action": "read",
                "requires_authorization": False,
            },
            {
                "name": "report_tool",
                "description": "Generate reports",
                "default_action": "generate",
                "requires_authorization": False,
            },
        ],
    )

    plan = planner.create_plan(make_task("code_reading"))

    assert plan.source == "model"
    assert plan.requires_confirmation is True
    assert plan.reason == "需要读文件并生成报告"
    assert [step.step_id for step in plan.steps] == [1, 2]
    assert plan.steps[0].tool_hint == "file_tool"
    assert plan.steps[0].inputs == {"path": "README.md"}
    assert plan.steps[1].depends_on == [1]
    assert client.calls
    assert "file_tool" in client.calls[0][1]


def test_model_planner_falls_back_when_model_returns_unknown_tool():
    client = FakePlanningClient(
        {
            "steps": [{"goal": "操作电脑", "tool_hint": "not_registered"}],
            "requires_confirmation": False,
        }
    )
    planner = Planner(
        llm_client=client,
        tool_catalog=[
            {
                "name": "text_tool",
                "description": "Process text",
                "default_action": "process",
                "requires_authorization": False,
            }
        ],
    )

    plan = planner.create_plan(make_task("summarize"))

    assert plan.source == "template"
    assert [step.goal for step in plan.steps] == SUMMARY_GOALS


def test_model_planner_falls_back_when_model_returns_unknown_action():
    client = FakePlanningClient(
        {
            "steps": [
                {
                    "goal": "删除项目文件",
                    "tool_hint": "file_tool",
                    "action_hint": "delete",
                    "inputs": {"path": "README.md"},
                }
            ],
            "requires_confirmation": False,
        }
    )
    planner = Planner(
        llm_client=client,
        tool_catalog=[
            {
                "name": "file_tool",
                "default_action": "read",
                "requires_authorization": False,
                "actions": [
                    {
                        "name": "read",
                        "parameter_schema": {"type": "object"},
                        "requires_authorization": False,
                    }
                ],
            }
        ],
    )

    plan = planner.create_plan(make_task("summarize"))

    assert plan.source == "template"


def test_model_planner_falls_back_when_action_inputs_violate_contract():
    client = FakePlanningClient(
        {
            "steps": [
                {
                    "goal": "读取项目文件",
                    "tool_hint": "file_tool",
                    "action_hint": "read",
                    "inputs": {"path": 42},
                }
            ],
            "requires_confirmation": False,
        }
    )
    planner = Planner(
        llm_client=client,
        tool_catalog=[
            {
                "name": "file_tool",
                "default_action": "read",
                "requires_authorization": False,
                "actions": [
                    {
                        "name": "read",
                        "parameter_schema": {
                            "type": "object",
                            "properties": {"path": {"type": "string"}},
                            "required": ["path"],
                        },
                        "requires_authorization": False,
                    }
                ],
            }
        ],
    )

    plan = planner.create_plan(make_task("summarize"))

    assert plan.source == "template"


def test_model_planner_falls_back_when_model_call_fails():
    planner = Planner(
        llm_client=FakePlanningClient(error=RuntimeError("offline")),
        tool_catalog=[],
    )

    plan = planner.create_plan(make_task("data_analysis"))

    assert plan.source == "template"
    assert [step.goal for step in plan.steps] == ["读取表格文件", "分析字段、行数、列数和缺失值", "生成表格分析报告"]


def test_model_replan_receives_failure_context_and_preserves_completed_prefix():
    client = FakePlanningClient(
        {
            "steps": [
                {
                    "goal": "根据校验缺口重新提取核心信息",
                    "tool_hint": "text_tool",
                    "action_hint": "process",
                    "depends_on": [1],
                    "success_criteria": ["包含摘要、核心观点和风险点"],
                },
                {
                    "goal": "生成结构化报告",
                    "tool_hint": "report_tool",
                    "action_hint": "generate",
                    "depends_on": [2],
                    "success_criteria": ["报告通过校验"],
                },
            ],
            "requires_confirmation": False,
            "reason": "根据失败证据修正后续步骤",
        }
    )
    planner = Planner(
        llm_client=client,
        tool_catalog=[
            {"name": "text_tool", "default_action": "process", "requires_authorization": False},
            {"name": "report_tool", "default_action": "generate", "requires_authorization": False},
        ],
    )
    existing_plan = Plan(
        plan_id="plan_task_test",
        task_id="task_test",
        steps=[
            PlanStep(step_id=1, goal="读取输入内容", status="completed"),
            PlanStep(step_id=2, goal="提取核心信息", status="failed"),
            PlanStep(step_id=3, goal="生成结构化报告"),
        ],
        status="running",
    )
    failure_context = {
        "failed_step_id": 2,
        "failed_goal": "提取核心信息",
        "root_cause": "输出不完整",
        "repair_strategy": "补齐必要小节",
        "failed_reasons": ["缺少风险点"],
        "completed_steps": [{"step_id": 1, "result": {"content": "原文"}}],
        "evidence": {"files": [{"path": "input.md"}]},
    }

    plan = planner.create_plan(
        make_task("summarize"),
        failure_context=failure_context,
        existing_plan=existing_plan,
    )

    assert plan.source == "replan"
    assert [step.goal for step in plan.steps] == [
        "读取输入内容",
        "根据校验缺口重新提取核心信息",
        "生成结构化报告",
    ]
    assert plan.steps[0].status == "completed"
    assert plan.steps[1].step_id == 2
    assert "缺少风险点" in client.calls[0][1]
    assert "input.md" in client.calls[0][1]


def test_fallback_replan_changes_failed_step_with_repair_strategy():
    planner = Planner()
    existing_plan = planner.create_plan(make_task("summarize"))
    existing_plan.steps[0].status = "completed"
    existing_plan.steps[1].status = "failed"
    existing_plan.steps[1].tool_hint = "text_tool"
    existing_plan.steps[1].action_hint = "process"
    existing_plan.steps[1].inputs = {"format": "stale"}
    existing_plan.steps[1].success_criteria = ["旧标准"]
    existing_plan.steps[1].requires_authorization = True

    plan = planner.create_plan(
        make_task("summarize"),
        failure_context={
            "failed_step_id": 2,
            "repair_strategy": "补齐必要小节",
        },
        existing_plan=existing_plan,
    )

    assert plan.source == "replan"
    assert plan.steps[0].status == "completed"
    assert plan.steps[1].goal != existing_plan.steps[1].goal
    assert "补齐必要小节" in plan.steps[1].goal
    assert plan.steps[1].status == "pending"
    assert plan.steps[1].tool_hint is None
    assert plan.steps[1].action_hint is None
    assert plan.steps[1].inputs == {}
    assert plan.steps[1].success_criteria == []
    assert plan.steps[1].requires_authorization is False


def test_planner_creates_data_analysis_plan():
    plan = Planner().create_plan(make_task("data_analysis"))

    assert [step.goal for step in plan.steps] == ["读取表格文件", "分析字段、行数、列数和缺失值", "生成表格分析报告"]


def test_planner_creates_unknown_fallback_plan():
    plan = Planner().create_plan(make_task("unknown"))

    assert len(plan.steps) == 1
    assert plan.steps[0].goal == "当前任务类型不受支持，停止执行并说明能力边界"


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


def test_planner_creates_history_query_plan():
    plan = Planner().create_plan(make_task("history_query"))

    assert [step.goal for step in plan.steps] == ["读取历史任务记录"]


def test_planner_creates_langchain_tool_plan():
    plan = Planner().create_plan(make_task("langchain_tool"))

    assert [step.goal for step in plan.steps] == ["调用 LangChain 工具处理请求"]


def test_planner_splits_complex_task_numbered_brackets():
    task = Task(
        task_id="task_test",
        user_input="帮我执行复杂任务：[1]分析当前项目状态 [2]列出下一步计划 [3]总结风险点",
        task_type="complex_task",
        intent="execute_complex_task",
        input_type="text",
        expected_output="step_checklist",
    )

    plan = Planner().create_plan(task)

    assert [step.goal for step in plan.steps] == [
        "分析当前项目状态",
        "列出下一步计划",
        "总结风险点",
    ]


def test_planner_splits_complex_task_compact_numbered_brackets():
    task = Task(
        task_id="task_test",
        user_input="帮我执行复杂任务：[1]分析项目[2]列出计划[3]总结风险",
        task_type="complex_task",
        intent="execute_complex_task",
        input_type="text",
        expected_output="step_checklist",
    )

    plan = Planner().create_plan(task)

    assert [step.goal for step in plan.steps] == [
        "分析项目",
        "列出计划",
        "总结风险",
    ]


def test_planner_splits_complex_task_connector_words():
    task = Task(
        task_id="task_test",
        user_input="请分步骤执行：先分析项目，然后列出计划，最后总结风险",
        task_type="complex_task",
        intent="execute_complex_task",
        input_type="text",
        expected_output="step_checklist",
    )

    plan = Planner().create_plan(task)

    assert [step.goal for step in plan.steps] == [
        "分析项目",
        "列出计划",
        "总结风险",
    ]


def test_planner_splits_numbered_agent_task_list_after_article_text():
    task = Task(
        task_id="task_test",
        user_input=(
            "帮我总结一段文本：文章里可能有 2026.6 这样的数字，也有很多正文。\n\n"
            "你可以让 Agent 做这几个任务：\n"
            "1. 总结全文核心观点\n"
            "2. 提炼 5 个关键结论\n"
            "3. 找出文章的逻辑结构\n"
            "4. 判断作者真正想反对什么\n"
            "5. 用一句话压缩全文\n"
            "6. 改写成适合小白看的版本\n"
            "7. 改写成适合发朋友圈/知乎的版本"
        ),
        task_type="complex_task",
        intent="execute_complex_task",
        input_type="text",
        expected_output="step_checklist",
    )

    plan = Planner().create_plan(task)

    assert [step.goal for step in plan.steps] == [
        "总结全文核心观点",
        "提炼 5 个关键结论",
        "找出文章的逻辑结构",
        "判断作者真正想反对什么",
        "用一句话压缩全文",
        "改写成适合小白看的版本",
        "改写成适合发朋友圈/知乎的版本",
    ]

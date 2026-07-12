from core.loop import run_minimal_loop
from core.state import AgentState, Plan, PlanStep, ToolResult
from tools.base_tool import BaseTool
from tools.report_tool import ReportTool


class EchoTool(BaseTool):
    name = "echo_tool"
    description = "test tool"

    def __init__(self, message):
        self.message = message

    def run(self, action_name, params):
        return {
            "message": self.message if isinstance(self.message, str) else str(self.message),
            "previous_result": params.get("previous_result"),
            **(self.message if isinstance(self.message, dict) else {}),
        }


class CountingTool(BaseTool):
    name = "counting_tool"
    description = "counts calls"

    def __init__(self, message):
        self.message = message
        self.calls = 0

    def run(self, action_name, params):
        self.calls += 1
        return {"message": self.message, "call": self.calls}


VALID_SUMMARY_REPORT = "## 摘要\n完成联调。\n## 核心观点\n流程清晰。\n## 风险点\n原文未提供明确风险。"


class SequenceReportTool(BaseTool):
    name = "sequence_report_tool"
    description = "test report sequence"

    def __init__(self, messages):
        self.messages = list(messages)
        self.params_seen = []

    def run(self, action_name, params):
        self.params_seen.append(params)
        message = self.messages.pop(0)
        return {"message": message, "report_markdown": message}


class SequenceTextTool(BaseTool):
    name = "sequence_text_tool"
    description = "test text sequence"

    def __init__(self, messages):
        self.messages = list(messages)
        self.params_seen = []

    def run(self, action_name, params):
        self.params_seen.append(params)
        message = self.messages.pop(0)
        return {"message": message, "summary_markdown": message}


def test_minimal_loop_fails_unknown_task_instead_of_claiming_mock_success():
    state = AgentState(
        task_id="task_test",
        user_input="做一个未知任务",
        task_type="unknown",
        intent="unknown fallback",
    )

    updated = run_minimal_loop(state)

    assert updated.status == "failed"
    assert updated.current_step_id == 1
    assert updated.plan.status == "failed"
    assert updated.plan.steps[0].status == "failed"
    assert updated.current_action.tool_name == "unsupported_task"
    assert len(updated.results) == 1
    assert updated.results[0].success is False
    assert updated.results[0].error == "当前任务不支持：没有匹配到可用工具，已停止执行，避免伪完成"
    assert len(updated.checks) == 1
    assert updated.checks[0].passed is False
    assert "不支持" in updated.final_output


def test_loop_executes_full_planned_summary_flow():
    state = AgentState(
        task_id="task_test",
        user_input="帮我总结",
        task_type="summarize",
        intent="summarize_article",
    )

    registry = {
        "file_tool": EchoTool("file"),
        "text_tool": EchoTool(VALID_SUMMARY_REPORT),
        "report_tool": EchoTool(VALID_SUMMARY_REPORT),
    }

    updated = run_minimal_loop(state, tool_registry=registry)

    assert updated.status == "completed"
    assert len(updated.plan.steps) == 3
    assert len(updated.results) == 3
    assert len(updated.checks) == 3
    assert [step.status for step in updated.plan.steps] == [
        "completed",
        "completed",
        "completed",
    ]
    assert updated.results[0].tool_name == "file_tool"
    assert updated.results[1].tool_name == "text_tool"
    assert updated.results[2].tool_name == "report_tool"


def test_loop_emits_progress_events():
    state = AgentState(
        task_id="task_test",
        user_input="帮我总结",
        task_type="summarize",
        intent="summarize_article",
    )
    registry = {
        "file_tool": EchoTool("file"),
        "text_tool": EchoTool(VALID_SUMMARY_REPORT),
        "report_tool": EchoTool(VALID_SUMMARY_REPORT),
    }
    events = []

    updated = run_minimal_loop(state, tool_registry=registry, on_progress=events.append)

    assert updated.status == "completed"
    assert [event["task_id"] for event in events] == ["task_test"] * len(events)
    assert [event["type"] for event in events] == [
        "plan_created",
        "step_started",
        "tool_selected",
        "tool_executed",
        "verified",
        "step_done",
        "step_started",
        "tool_selected",
        "tool_executed",
        "verified",
        "step_done",
        "step_started",
        "tool_selected",
        "tool_executed",
        "verified",
        "step_done",
    ]
    assert events[0]["data"]["steps"][0] == {"step_id": 1, "goal": "读取输入内容"}
    assert events[2]["data"]["tool_name"] == "file_tool"
    assert events[4]["data"]["passed"] is True


def test_loop_accepts_injected_tool_registry_for_summary_flow():
    state = AgentState(
        task_id="task_test",
        user_input="帮我总结",
        task_type="summarize",
        intent="summarize_article",
    )
    registry = {
        "file_tool": EchoTool("file"),
        "text_tool": EchoTool(VALID_SUMMARY_REPORT),
        "report_tool": EchoTool(VALID_SUMMARY_REPORT),
    }

    updated = run_minimal_loop(state, tool_registry=registry)

    assert updated.final_output == VALID_SUMMARY_REPORT
    assert updated.results[1].result["previous_result"]["message"] == "file"
    assert updated.results[2].result["previous_result"]["message"] == VALID_SUMMARY_REPORT


def test_loop_passes_matched_skill_workflow_to_planner():
    state = AgentState(
        task_id="task_test",
        user_input="帮我总结",
        task_type="summarize",
        intent="summarize_article",
        matched_skill={
            "id": "custom_summary",
            "workflow": ["读取客户文本", "提取客户核心观点", "生成客户报告"],
        },
    )
    registry = {
        "file_tool": EchoTool("file"),
        "text_tool": EchoTool(VALID_SUMMARY_REPORT),
        "report_tool": EchoTool(VALID_SUMMARY_REPORT),
    }

    updated = run_minimal_loop(state, tool_registry=registry)

    assert [step.goal for step in updated.plan.steps] == [
        "读取客户文本",
        "提取客户核心观点",
        "生成客户报告",
    ]


def test_loop_retries_failed_report_step_and_then_completes():
    report_tool = SequenceReportTool(
        [
            "## 摘要\n完成联调。\n## 核心观点\n流程清晰。",
            VALID_SUMMARY_REPORT,
        ]
    )
    registry = {
        "file_tool": EchoTool("file"),
        "text_tool": EchoTool(VALID_SUMMARY_REPORT),
        "report_tool": report_tool,
    }
    state = AgentState(
        task_id="task_test",
        user_input="帮我总结",
        task_type="summarize",
        intent="summarize_article",
    )

    updated = run_minimal_loop(state, tool_registry=registry)

    assert updated.status == "completed"
    assert len(updated.feedbacks) == 1
    assert updated.feedbacks[0].failure_type == "incomplete_output"
    assert report_tool.params_seen[1]["feedback"].failure_type == "incomplete_output"
    assert report_tool.params_seen[1]["previous_result"]["message"] == VALID_SUMMARY_REPORT


def test_loop_retries_failed_text_step_with_feedback():
    text_tool = SequenceTextTool(
        [
            "## 摘要\n完成联调。\n## 核心观点\n流程清晰。",
            VALID_SUMMARY_REPORT,
        ]
    )
    registry = {
        "file_tool": EchoTool("file"),
        "text_tool": text_tool,
        "report_tool": EchoTool(VALID_SUMMARY_REPORT),
    }
    state = AgentState(
        task_id="task_test",
        user_input="帮我总结",
        task_type="summarize",
        intent="summarize_article",
    )

    updated = run_minimal_loop(state, tool_registry=registry)

    assert updated.status == "completed"
    assert len(updated.feedbacks) == 1
    assert text_tool.params_seen[1]["feedback"].failure_type == "incomplete_output"
    assert text_tool.params_seen[1]["previous_result"]["message"] == "file"


def test_loop_fails_after_report_step_retries_are_exhausted():
    report_tool = SequenceReportTool(
        [
            "## 摘要\n完成联调。",
            "## 摘要\n完成联调。",
            "## 摘要\n完成联调。",
        ]
    )
    registry = {
        "file_tool": EchoTool("file"),
        "text_tool": EchoTool(VALID_SUMMARY_REPORT),
        "report_tool": report_tool,
    }
    state = AgentState(
        task_id="task_test",
        user_input="帮我总结",
        task_type="summarize",
        intent="summarize_article",
        max_replans=0,
    )

    updated = run_minimal_loop(state, tool_registry=registry)

    assert updated.status == "failed"
    assert updated.plan.status == "failed"
    assert len(updated.feedbacks) == 3
    assert "缺少必要小节：核心观点" in updated.final_output


def test_loop_replans_once_without_rerunning_completed_steps():
    file_tool = CountingTool("file")
    text_tool = SequenceTextTool(
        [
            "## 摘要\n缺少小节。",
            "## 摘要\n还是缺少。",
            "## 摘要\n继续缺少。",
            VALID_SUMMARY_REPORT,
        ]
    )
    registry = {
        "file_tool": file_tool,
        "text_tool": text_tool,
        "report_tool": EchoTool(VALID_SUMMARY_REPORT),
    }
    state = AgentState(
        task_id="task_test",
        user_input="帮我总结",
        task_type="summarize",
        intent="summarize_article",
        max_replans=1,
    )

    updated = run_minimal_loop(state, tool_registry=registry)

    assert updated.status == "completed"
    assert updated.replan_count == 1
    assert len(updated.replan_events) == 1
    assert updated.replan_events[0]["failed_step_id"] == 2
    assert updated.replan_events[0]["resume_step_id"] == 2
    assert file_tool.calls == 1
    assert len(text_tool.params_seen) == 4
    assert updated.final_output == VALID_SUMMARY_REPORT


def test_loop_resumes_existing_plan_without_rerunning_completed_steps():
    file_tool = CountingTool("file")
    text_tool = CountingTool(VALID_SUMMARY_REPORT)
    report_tool = CountingTool(VALID_SUMMARY_REPORT)
    registry = {
        "file_tool": file_tool,
        "text_tool": text_tool,
        "report_tool": report_tool,
    }
    state = AgentState(
        task_id="task_resume",
        user_input="帮我总结",
        task_type="summarize",
        intent="summarize_article",
        status="running",
        current_step_id=2,
    )
    state.plan = Plan(
        plan_id="plan_task_resume",
        task_id="task_resume",
        steps=[
            PlanStep(
                step_id=1,
                goal="读取输入内容",
                status="completed",
            ),
            PlanStep(
                step_id=2,
                goal="提取核心信息",
                status="running",
            ),
            PlanStep(
                step_id=3,
                goal="生成结构化报告",
                status="pending",
            ),
        ],
        status="running",
    )
    state.results.append(
        ToolResult(
            success=True,
            tool_name="file_tool",
            action_name="read",
            result={"message": "file"},
            step_id=1,
        )
    )
    events = []

    updated = run_minimal_loop(state, tool_registry=registry, on_progress=events.append)

    assert updated.status == "completed"
    assert file_tool.calls == 0
    assert text_tool.calls == 1
    assert report_tool.calls == 1
    assert updated.results[0].tool_name == "file_tool"
    assert updated.results[1].tool_name == "text_tool"
    assert [step.status for step in updated.plan.steps] == ["completed", "completed", "completed"]
    assert events[0]["type"] == "plan_resumed"
    assert events[0]["data"]["resume_step_id"] == 2


def test_loop_fails_when_replan_budget_is_exhausted():
    text_tool = SequenceTextTool(
        [
            "## 摘要\n缺少小节。",
            "## 摘要\n还是缺少。",
            "## 摘要\n继续缺少。",
        ]
    )
    registry = {
        "file_tool": EchoTool("file"),
        "text_tool": text_tool,
        "report_tool": EchoTool(VALID_SUMMARY_REPORT),
    }
    state = AgentState(
        task_id="task_test",
        user_input="帮我总结",
        task_type="summarize",
        intent="summarize_article",
        max_replans=0,
    )

    updated = run_minimal_loop(state, tool_registry=registry)

    assert updated.status == "failed"
    assert updated.replan_count == 0
    assert updated.replan_events == []


def test_loop_emits_replanned_progress_event():
    text_tool = SequenceTextTool(
        [
            "## 摘要\n缺少小节。",
            "## 摘要\n还是缺少。",
            "## 摘要\n继续缺少。",
            VALID_SUMMARY_REPORT,
        ]
    )
    registry = {
        "file_tool": EchoTool("file"),
        "text_tool": text_tool,
        "report_tool": EchoTool(VALID_SUMMARY_REPORT),
    }
    state = AgentState(
        task_id="task_test",
        user_input="帮我总结",
        task_type="summarize",
        intent="summarize_article",
        max_replans=1,
    )
    events = []

    run_minimal_loop(state, tool_registry=registry, on_progress=events.append)

    replanned = [event for event in events if event["type"] == "replanned"]
    assert len(replanned) == 1
    assert replanned[0]["data"]["failed_step_id"] == 2
    assert replanned[0]["data"]["resume_step_id"] == 2


def test_loop_executes_data_analysis_flow(tmp_path):
    csv_path = tmp_path / "orders.csv"
    csv_path.write_text(
        "order_id,warehouse,quantity\n"
        "1,上海仓,10\n"
        "2,北京仓,\n"
        "3,上海仓,12\n",
        encoding="utf-8",
    )
    state = AgentState(
        task_id="task_test",
        user_input=f"分析 {csv_path}",
        task_type="data_analysis",
        intent="analyze_table",
    )

    updated = run_minimal_loop(state)

    assert updated.status == "completed"
    assert updated.results[0].tool_name == "file_tool"
    assert updated.results[1].tool_name == "table_tool"
    assert updated.results[2].tool_name == "report_tool"
    assert "## 字段说明" in updated.final_output
    assert "行数：3" in updated.final_output
    assert "缺失值数量：1" in updated.final_output


def test_loop_executes_research_flow():
    registry = {
        "search_tool": EchoTool(
            {
                "query": "UTA Agent",
                "search_results": [
                    {
                        "title": "UTA 路线",
                        "url": "https://example.com/uta",
                        "snippet": "UTA 应先跑通核心 Agent Loop。",
                        "source": "fixture",
                    }
                ],
                "sources": ["https://example.com/uta"],
                "provider": "fixture",
            }
        ),
        "report_tool": ReportTool(),
    }
    state = AgentState(
        task_id="task_test",
        user_input="调研 UTA Agent 框架",
        task_type="research",
        intent="research_topic",
    )

    updated = run_minimal_loop(state, tool_registry=registry)

    assert updated.status == "completed"
    assert updated.results[0].tool_name == "search_tool"
    assert updated.results[1].tool_name == "report_tool"
    assert "## 来源" in updated.final_output

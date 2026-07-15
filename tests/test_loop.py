from pathlib import Path
from types import SimpleNamespace

from core.loop import _apply_plan_edits, _request_user_interaction, run_minimal_loop
from core.interaction import InteractionDecision
from core.state import Action, AgentState, CriterionResult, Plan, PlanStep, ToolResult
from tools.base_tool import BaseTool
from tools.langchain_adapter import LangChainToolAdapter
from tools.langchain_common_tools import (
    DirectoryCreateLangChainTool,
    FileDeleteLangChainTool,
    FileWriteLangChainTool,
)
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


class EvidenceWriteTool(BaseTool):
    name = "langchain_file_write_tool"
    description = "writes evidence file"

    def __init__(self, path):
        self.path = path

    def run(self, action_name, params):
        del action_name, params
        self.path.write_text("done", encoding="utf-8")
        return {"path": str(self.path), "mode": "create", "bytes_written": 4}


class AutoApproveAuthorization:
    def request(self, operation, timeout=None):
        del operation, timeout
        return SimpleNamespace(approved=True, approved_by="test", reason="")


class RecordingRejectAuthorization:
    def __init__(self):
        self.requests = []

    def request(self, operation, timeout=None):
        del timeout
        self.requests.append(operation)
        return SimpleNamespace(approved=False, approved_by="", reason="用户拒绝授权")


class ImmediateInteractionManager:
    def __init__(self, decisions):
        self.decisions = list(decisions)
        self.requests = []

    def request(
        self,
        kind,
        payload,
        task_id,
        request_id=None,
        created_at=None,
        timeout=None,
    ):
        self.requests.append(
            {
                "kind": kind,
                "payload": payload,
                "task_id": task_id,
                "request_id": request_id,
                "created_at": created_at,
                "timeout": timeout,
            }
        )
        return self.decisions.pop(0)


class ReplayInteractionManager:
    def __init__(self, *, accepted=True, status="accepted", response=""):
        self.accepted = accepted
        self.status = status
        self.response = response
        self.requests = []

    def request(
        self,
        kind,
        payload,
        task_id,
        request_id=None,
        created_at=None,
        timeout=None,
    ):
        self.requests.append(
            {
                "kind": kind,
                "payload": payload,
                "task_id": task_id,
                "request_id": request_id,
                "created_at": created_at,
                "timeout": timeout,
            }
        )
        return InteractionDecision(
            request_id=request_id or "",
            accepted=self.accepted,
            status=self.status,
            response=self.response,
        )


class RecordingCheckpointStore:
    def __init__(self):
        self.snapshots = []

    def save(self, state):
        self.snapshots.append(AgentState.from_dict(state.to_dict()))


def test_interaction_checkpoint_precedes_display_and_terminal_decision_precedes_clear():
    state = AgentState(task_id="task_durable_order", user_input="继续任务")
    manager = ReplayInteractionManager(response="/tmp/input.md")
    checkpoints = RecordingCheckpointStore()
    events = []

    def record_event(event):
        events.append(event)
        if event["type"] == "waiting_user":
            saved = checkpoints.snapshots[-1]
            assert saved.pending_interaction is not None
            assert saved.pending_interaction["request_id"] == event["data"]["request_id"]
            assert saved.pending_interaction["task_id"] == state.task_id
            assert saved.pending_interaction["status"] == "pending"

    decision = _request_user_interaction(
        state,
        manager,
        "missing_info",
        {"title": "补充信息", "question": "请提供文件路径"},
        on_progress=record_event,
        checkpoint_store=checkpoints,
    )

    assert decision.accepted is True
    assert [event["type"] for event in events] == ["waiting_user", "interaction_resolved"]
    assert manager.requests[0]["request_id"].startswith("interaction_")
    assert manager.requests[0]["created_at"]
    terminal = next(
        snapshot
        for snapshot in checkpoints.snapshots
        if snapshot.pending_interaction
        and snapshot.pending_interaction.get("status") == "accepted"
    )
    assert terminal.interaction_history[-1]["status"] == "accepted"
    assert terminal.interaction_history[-1]["accepted"] is True
    assert terminal.pending_interaction["response"] == "/tmp/input.md"
    assert checkpoints.snapshots[-1].pending_interaction is None
    assert state.pending_interaction is None


def test_loop_replays_checkpointed_interaction_with_same_identity():
    state = AgentState(
        task_id="task_replay_pending",
        user_input="帮我总结",
        task_type="summarize",
        intent="summarize_article",
        status="waiting_user",
        missing_info=["需要总结的文本"],
    )
    state.pending_interaction = {
        "request_id": "interaction_replay_stable",
        "task_id": state.task_id,
        "kind": "missing_info",
        "payload": {
            "title": "补充任务信息",
            "question": "请补充以下信息：需要总结的文本",
            "missing_info": ["需要总结的文本"],
        },
        "status": "pending",
        "created_at": "2026-07-14T20:00:00",
    }
    manager = ReplayInteractionManager(response="库存接口已完成联调。")
    registry = {
        "file_tool": EchoTool("file"),
        "text_tool": EchoTool(VALID_SUMMARY_REPORT),
        "report_tool": EchoTool(VALID_SUMMARY_REPORT),
    }

    updated = run_minimal_loop(
        state,
        tool_registry=registry,
        interaction_manager=manager,
    )

    assert updated.status == "completed"
    assert manager.requests[0]["request_id"] == "interaction_replay_stable"
    assert manager.requests[0]["task_id"] == "task_replay_pending"
    assert manager.requests[0]["created_at"] == "2026-07-14T20:00:00"
    assert updated.interaction_history[-1]["request_id"] == "interaction_replay_stable"


def test_loop_consumes_checkpointed_terminal_interaction_without_prompting_again():
    class UnexpectedInteractionManager:
        def request(self, *args, **kwargs):
            raise AssertionError("terminal interaction must not be requested again")

    state = AgentState(
        task_id="task_replay_terminal",
        user_input="帮我总结",
        status="waiting_user",
    )
    state.pending_interaction = {
        "request_id": "interaction_terminal",
        "task_id": state.task_id,
        "kind": "missing_info",
        "payload": {"question": "请补充文本"},
        "status": "accepted",
        "accepted": True,
        "response": "库存接口已完成联调。",
        "steps": [],
        "created_at": "2026-07-14T20:00:00",
        "decided_at": "2026-07-14T20:01:00",
    }
    state.interaction_history.append(dict(state.pending_interaction))

    decision = _request_user_interaction(
        state,
        UnexpectedInteractionManager(),
        "missing_info",
        {"question": "请补充文本"},
    )

    assert decision.accepted is True
    assert decision.response == "库存接口已完成联调。"
    assert state.pending_interaction is None
    assert state.status == "running"
    assert [
        item["request_id"]
        for item in state.interaction_history
        if item.get("request_id") == "interaction_terminal"
    ] == ["interaction_terminal"]


def test_interaction_timeout_records_explicit_recoverable_status():
    state = AgentState(task_id="task_timeout_state", user_input="继续任务")
    manager = ReplayInteractionManager(
        accepted=False,
        status="timeout",
        response="等待用户回复超时",
    )
    checkpoints = RecordingCheckpointStore()

    _request_user_interaction(
        state,
        manager,
        "missing_info",
        {"question": "请提供文件路径"},
        checkpoint_store=checkpoints,
    )

    assert state.status == "timed_out"
    assert state.interaction_history[-1]["status"] == "timeout"
    assert state.interaction_history[-1]["response"] == "等待用户回复超时"
    assert checkpoints.snapshots[-1].status == "timed_out"


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


def test_loop_rejects_empty_plan_instead_of_claiming_completion():
    class EmptyPlanner:
        def create_plan(self, task, matched_skill=None, failure_context=None, existing_plan=None):
            del matched_skill, failure_context, existing_plan
            return Plan(plan_id=f"plan_{task.task_id}", task_id=task.task_id, steps=[])

    state = AgentState(task_id="task_empty_plan", user_input="执行任务")

    updated = run_minimal_loop(state, planner=EmptyPlanner())

    assert updated.status == "failed"
    assert updated.plan is not None
    assert updated.plan.status == "failed"
    assert updated.final_output == "计划没有可执行步骤"


def test_loop_fails_safely_when_required_information_has_no_interaction_channel():
    state = AgentState(
        task_id="task_missing_without_channel",
        user_input="帮我总结",
        missing_info=["需要总结的文本"],
    )

    updated = run_minimal_loop(state, interaction_manager=None)

    assert updated.status == "failed"
    assert updated.final_output == "缺少任务必需信息：需要总结的文本"
    assert updated.plan is None


def test_loop_uses_structured_tool_result_as_completed_task_output():
    class SingleStepPlanner:
        def create_plan(self, task, matched_skill=None, failure_context=None, existing_plan=None):
            del matched_skill, failure_context, existing_plan
            return Plan(
                plan_id=f"plan_{task.task_id}",
                task_id=task.task_id,
                steps=[PlanStep(step_id=1, goal="创建输出")],
            )

    class StructuredRouter:
        def choose_tool(self, state, step):
            return Action(
                action_id=f"action_{state.task_id}_{step.step_id}",
                step_id=step.step_id,
                tool_name="structured_tool",
                action_name="run",
                params={},
                reason="test",
            )

    class StructuredTool(BaseTool):
        name = "structured_tool"
        description = "returns structured data"

        def run(self, action_name, params):
            del action_name, params
            return {"path": "/tmp/output.txt", "created": True}

    state = AgentState(task_id="task_structured_output", user_input="创建输出")

    updated = run_minimal_loop(
        state,
        tool_registry={"structured_tool": StructuredTool()},
        planner=SingleStepPlanner(),
        router=StructuredRouter(),
    )

    assert updated.status == "completed"
    assert '"path": "/tmp/output.txt"' in updated.final_output
    assert '"created": true' in updated.final_output


def test_loop_requests_missing_information_before_planning_and_continues():
    manager = ImmediateInteractionManager(
        [
            InteractionDecision(
                request_id="interaction_1",
                accepted=True,
                status="accepted",
                response="文本内容是：库存接口已完成联调。",
            )
        ]
    )
    state = AgentState(
        task_id="task_missing_info",
        user_input="帮我总结",
        task_type="summarize",
        intent="summarize_article",
        missing_info=["需要总结的文本"],
    )
    registry = {
        "file_tool": EchoTool("file"),
        "text_tool": EchoTool(VALID_SUMMARY_REPORT),
        "report_tool": EchoTool(VALID_SUMMARY_REPORT),
    }

    updated = run_minimal_loop(
        state,
        tool_registry=registry,
        interaction_manager=manager,
    )

    assert updated.status == "completed"
    assert manager.requests[0]["kind"] == "missing_info"
    assert "需要总结的文本" in manager.requests[0]["payload"]["question"]
    assert "库存接口已完成联调" in updated.execution_input
    assert updated.missing_info == []
    assert updated.pending_interaction is None
    assert updated.interaction_history[-1]["status"] == "accepted"


def test_loop_does_not_clear_missing_information_after_empty_confirmation():
    manager = ImmediateInteractionManager(
        [
            InteractionDecision(
                request_id="interaction_empty_missing_info",
                accepted=True,
                status="accepted",
                response="   ",
            )
        ]
    )
    state = AgentState(
        task_id="task_empty_missing_info",
        user_input="帮我总结",
        task_type="summarize",
        missing_info=["需要总结的文本"],
    )

    updated = run_minimal_loop(state, interaction_manager=manager)

    assert updated.status == "failed"
    assert updated.missing_info == ["需要总结的文本"]
    assert updated.plan is None
    assert updated.final_output == "用户未提供任务所需信息"


def test_loop_retries_current_step_once_after_user_supplies_missing_path():
    class MissingThenSuccessfulFileTool(BaseTool):
        name = "file_tool"
        description = "fails until user supplies a path"

        def __init__(self):
            self.calls = 0
            self.inputs = []

        def run(self, action_name, params):
            del action_name
            self.calls += 1
            self.inputs.append(params.get("user_input"))
            if self.calls == 1:
                raise FileNotFoundError("文件路径不存在")
            return {"message": "已读取文件"}

    class SingleStepPlanner:
        def create_plan(self, task, matched_skill=None, failure_context=None, existing_plan=None):
            del matched_skill, failure_context, existing_plan
            return Plan(
                plan_id=f"plan_{task.task_id}",
                task_id=task.task_id,
                steps=[PlanStep(step_id=1, goal="读取目标文件", max_retries=0)],
            )

    tool = MissingThenSuccessfulFileTool()
    manager = ImmediateInteractionManager(
        [
            InteractionDecision(
                request_id="interaction_path",
                accepted=True,
                status="accepted",
                response="正确路径是 /tmp/input.md",
            )
        ]
    )
    state = AgentState(
        task_id="task_step_input",
        user_input="读取那个文件",
        task_type="summarize",
        intent="read_file",
        max_replans=0,
    )

    updated = run_minimal_loop(
        state,
        tool_registry={"file_tool": tool},
        planner=SingleStepPlanner(),
        interaction_manager=manager,
    )

    assert updated.status == "completed"
    assert tool.calls == 2
    assert "正确路径是 /tmp/input.md" in tool.inputs[1]


def test_loop_user_supplement_completes_missing_file_write_arguments(tmp_path):
    output_path = tmp_path / "supplemented.txt"
    manager = ImmediateInteractionManager(
        [
            InteractionDecision(
                request_id="interaction_file_write_arguments",
                accepted=True,
                status="accepted",
                response=f"文件路径是 {output_path}，内容是 hello",
            )
        ]
    )
    tool = FileWriteLangChainTool(
        authorization_manager=AutoApproveAuthorization(),
        enabled=True,
        allowed_roots=[tmp_path],
    )
    state = AgentState(
        task_id="task_supplement_file_write",
        user_input="创建文件",
        task_type="langchain_tool",
        workspace_path=str(tmp_path),
        max_replans=0,
    )

    updated = run_minimal_loop(
        state,
        tool_registry={
            "langchain_file_write_tool": LangChainToolAdapter(tool),
        },
        interaction_manager=manager,
    )

    assert updated.status == "completed"
    assert manager.requests[0]["kind"] == "step_input"
    assert output_path.read_text(encoding="utf-8") == "hello"
    assert len(updated.results) == 2
    assert updated.results[0].success is False
    assert updated.results[1].success is True


def test_loop_does_not_retry_step_after_empty_user_supplement():
    class MissingPathTool(BaseTool):
        name = "file_tool"
        description = "requires a path"

        def __init__(self):
            self.calls = 0

        def run(self, action_name, params):
            del action_name, params
            self.calls += 1
            raise FileNotFoundError("文件路径不存在")

    class SingleStepPlanner:
        def create_plan(self, task, matched_skill=None, failure_context=None, existing_plan=None):
            del matched_skill, failure_context, existing_plan
            return Plan(
                plan_id=f"plan_{task.task_id}",
                task_id=task.task_id,
                steps=[PlanStep(step_id=1, goal="读取文件", max_retries=0)],
            )

    manager = ImmediateInteractionManager(
        [
            InteractionDecision(
                request_id="interaction_empty_step_input",
                accepted=True,
                status="accepted",
                response="  ",
            )
        ]
    )
    tool = MissingPathTool()
    state = AgentState(
        task_id="task_empty_step_input",
        user_input="读取那个文件",
        task_type="summarize",
        max_replans=0,
    )

    updated = run_minimal_loop(
        state,
        tool_registry={"file_tool": tool},
        planner=SingleStepPlanner(),
        interaction_manager=manager,
    )

    assert updated.status == "failed"
    assert updated.final_output == "用户未提供当前步骤所需信息"
    assert tool.calls == 1


def test_loop_allows_user_to_edit_complex_plan_before_execution():
    class ConfirmablePlanner:
        def create_plan(self, task, matched_skill=None, failure_context=None, existing_plan=None):
            del matched_skill, failure_context, existing_plan
            return Plan(
                plan_id=f"plan_{task.task_id}",
                task_id=task.task_id,
                requires_confirmation=True,
                steps=[
                    PlanStep(step_id=1, goal="分析需求"),
                    PlanStep(step_id=2, goal="生成总结"),
                ],
            )

    manager = ImmediateInteractionManager(
        [
            InteractionDecision(
                request_id="interaction_plan",
                accepted=True,
                status="accepted",
                steps=["总结核心观点"],
            )
        ]
    )
    state = AgentState(
        task_id="task_confirm_plan",
        user_input="帮我完成复杂文本任务",
        task_type="complex_task",
        intent="execute_complex_task",
    )

    updated = run_minimal_loop(
        state,
        tool_registry={"text_tool": EchoTool("已完成总结")},
        planner=ConfirmablePlanner(),
        interaction_manager=manager,
    )

    assert updated.status == "completed"
    assert manager.requests[0]["kind"] == "plan_confirmation"
    assert updated.plan.source == "user_edited"
    assert [step.goal for step in updated.plan.steps] == ["总结核心观点"]


def test_apply_plan_edits_preserves_completed_prefix_and_clears_changed_bindings():
    plan = Plan(
        plan_id="plan_edit",
        task_id="task_edit",
        steps=[
            PlanStep(
                step_id=1,
                goal="读取输入",
                status="completed",
                tool_hint="file_tool",
                action_hint="read",
                inputs={"path": "README.md"},
                success_criteria=["读取成功"],
            ),
            PlanStep(
                step_id=2,
                goal="生成报告",
                tool_hint="report_tool",
                action_hint="generate",
                inputs={"format": "markdown"},
                depends_on=[1],
                success_criteria=["报告完成"],
                requires_authorization=True,
            ),
        ],
    )

    edited = _apply_plan_edits(plan, ["不要修改已完成步骤", "提取核心信息"])

    assert edited is True
    assert plan.steps[0].goal == "读取输入"
    assert plan.steps[0].status == "completed"
    assert plan.steps[0].tool_hint == "file_tool"
    assert plan.steps[1].goal == "提取核心信息"
    assert plan.steps[1].tool_hint is None
    assert plan.steps[1].action_hint is None
    assert plan.steps[1].inputs == {}
    assert plan.steps[1].depends_on == []
    assert plan.steps[1].success_criteria == []
    assert plan.steps[1].requires_authorization is False


def test_loop_rebinds_user_edited_step_to_new_safe_tool():
    class ConfirmablePlanner:
        def create_plan(self, task, matched_skill=None, failure_context=None, existing_plan=None):
            del matched_skill, failure_context, existing_plan
            return Plan(
                plan_id=f"plan_{task.task_id}",
                task_id=task.task_id,
                requires_confirmation=True,
                steps=[
                    PlanStep(
                        step_id=1,
                        goal="读取项目文件",
                        tool_hint="file_tool",
                        action_hint="read",
                        inputs={"path": "README.md"},
                    )
                ],
            )

    manager = ImmediateInteractionManager(
        [
            InteractionDecision(
                request_id="interaction_rebind",
                accepted=True,
                status="accepted",
                steps=["提取核心信息"],
            )
        ]
    )
    file_tool = CountingTool("不应读取")
    text_tool = CountingTool("已提取核心信息")
    state = AgentState(
        task_id="task_rebind",
        user_input="处理这段文字",
        task_type="complex_task",
    )

    updated = run_minimal_loop(
        state,
        tool_registry={"file_tool": file_tool, "text_tool": text_tool},
        planner=ConfirmablePlanner(),
        interaction_manager=manager,
    )

    assert updated.status == "completed"
    assert file_tool.calls == 0
    assert text_tool.calls == 1
    assert updated.results[0].tool_name == "text_tool"


def test_loop_requires_declared_success_criteria_before_completing_step():
    class CriteriaPlanner:
        def create_plan(self, task, matched_skill=None, failure_context=None, existing_plan=None):
            del matched_skill, failure_context, existing_plan
            return Plan(
                plan_id=f"plan_{task.task_id}",
                task_id=task.task_id,
                steps=[
                    PlanStep(
                        step_id=1,
                        goal="生成结论",
                        max_retries=0,
                        tool_hint="report_tool",
                        action_hint="generate",
                        success_criteria=["结果包含来源"],
                    )
                ],
            )

    state = AgentState(
        task_id="task_criteria_gate",
        user_input="生成结论",
        task_type="complex_task",
        max_replans=0,
    )

    updated = run_minimal_loop(
        state,
        tool_registry={"report_tool": EchoTool("只有结论，没有引用")},
        planner=CriteriaPlanner(),
    )

    assert updated.status == "failed"
    assert updated.plan.steps[0].status == "failed"
    assert updated.criterion_results[0].criterion == "结果包含来源"
    assert updated.criterion_results[0].passed is False
    assert "来源" in updated.checks[-1].failed_reasons[0]


def test_loop_passes_criterion_failures_to_replan_context():
    class CriteriaReplanner:
        def __init__(self):
            self.failure_context = None

        def create_plan(self, task, matched_skill=None, failure_context=None, existing_plan=None):
            del matched_skill, existing_plan
            if failure_context is None:
                return Plan(
                    plan_id=f"plan_{task.task_id}",
                    task_id=task.task_id,
                    steps=[
                        PlanStep(step_id=1, goal="读取输入", status="completed"),
                        PlanStep(
                            step_id=2,
                            goal="生成报告",
                            max_retries=0,
                            tool_hint="report_tool",
                            action_hint="generate",
                            success_criteria=["结果包含来源"],
                        ),
                    ],
                )
            self.failure_context = failure_context
            return Plan(
                plan_id=f"plan_{task.task_id}_replan",
                task_id=task.task_id,
                source="replan",
                steps=[
                    PlanStep(step_id=1, goal="读取输入", status="completed"),
                    PlanStep(
                        step_id=2,
                        goal="补齐来源",
                        tool_hint="report_tool",
                        action_hint="generate",
                        success_criteria=["结果包含来源"],
                    ),
                ],
            )

    planner = CriteriaReplanner()
    report = SequenceReportTool(["只有结论", "结论和来源：https://example.com"])
    state = AgentState(
        task_id="task_criteria_replan",
        user_input="生成报告",
        task_type="complex_task",
        max_replans=1,
    )
    state.results.append(
        ToolResult(True, "file_tool", "read", {"message": "input"}, step_id=1)
    )

    updated = run_minimal_loop(
        state,
        tool_registry={"report_tool": report},
        planner=planner,
    )

    assert updated.status == "completed"
    assert planner.failure_context is not None
    assert planner.failure_context["criterion_results"][0]["criterion"] == "结果包含来源"
    assert planner.failure_context["criterion_results"][0]["passed"] is False
    assert updated.replan_count == 1


def test_loop_resume_keeps_completed_criterion_results_without_reevaluating():
    state = AgentState(
        task_id="task_criteria_resume",
        user_input="继续任务",
        task_type="complex_task",
        status="running",
    )
    state.plan = Plan(
        plan_id="plan_task_criteria_resume",
        task_id=state.task_id,
        status="running",
        steps=[
            PlanStep(step_id=1, goal="读取输入", status="completed", success_criteria=["已读取"]),
            PlanStep(step_id=2, goal="生成结构化报告", status="pending"),
        ],
    )
    state.results.append(ToolResult(True, "file_tool", "read", {"message": "input"}, step_id=1))
    state.criterion_results.append(
        CriterionResult(
            task_id=state.task_id,
            plan_id=state.plan.plan_id,
            step_id=1,
            criterion="已读取",
            status="passed",
            passed=True,
            source="tool_result",
            evidence=[{"key": "message", "preview": "input"}],
        )
    )

    updated = run_minimal_loop(
        state,
        tool_registry={"report_tool": EchoTool("结果")},
    )

    assert updated.status == "completed"
    assert len([item for item in updated.criterion_results if item.step_id == 1]) == 1


def test_loop_user_edited_dangerous_goal_still_requests_tool_authorization(tmp_path):
    target = tmp_path / "edited-folder"

    class ConfirmablePlanner:
        def create_plan(self, task, matched_skill=None, failure_context=None, existing_plan=None):
            del matched_skill, failure_context, existing_plan
            return Plan(
                plan_id=f"plan_{task.task_id}",
                task_id=task.task_id,
                requires_confirmation=True,
                steps=[
                    PlanStep(
                        step_id=1,
                        goal="读取工作区",
                        max_retries=0,
                        tool_hint="file_tool",
                        action_hint="read",
                    )
                ],
            )

    manager = ImmediateInteractionManager(
        [
            InteractionDecision(
                request_id="interaction_dangerous_rebind",
                accepted=True,
                status="accepted",
                steps=[f"创建文件夹 {target}"],
            )
        ]
    )
    authorization = RecordingRejectAuthorization()
    dangerous_tool = DirectoryCreateLangChainTool(
        authorization_manager=authorization,
        enabled=True,
        allowed_roots=[tmp_path],
    )
    state = AgentState(
        task_id="task_dangerous_rebind",
        user_input=f"创建文件夹 {target}",
        task_type="langchain_tool",
        workspace_path=str(tmp_path),
        max_replans=0,
    )

    updated = run_minimal_loop(
        state,
        tool_registry={
            "file_tool": CountingTool("不应读取"),
            "langchain_directory_create_tool": LangChainToolAdapter(dangerous_tool),
        },
        planner=ConfirmablePlanner(),
        interaction_manager=manager,
    )

    assert updated.status == "failed"
    assert len(authorization.requests) == 1
    assert authorization.requests[0]["tool_name"] == "langchain_directory_create_tool"
    assert not target.exists()


def test_loop_stops_after_dangerous_tool_authorization_is_rejected(tmp_path):
    target = tmp_path / "rejected-folder"

    class DangerousPlanner:
        def create_plan(self, task, matched_skill=None, failure_context=None, existing_plan=None):
            del matched_skill, failure_context, existing_plan
            return Plan(
                plan_id=f"plan_{task.task_id}",
                task_id=task.task_id,
                steps=[
                    PlanStep(
                        step_id=1,
                        goal=f"创建文件夹 {target}",
                        max_retries=2,
                    )
                ],
            )

    authorization = RecordingRejectAuthorization()
    dangerous_tool = DirectoryCreateLangChainTool(
        authorization_manager=authorization,
        enabled=True,
        allowed_roots=[tmp_path],
    )
    state = AgentState(
        task_id="task_reject_dangerous_authorization",
        user_input=f"创建文件夹 {target}",
        task_type="langchain_tool",
        workspace_path=str(tmp_path),
        max_replans=1,
    )

    updated = run_minimal_loop(
        state,
        tool_registry={
            "langchain_directory_create_tool": LangChainToolAdapter(dangerous_tool),
        },
        planner=DangerousPlanner(),
    )

    assert updated.status == "failed"
    assert len(authorization.requests) == 1
    assert len(updated.results) == 1
    assert updated.replan_count == 0
    assert "用户拒绝授权" in updated.final_output
    assert not target.exists()


def test_loop_cancels_when_user_rejects_plan():
    class ConfirmablePlanner:
        def create_plan(self, task, matched_skill=None, failure_context=None, existing_plan=None):
            del matched_skill, failure_context, existing_plan
            return Plan(
                plan_id=f"plan_{task.task_id}",
                task_id=task.task_id,
                requires_confirmation=True,
                steps=[PlanStep(step_id=1, goal="总结核心观点")],
            )

    tool = CountingTool("不应执行")
    manager = ImmediateInteractionManager(
        [
            InteractionDecision(
                request_id="interaction_reject",
                accepted=False,
                status="rejected",
                response="先不执行",
            )
        ]
    )
    state = AgentState(
        task_id="task_reject_plan",
        user_input="帮我完成复杂任务",
        task_type="complex_task",
        intent="execute_complex_task",
    )

    updated = run_minimal_loop(
        state,
        tool_registry={"text_tool": tool},
        planner=ConfirmablePlanner(),
        interaction_manager=manager,
    )

    assert updated.status == "cancelled"
    assert updated.final_output == "用户取消了计划执行"
    assert tool.calls == 0


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
        "artifact_created",
        "verified",
        "step_done",
    ]
    assert events[0]["data"]["steps"][0] == {"step_id": 1, "goal": "读取输入内容"}
    assert events[2]["data"]["tool_name"] == "file_tool"
    assert events[4]["data"]["passed"] is True


def test_loop_persists_and_emits_file_change_and_artifact_evidence(tmp_path):
    output = tmp_path / "result.txt"
    state = AgentState(
        task_id="task_evidence",
        user_input=f"创建文件 {output}",
        task_type="langchain_tool",
        intent="write_file",
        workspace_path=str(tmp_path),
    )
    events = []

    updated = run_minimal_loop(
        state,
        tool_registry={"langchain_file_write_tool": EvidenceWriteTool(output)},
        on_progress=events.append,
    )

    assert updated.status == "completed"
    assert updated.evidence["changes"][0]["path"] == str(output.resolve())
    assert updated.evidence["changes"][0]["change_type"] == "created"
    assert updated.evidence["artifacts"][0]["path"] == str(output.resolve())
    assert [event["type"] for event in events if event["type"] in {"file_changed", "artifact_created"}] == [
        "file_changed",
        "artifact_created",
    ]


def test_loop_real_file_write_produces_verified_evidence(tmp_path):
    output = tmp_path / "written.txt"
    tool = FileWriteLangChainTool(
        authorization_manager=AutoApproveAuthorization(),
        enabled=True,
        allowed_roots=[tmp_path],
    )
    state = AgentState(
        task_id="task_real_write",
        user_input=f"写入文件 {output} 内容 真实写入",
        task_type="langchain_tool",
        intent="write_file",
        workspace_path=str(tmp_path),
    )

    updated = run_minimal_loop(
        state,
        tool_registry={"langchain_file_write_tool": LangChainToolAdapter(tool)},
    )

    assert updated.status == "completed"
    assert output.read_text(encoding="utf-8") == "真实写入"
    assert updated.evidence["changes"][0]["change_type"] == "created"
    assert updated.evidence["artifacts"][0]["verified"] is True


def test_loop_real_directory_create_records_existing_directory(tmp_path):
    target = tmp_path / "evidence-folder"
    tool = DirectoryCreateLangChainTool(
        authorization_manager=AutoApproveAuthorization(),
        enabled=True,
        allowed_roots=[tmp_path],
    )
    state = AgentState(
        task_id="task_real_directory",
        user_input=f"创建文件夹 {target}",
        task_type="langchain_tool",
        intent="create_directory",
        workspace_path=str(tmp_path),
    )

    updated = run_minimal_loop(
        state,
        tool_registry={"langchain_directory_create_tool": LangChainToolAdapter(tool)},
    )

    assert updated.status == "completed"
    assert target.is_dir()
    assert any(item["path"] == str(target.resolve()) for item in updated.evidence["changes"])


def test_loop_real_file_delete_records_trash_restore_path(tmp_path):
    target = tmp_path / "delete-me.txt"
    target.write_text("delete", encoding="utf-8")
    trash_root = tmp_path / "uta-trash"
    tool = FileDeleteLangChainTool(
        authorization_manager=AutoApproveAuthorization(),
        enabled=True,
        allowed_roots=[tmp_path],
        trash_root=trash_root,
    )
    state = AgentState(
        task_id="task_real_delete",
        user_input=f"删除文件 {target}",
        task_type="langchain_tool",
        intent="delete_file",
        workspace_path=str(tmp_path),
    )

    updated = run_minimal_loop(
        state,
        tool_registry={"langchain_file_delete_tool": LangChainToolAdapter(tool)},
    )

    assert updated.status == "completed"
    assert not target.exists()
    deleted = next(item for item in updated.evidence["changes"] if item["change_type"] == "deleted")
    assert deleted["restore_path"]
    assert Path(deleted["restore_path"]).exists()


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


def test_loop_passes_failure_evidence_to_replanner_and_uses_changed_step():
    class CapturingReplanner:
        def __init__(self):
            self.failure_context = None
            self.existing_plan = None

        def create_plan(self, task, matched_skill=None, failure_context=None, existing_plan=None):
            del matched_skill
            if failure_context is None:
                return Plan(
                    plan_id=f"plan_{task.task_id}",
                    task_id=task.task_id,
                    steps=[
                        PlanStep(step_id=1, goal="读取输入内容"),
                        PlanStep(step_id=2, goal="提取核心信息", max_retries=0),
                        PlanStep(step_id=3, goal="生成结构化报告"),
                    ],
                )
            self.failure_context = failure_context
            self.existing_plan = existing_plan
            return Plan(
                plan_id=f"plan_{task.task_id}_replan",
                task_id=task.task_id,
                source="replan",
                steps=[
                    PlanStep(step_id=1, goal="读取输入内容", status="completed"),
                    PlanStep(step_id=2, goal="重新提取核心信息并补齐小节"),
                    PlanStep(step_id=3, goal="生成结构化报告"),
                ],
            )

    planner = CapturingReplanner()
    file_tool = CountingTool("file")
    text_tool = SequenceTextTool(
        [
            "## 摘要\n缺少小节。",
            VALID_SUMMARY_REPORT,
        ]
    )
    registry = {
        "file_tool": file_tool,
        "text_tool": text_tool,
        "report_tool": EchoTool(VALID_SUMMARY_REPORT),
    }
    state = AgentState(
        task_id="task_replan_context",
        user_input="帮我总结",
        task_type="summarize",
        intent="summarize_article",
        max_replans=1,
    )
    state.evidence["files"].append({"path": "input.md", "step_id": 1})

    updated = run_minimal_loop(state, tool_registry=registry, planner=planner)

    assert updated.status == "completed"
    assert file_tool.calls == 1
    assert planner.failure_context is not None
    assert planner.failure_context["failed_step_id"] == 2
    assert planner.failure_context["failed_reasons"]
    assert planner.failure_context["completed_steps"][0]["step_id"] == 1
    assert planner.failure_context["evidence"]["files"]
    assert planner.existing_plan is not None
    assert updated.plan.source == "replan"
    assert updated.plan.steps[1].goal == "重新提取核心信息并补齐小节"


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


def test_loop_resumes_legacy_checkpoint_without_rerunning_completed_steps():
    file_tool = CountingTool("file")
    text_tool = CountingTool(VALID_SUMMARY_REPORT)
    report_tool = CountingTool(VALID_SUMMARY_REPORT)
    registry = {
        "file_tool": file_tool,
        "text_tool": text_tool,
        "report_tool": report_tool,
    }
    state = AgentState.from_dict(
        {
            "task_id": "task_legacy_resume",
            "user_input": "帮我总结",
            "task_type": "summarize",
            "status": "running",
            "current_step_id": 2,
            "plan": {
                "plan_id": "plan_task_legacy_resume",
                "task_id": "task_legacy_resume",
                "status": "running",
                "steps": [
                    {"step_id": 1, "goal": "读取输入内容", "status": "completed"},
                    {"step_id": 2, "goal": "提取核心信息", "status": "running"},
                    {"step_id": 3, "goal": "生成结构化报告", "status": "pending"},
                ],
            },
            "results": [
                {
                    "success": True,
                    "tool_name": "file_tool",
                    "action_name": "read",
                    "result": {"message": "旧 checkpoint 已读取"},
                    "step_id": 1,
                }
            ],
        }
    )

    updated = run_minimal_loop(state, tool_registry=registry)

    assert updated.status == "completed"
    assert file_tool.calls == 0
    assert text_tool.calls == 1
    assert report_tool.calls == 1


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

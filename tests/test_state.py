import json

from core.state import (
    Action,
    AgentState,
    CheckResult,
    CriterionResult,
    Plan,
    PlanStep,
    ToolResult,
)


def test_agent_state_exports_nested_dataclasses_to_json_dict():
    state = AgentState(
        task_id="task_test",
        user_input="帮我总结一段文本",
        task_type="summarize",
        intent="v0.1 hard-coded summarize skeleton",
    )
    state.plan = Plan(
        plan_id="plan_task_test",
        task_id="task_test",
        steps=[PlanStep(step_id=1, goal="执行 V0.1 mock 工具", status="completed")],
        status="completed",
    )
    state.current_action = Action(
        action_id="action_task_test_1",
        step_id=1,
        tool_name="mock_tool",
        action_name="run",
        params={"user_input": state.user_input},
        reason="V0.1 uses a hard-coded mock action",
    )
    state.results.append(
        ToolResult(
            success=True,
            tool_name="mock_tool",
            action_name="run",
            result={"message": "mock result"},
        )
    )
    state.checks.append(CheckResult(passed=True, failed_reasons=[], suggested_fix=[]))

    exported = state.to_dict()

    assert exported["task_id"] == "task_test"
    assert exported["task_type"] == "summarize"
    assert exported["plan"]["steps"][0]["goal"] == "执行 V0.1 mock 工具"
    assert exported["results"][0]["result"]["message"] == "mock result"
    json.dumps(exported, ensure_ascii=False)


def test_agent_state_can_save_json(tmp_path):
    state = AgentState(task_id="task_test", user_input="帮我总结一段文本")

    output_path = state.save_json(tmp_path)

    assert output_path.name == "task_test_state.json"
    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved["task_id"] == "task_test"


def test_agent_state_includes_memory_saved_flag():
    state = AgentState(task_id="task_test", user_input="测试")

    assert state.memory_saved is False
    assert state.to_dict()["memory_saved"] is False


def test_agent_state_exports_replan_tracking_fields():
    state = AgentState(task_id="task_test", user_input="测试")
    state.replan_count = 1
    state.replan_events.append({"failed_step_id": 2, "resume_step_id": 2})

    exported = state.to_dict()

    assert exported["replan_count"] == 1
    assert exported["replan_events"] == [{"failed_step_id": 2, "resume_step_id": 2}]


def test_agent_state_round_trips_task_evidence():
    state = AgentState(task_id="task_evidence", user_input="读取并写入文件")
    state.evidence["files"].append(
        {"path": "/tmp/input.md", "operation": "read", "tool_name": "file_tool", "step_id": 1}
    )
    state.evidence["changes"].append(
        {"path": "/tmp/output.md", "change_type": "created", "tool_name": "write", "step_id": 2}
    )
    state.evidence["artifacts"].append(
        {"artifact_id": "artifact-1", "kind": "file", "path": "/tmp/output.md", "verified": True}
    )

    restored = AgentState.from_dict(state.to_dict())

    assert restored.evidence == state.evidence


def test_agent_state_round_trips_structured_plan_and_task_context():
    state = AgentState(
        task_id="task_structured",
        user_input="分析报表后生成报告",
        constraints=["不要修改原始文件"],
        missing_info=["输出文件名"],
    )
    state.plan = Plan(
        plan_id="plan_task_structured",
        task_id=state.task_id,
        source="model",
        requires_confirmation=True,
        reason="任务包含多步文件操作",
        steps=[
            PlanStep(
                step_id=1,
                goal="读取表格",
                tool_hint="file_tool",
                action_hint="read",
                inputs={"path": "report.csv"},
                depends_on=[],
                success_criteria=["已获得表格内容"],
                requires_authorization=False,
            ),
            PlanStep(
                step_id=2,
                goal="生成分析报告",
                tool_hint="report_tool",
                action_hint="generate",
                inputs={"format": "markdown"},
                depends_on=[1],
                success_criteria=["报告包含结论和依据"],
                requires_authorization=False,
            ),
        ],
    )

    restored = AgentState.from_dict(state.to_dict())

    assert restored.constraints == ["不要修改原始文件"]
    assert restored.missing_info == ["输出文件名"]
    assert restored.plan is not None
    assert restored.plan.source == "model"
    assert restored.plan.requires_confirmation is True
    assert restored.plan.reason == "任务包含多步文件操作"
    assert restored.plan.steps[0].tool_hint == "file_tool"
    assert restored.plan.steps[0].inputs == {"path": "report.csv"}
    assert restored.plan.steps[1].depends_on == [1]
    assert restored.plan.steps[1].success_criteria == ["报告包含结论和依据"]


def test_agent_state_round_trip_preserves_disabled_retry_budgets():
    state = AgentState(
        task_id="task_no_retry",
        user_input="只执行一次",
        max_replans=0,
    )
    state.plan = Plan(
        plan_id="plan_no_retry",
        task_id=state.task_id,
        steps=[PlanStep(step_id=1, goal="执行操作", max_retries=0)],
    )

    restored = AgentState.from_dict(state.to_dict())

    assert restored.max_replans == 0
    assert restored.plan is not None
    assert restored.plan.steps[0].max_retries == 0


def test_agent_state_round_trips_pending_interaction_and_history():
    state = AgentState(task_id="task_interaction", user_input="处理文件")
    state.pending_interaction = {
        "request_id": "interaction_missing_path",
        "task_id": state.task_id,
        "kind": "missing_info",
        "payload": {"question": "请提供文件路径"},
        "status": "pending",
        "created_at": "2026-07-14T06:00:00",
    }
    state.interaction_history.append(
        {
            "request_id": "interaction_plan",
            "task_id": state.task_id,
            "kind": "plan_confirmation",
            "status": "accepted",
            "accepted": True,
            "response": "确认执行",
            "decided_at": "2026-07-14T06:01:00",
        }
    )

    restored = AgentState.from_dict(state.to_dict())

    assert restored.pending_interaction == {
        "request_id": "interaction_missing_path",
        "task_id": "task_interaction",
        "kind": "missing_info",
        "payload": {"question": "请提供文件路径"},
        "status": "pending",
        "created_at": "2026-07-14T06:00:00",
    }
    assert restored.interaction_history == [
        {
            "request_id": "interaction_plan",
            "task_id": "task_interaction",
            "kind": "plan_confirmation",
            "status": "accepted",
            "accepted": True,
            "response": "确认执行",
            "decided_at": "2026-07-14T06:01:00",
        }
    ]


def test_agent_state_round_trips_step_criterion_results():
    state = AgentState(task_id="task_criteria", user_input="创建报告")
    state.criterion_results.append(
        CriterionResult(
            task_id=state.task_id,
            plan_id="plan_task_criteria",
            step_id=2,
            criterion="报告文件已经创建",
            status="failed",
            passed=False,
            source="deterministic",
            evidence=[{"path": "/tmp/report.md", "exists": False}],
            failure_reason="目标文件不存在",
        )
    )

    restored = AgentState.from_dict(state.to_dict())

    assert restored.criterion_results == state.criterion_results
    assert restored.criterion_results[0].plan_id == "plan_task_criteria"
    assert restored.criterion_results[0].step_id == 2
    assert restored.criterion_results[0].status == "failed"
    assert restored.criterion_results[0].evidence[0]["exists"] is False


def test_agent_state_loads_legacy_checkpoint_without_new_release_fields():
    restored = AgentState.from_dict(
        {
            "task_id": "task_legacy",
            "user_input": "继续旧任务",
            "status": "waiting_user",
            "plan": {
                "plan_id": "plan_task_legacy",
                "task_id": "task_legacy",
                "steps": [
                    {"step_id": 1, "goal": "读取输入", "status": "completed"},
                    {"step_id": 2, "goal": "生成输出", "status": "running"},
                ],
            },
            "pending_interaction": {
                "kind": "missing_info",
                "question": "请补充路径",
            },
        }
    )

    assert restored.criterion_results == []
    assert restored.plan is not None
    assert restored.plan.steps[0].status == "completed"
    assert restored.pending_interaction == {
        "kind": "missing_info",
        "question": "请补充路径",
    }

import json

from core.state import Action, AgentState, CheckResult, Plan, PlanStep, ToolResult


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

from core.loop import run_minimal_loop
from core.state import AgentState


def test_minimal_loop_completes_state_with_mock_result():
    state = AgentState(
        task_id="task_test",
        user_input="帮我总结一段文本",
        task_type="summarize",
        intent="v0.1 hard-coded summarize skeleton",
    )

    updated = run_minimal_loop(state)

    assert updated.status == "completed"
    assert updated.current_step_id == 1
    assert updated.plan.status == "completed"
    assert updated.plan.steps[0].status == "completed"
    assert updated.current_action.tool_name == "mock_tool"
    assert len(updated.results) == 1
    assert updated.results[0].result["message"] == "mock result"
    assert len(updated.checks) == 1
    assert updated.checks[0].passed is True
    assert updated.final_output == "mock result"

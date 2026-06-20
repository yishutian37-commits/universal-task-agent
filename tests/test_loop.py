from core.loop import run_minimal_loop
from core.state import AgentState


def test_minimal_loop_keeps_unknown_task_fallback_with_mock_result():
    state = AgentState(
        task_id="task_test",
        user_input="做一个未知任务",
        task_type="unknown",
        intent="unknown fallback",
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


def test_loop_executes_full_planned_summary_flow():
    state = AgentState(
        task_id="task_test",
        user_input="帮我总结",
        task_type="summarize",
        intent="summarize_article",
    )

    updated = run_minimal_loop(state)

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

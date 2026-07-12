from core.checkpoint_store import CheckpointStore
from core.state import Action, AgentState, CheckResult, Plan, PlanStep, ToolResult


def test_checkpoint_store_round_trips_agent_state(tmp_path):
    store = CheckpointStore(tmp_path)
    state = AgentState(
        task_id="task_20260708_120000_000001",
        user_input="帮我总结刚才提到的项目",
        execution_input="以下是同一对话前文：项目叫 UTA。\n\n当前用户输入：帮我总结刚才提到的项目",
        conversation_id="conv_20260708_120000_000001",
        workspace_path=str(tmp_path / "workspace"),
        task_type="summarize",
        intent="summarize_article",
        status="running",
        current_step_id=2,
    )
    state.plan = Plan(
        plan_id="plan_task_20260708_120000_000001",
        task_id=state.task_id,
        steps=[
            PlanStep(step_id=1, goal="读取输入内容", status="completed"),
            PlanStep(step_id=2, goal="提取核心信息", status="running"),
        ],
        status="running",
    )
    state.current_action = Action(
        action_id="action_task_20260708_120000_000001_2",
        step_id=2,
        tool_name="text_tool",
        action_name="process",
        params={"user_input": state.execution_input},
        reason="规则命中",
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
    state.checks.append(CheckResult(passed=True, failed_reasons=[], suggested_fix=[]))

    saved_path = store.save(state)
    loaded = store.load(state.task_id)

    assert saved_path.name == f"{state.task_id}.json"
    assert loaded is not None
    assert loaded.task_id == state.task_id
    assert loaded.user_input == "帮我总结刚才提到的项目"
    assert loaded.execution_input.startswith("以下是同一对话前文")
    assert loaded.conversation_id == "conv_20260708_120000_000001"
    assert loaded.workspace_path == str(tmp_path / "workspace")
    assert loaded.plan.steps[0].status == "completed"
    assert loaded.current_action.tool_name == "text_tool"
    assert loaded.results[0].result["message"] == "file"
    assert loaded.checks[0].passed is True


def test_checkpoint_store_rejects_unsafe_task_id(tmp_path):
    store = CheckpointStore(tmp_path)

    assert store.load("../bad") is None

from core.executor import Executor
from core.state import Action, AgentState, Plan, PlanStep
from core.verifier import Verifier


def create_v0_1_plan(task_id: str) -> Plan:
    return Plan(
        plan_id=f"plan_{task_id}",
        task_id=task_id,
        steps=[PlanStep(step_id=1, goal="执行 V0.1 mock 工具")],
    )


def create_v0_1_action(state: AgentState) -> Action:
    return Action(
        action_id=f"action_{state.task_id}_1",
        step_id=1,
        tool_name="mock_tool",
        action_name="run",
        params={"user_input": state.user_input},
        reason="V0.1 uses a hard-coded mock action",
    )


def run_minimal_loop(state: AgentState) -> AgentState:
    state.plan = create_v0_1_plan(state.task_id)
    step = state.plan.steps[0]
    state.current_step_id = step.step_id
    state.status = "running"
    step.status = "running"

    action = create_v0_1_action(state)
    state.current_action = action

    result = Executor().run(action)
    state.results.append(result)

    check = Verifier().check(result)
    state.checks.append(check)

    if check.passed:
        step.status = "completed"
        state.plan.status = "completed"
        state.status = "completed"
        state.final_output = result.result.get("message", "")
    else:
        step.status = "failed"
        state.plan.status = "failed"
        state.status = "failed"
        state.final_output = result.error

    state.touch()
    return state

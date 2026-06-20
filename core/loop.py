from core.executor import Executor
from core.planner import Planner
from core.router import Router
from core.state import AgentState, Task
from core.verifier import Verifier


def _task_from_state(state: AgentState) -> Task:
    return Task(
        task_id=state.task_id,
        user_input=state.user_input,
        task_type=state.task_type,
        intent=state.intent,
        input_type="unknown",
        expected_output="unknown",
    )


def run_minimal_loop(state: AgentState, tool_registry=None) -> AgentState:
    planner = Planner()
    router = Router()
    executor = Executor(tool_registry)
    verifier = Verifier()

    state.plan = planner.create_plan(_task_from_state(state))
    state.plan.status = "running"
    state.status = "running"

    for step in state.plan.steps:
        state.current_step_id = step.step_id
        step.status = "running"

        action = router.choose_tool(state, step)
        state.current_action = action

        result = executor.run(action)
        state.results.append(result)

        check = verifier.check(result)
        state.checks.append(check)

        step.status = "completed"
        if not check.passed:
            step.status = "failed"
            state.plan.status = "failed"
            state.status = "failed"
            state.final_output = result.error
            state.touch()
            return state

    if state.results:
        state.final_output = state.results[-1].result.get("message", "")

    if all(step.status == "completed" for step in state.plan.steps):
        state.plan.status = "completed"
        state.status = "completed"
    else:
        step.status = "failed"
        state.plan.status = "failed"
        state.status = "failed"

    state.touch()
    return state

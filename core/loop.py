from core.executor import Executor
from core.planner import Planner
from core.reflection import Reflection
from core.router import Router
from core.state import AgentState, Task
from core.verifier import Verifier


def _emit_progress(on_progress, event_type: str, state: AgentState, data: dict) -> None:
    if on_progress is None:
        return
    on_progress(
        {
            "type": event_type,
            "task_id": state.task_id,
            "data": data,
        }
    )


def _task_from_state(state: AgentState) -> Task:
    return Task(
        task_id=state.task_id,
        user_input=state.user_input,
        task_type=state.task_type,
        intent=state.intent,
        input_type="unknown",
        expected_output="unknown",
    )


def run_minimal_loop(state: AgentState, tool_registry=None, on_progress=None) -> AgentState:
    planner = Planner()
    router = Router()
    executor = Executor(tool_registry)
    verifier = Verifier()
    reflection = Reflection()

    state.plan = planner.create_plan(_task_from_state(state), matched_skill=state.matched_skill)
    state.plan.status = "running"
    state.status = "running"
    _emit_progress(
        on_progress,
        "plan_created",
        state,
        {
            "steps": [
                {"step_id": step.step_id, "goal": step.goal}
                for step in state.plan.steps
            ]
        },
    )

    for step in state.plan.steps:
        feedback = None
        attempt = 0
        previous_step_result = state.results[-1].result if state.results else None

        while attempt <= step.max_retries:
            state.current_step_id = step.step_id
            step.status = "running"
            _emit_progress(
                on_progress,
                "step_started",
                state,
                {
                    "step_id": step.step_id,
                    "goal": step.goal,
                    "attempt": attempt + 1,
                    "max_retries": step.max_retries,
                },
            )

            action = router.choose_tool(state, step)
            action.params["previous_result"] = previous_step_result
            if feedback is not None:
                action.params["feedback"] = feedback
            state.current_action = action
            _emit_progress(
                on_progress,
                "tool_selected",
                state,
                {
                    "step_id": step.step_id,
                    "tool_name": action.tool_name,
                    "action_name": action.action_name,
                    "reason": action.reason,
                },
            )

            result = executor.run(action)
            state.results.append(result)
            _emit_progress(
                on_progress,
                "tool_executed",
                state,
                {
                    "step_id": step.step_id,
                    "tool_name": result.tool_name,
                    "success": result.success,
                    "error": result.error,
                },
            )

            check = verifier.check(state, step, result)
            state.checks.append(check)
            _emit_progress(
                on_progress,
                "verified",
                state,
                {
                    "step_id": step.step_id,
                    "passed": check.passed,
                    "failed_reasons": check.failed_reasons,
                },
            )

            if check.passed:
                step.status = "completed"
                _emit_progress(
                    on_progress,
                    "step_done",
                    state,
                    {"step_id": step.step_id, "status": step.status},
                )
                break

            feedback = reflection.analyze(state, step, result, check)
            state.feedbacks.append(feedback)
            _emit_progress(
                on_progress,
                "reflection",
                state,
                {
                    "step_id": step.step_id,
                    "failure_type": feedback.failure_type,
                    "repair_strategy": feedback.repair_strategy,
                },
            )
            attempt += 1

        if step.status != "completed":
            step.status = "failed"
            state.plan.status = "failed"
            state.status = "failed"
            state.final_output = "；".join(state.checks[-1].failed_reasons)
            state.touch()
            _emit_progress(
                on_progress,
                "step_done",
                state,
                {"step_id": step.step_id, "status": step.status},
            )
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

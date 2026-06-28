import json

from core.executor import Executor
from core.planner import Planner
from core.reflection import Reflection
from core.router import Router
from core.state import AgentState, Feedback, Plan, PlanStep, Task, ToolResult
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


def _plan_goals(plan: Plan | None) -> list[str]:
    if plan is None:
        return []
    return [step.goal for step in plan.steps]


def _result_text(result: ToolResult | None) -> str:
    if result is None:
        return "未生成可展示结果。"
    if not result.success:
        return f"失败：{result.error or 'unknown error'}"

    for key in ("message", "report_markdown", "summary_markdown"):
        value = result.result.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    if result.result:
        return "```json\n" + json.dumps(result.result, ensure_ascii=False, indent=2) + "\n```"
    return "未生成可展示结果。"


def _results_by_step(results: list[ToolResult]) -> dict[int, ToolResult]:
    mapped = {}
    for result in results:
        if result.step_id is None:
            continue
        if result.success or result.step_id not in mapped:
            mapped[result.step_id] = result
    return mapped


def _complex_task_output(state: AgentState) -> str:
    steps = state.plan.steps if state.plan is not None else []
    results_by_step = _results_by_step(state.results)
    failed = sum(1 for step in steps if step.status == "failed")

    lines = ["## 分步结果", ""]
    for step in steps:
        lines.append(f"### {step.step_id}. {step.goal}")
        lines.append(_result_text(results_by_step.get(step.step_id)))
        lines.append("")

    if failed:
        lines.extend(["## 执行异常", ""])
        reasons = state.checks[-1].failed_reasons if state.checks else []
        lines.append(f"失败 {failed} 个步骤。")
        if reasons:
            lines.append("失败原因：" + "；".join(reasons))
    return "\n".join(lines)


def _record_replan(
    state: AgentState,
    failed_step: PlanStep,
    feedback: Feedback,
    old_plan: Plan | None,
    new_plan: Plan,
    resume_step_id: int,
) -> dict:
    state.touch()
    event = {
        "failed_step_id": failed_step.step_id,
        "failed_goal": failed_step.goal,
        "root_cause": feedback.root_cause,
        "repair_strategy": feedback.repair_strategy,
        "old_plan_goals": _plan_goals(old_plan),
        "new_plan_goals": _plan_goals(new_plan),
        "resume_step_id": resume_step_id,
        "created_at": state.updated_at,
    }
    state.replan_count += 1
    state.replan_events.append(event)
    return event


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

    completed_step_results = {}
    step_index = 0
    while step_index < len(state.plan.steps):
        step = state.plan.steps[step_index]
        feedback = None
        attempt = 0
        previous_step_result = completed_step_results.get(step.step_id - 1)

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
                completed_step_results[step.step_id] = result.result
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
            if feedback is not None and state.replan_count < state.max_replans:
                feedback.need_replan = True
                old_plan = state.plan
                new_plan = planner.create_plan(_task_from_state(state), matched_skill=state.matched_skill)
                new_plan.status = "running"
                resume_index = step_index
                if resume_index >= len(new_plan.steps):
                    step.status = "failed"
                    state.plan.status = "failed"
                    state.status = "failed"
                    if state.task_type == "complex_task":
                        state.final_output = _complex_task_output(state)
                    else:
                        state.final_output = "replan 后没有可继续执行的步骤"
                    state.touch()
                    return state

                for completed_index in range(resume_index):
                    new_plan.steps[completed_index].status = "completed"

                state.plan = new_plan
                state.current_step_id = new_plan.steps[resume_index].step_id
                event = _record_replan(
                    state,
                    step,
                    feedback,
                    old_plan,
                    new_plan,
                    new_plan.steps[resume_index].step_id,
                )
                _emit_progress(on_progress, "replanned", state, event)
                step_index = resume_index
                continue

            step.status = "failed"
            state.plan.status = "failed"
            state.status = "failed"
            if state.task_type == "complex_task":
                state.final_output = _complex_task_output(state)
            else:
                state.final_output = "；".join(state.checks[-1].failed_reasons)
            state.touch()
            _emit_progress(
                on_progress,
                "step_done",
                state,
                {"step_id": step.step_id, "status": step.status},
            )
            return state

        step_index += 1

    if state.task_type == "complex_task":
        state.final_output = _complex_task_output(state)
    elif state.results:
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

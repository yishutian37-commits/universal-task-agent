import json
import re

from core.evidence import (
    artifacts_from_changes,
    collect_tool_evidence,
    diff_workspace_snapshots,
    merge_evidence,
    should_snapshot_tool,
    snapshot_workspace,
)
from core.executor import Executor
from core.planner import Planner
from core.reflection import Reflection
from core.router import Router
from core.state import AgentState, Feedback, Plan, PlanStep, Task, ToolResult
from core.verifier import Verifier


def _save_checkpoint(checkpoint_store, state: AgentState) -> None:
    if checkpoint_store is not None:
        checkpoint_store.save(state)


def _emit_progress(on_progress, event_type: str, state: AgentState, data: dict, checkpoint_store=None) -> None:
    _save_checkpoint(checkpoint_store, state)
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
        user_input=state.execution_input or state.user_input,
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
            return _unwrap_markdown_fence(value)

    if result.result:
        return "```json\n" + json.dumps(result.result, ensure_ascii=False, indent=2) + "\n```"
    return "未生成可展示结果。"


def _unwrap_markdown_fence(value: str) -> str:
    text = value.strip()
    match = re.fullmatch(r"```(?:markdown|md)?[ \t]*\r?\n(.*?)\r?\n```", text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text


def _results_by_step(results: list[ToolResult]) -> dict[int, ToolResult]:
    mapped = {}
    for result in results:
        if result.step_id is None:
            continue
        if result.success or result.step_id not in mapped:
            mapped[result.step_id] = result
    return mapped


def _completed_step_results(results: list[ToolResult]) -> dict[int, dict]:
    return {
        step_id: result.result
        for step_id, result in _results_by_step(results).items()
        if result.success
    }


def _resume_step_index(plan: Plan) -> int:
    for index, step in enumerate(plan.steps):
        if step.status != "completed":
            return index
    return len(plan.steps)


def _normalize_resumed_plan(plan: Plan) -> None:
    for step in plan.steps:
        if step.status == "running":
            step.status = "pending"


def _is_unsupported_result(result: ToolResult | None) -> bool:
    return result is not None and result.tool_name == "unsupported_task"


def _record_tool_evidence(state: AgentState, action, result, before_snapshot) -> dict[str, list[dict]]:
    incoming = collect_tool_evidence(action, result, workspace_path=state.workspace_path)
    if before_snapshot is not None and state.workspace_path:
        snapshot_changes = diff_workspace_snapshots(
            before_snapshot,
            snapshot_workspace(state.workspace_path),
            state.workspace_path,
            tool_name=result.tool_name,
            step_id=result.step_id,
        )
        incoming["changes"] = snapshot_changes + incoming["changes"]
        incoming["artifacts"] = artifacts_from_changes(snapshot_changes) + incoming["artifacts"]
    return merge_evidence(state.evidence, incoming)


def _emit_evidence_events(on_progress, state: AgentState, added: dict[str, list[dict]], checkpoint_store=None) -> None:
    event_types = {
        "files": "file_recorded",
        "changes": "file_changed",
        "artifacts": "artifact_created",
    }
    for bucket, event_type in event_types.items():
        for record in added.get(bucket, []):
            _emit_progress(on_progress, event_type, state, record, checkpoint_store=checkpoint_store)


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


def run_minimal_loop(state: AgentState, tool_registry=None, on_progress=None, checkpoint_store=None) -> AgentState:
    planner = Planner()
    router = Router()
    executor = Executor(tool_registry)
    verifier = Verifier()
    reflection = Reflection()

    if state.plan is None:
        state.plan = planner.create_plan(_task_from_state(state), matched_skill=state.matched_skill)
        state.plan.status = "running"
        event_type = "plan_created"
        resume_step_id = None
    else:
        _normalize_resumed_plan(state.plan)
        state.plan.status = "running"
        resume_index = _resume_step_index(state.plan)
        resume_step_id = (
            state.plan.steps[resume_index].step_id
            if resume_index < len(state.plan.steps)
            else None
        )
        event_type = "plan_resumed"
    state.status = "running"
    _emit_progress(
        on_progress,
        event_type,
        state,
        {
            "steps": [
                {"step_id": step.step_id, "goal": step.goal}
                for step in state.plan.steps
            ],
            "resume_step_id": resume_step_id,
        },
        checkpoint_store=checkpoint_store,
    )

    completed_step_results = _completed_step_results(state.results)
    step_index = _resume_step_index(state.plan)
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
                checkpoint_store=checkpoint_store,
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
                checkpoint_store=checkpoint_store,
            )

            before_snapshot = (
                snapshot_workspace(state.workspace_path)
                if state.workspace_path and should_snapshot_tool(action.tool_name)
                else None
            )
            result = executor.run(action)
            state.results.append(result)
            added_evidence = _record_tool_evidence(state, action, result, before_snapshot)
            _emit_progress(
                on_progress,
                "tool_executed",
                state,
                {
                    "step_id": step.step_id,
                    "tool_name": result.tool_name,
                    "success": result.success,
                    "error": result.error,
                    "evidence_counts": {key: len(value) for key, value in added_evidence.items()},
                },
                checkpoint_store=checkpoint_store,
            )
            _emit_evidence_events(on_progress, state, added_evidence, checkpoint_store=checkpoint_store)

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
                checkpoint_store=checkpoint_store,
            )

            if check.passed:
                step.status = "completed"
                completed_step_results[step.step_id] = result.result
                _emit_progress(
                    on_progress,
                    "step_done",
                    state,
                    {"step_id": step.step_id, "status": step.status},
                    checkpoint_store=checkpoint_store,
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
                checkpoint_store=checkpoint_store,
            )
            attempt += 1

        if step.status != "completed":
            if feedback is not None and state.replan_count < state.max_replans and not _is_unsupported_result(result):
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
                _emit_progress(on_progress, "replanned", state, event, checkpoint_store=checkpoint_store)
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
                checkpoint_store=checkpoint_store,
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
    _save_checkpoint(checkpoint_store, state)
    return state

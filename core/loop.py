import json
import re
import uuid
from dataclasses import replace

from core.evidence import (
    artifacts_from_changes,
    collect_tool_evidence,
    diff_workspace_snapshots,
    merge_evidence,
    should_snapshot_tool,
    snapshot_workspace,
)
from core.executor import Executor
from core.interaction import InteractionDecision
from core.planner import Planner
from core.reflection import Reflection
from core.router import Router
from core.state import AgentState, Feedback, Plan, PlanStep, Task, ToolResult, dataclass_to_dict
from core.tool_catalog import DANGEROUS_TOOL_NAMES, build_tool_catalog
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
        constraints=list(state.constraints),
        missing_info=list(state.missing_info),
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


def _is_terminal_authorization_failure(result: ToolResult | None) -> bool:
    if result is None or result.success or result.tool_name not in DANGEROUS_TOOL_NAMES:
        return False
    error = str(result.error or "")
    return any(marker in error for marker in ("拒绝授权", "未授权", "授权等待超时"))


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


def _request_user_interaction(
    state: AgentState,
    interaction_manager,
    kind: str,
    payload: dict,
    on_progress=None,
    checkpoint_store=None,
):
    restored = state.pending_interaction if isinstance(state.pending_interaction, dict) else None
    restored_matches = bool(
        restored
        and restored.get("request_id")
        and str(restored.get("task_id") or state.task_id) == state.task_id
        and str(restored.get("kind") or "") == kind
    )
    restored_status = str(restored.get("status") or "pending") if restored_matches else ""
    can_replay = restored_matches and restored_status == "pending"
    can_consume = restored_matches and restored_status in {
        "accepted",
        "rejected",
        "cancelled",
        "timeout",
        "timed_out",
    }
    if can_replay or can_consume:
        request_id = str(restored.get("request_id") or "")
        created_at = str(restored.get("created_at") or state.updated_at)
        restored_payload = restored.get("payload")
        request_payload = (
            dict(restored_payload) if isinstance(restored_payload, dict) else dict(payload)
        )
    else:
        request_id = "interaction_" + uuid.uuid4().hex
        state.touch()
        created_at = state.updated_at
        request_payload = dict(payload)

    if can_consume:
        decision = InteractionDecision(
            request_id=request_id,
            accepted=bool(restored.get("accepted")),
            status=restored_status,
            response=str(restored.get("response") or ""),
            steps=list(restored.get("steps") or []),
        )
        decided_at = str(restored.get("decided_at") or state.updated_at)
    else:
        state.status = "waiting_user"
        state.pending_interaction = {
            "request_id": request_id,
            "task_id": state.task_id,
            "kind": kind,
            "payload": request_payload,
            "status": "pending",
            "created_at": created_at,
        }
        state.touch()
        _emit_progress(
            on_progress,
            "waiting_user",
            state,
            {
                **request_payload,
                "request_id": request_id,
                "task_id": state.task_id,
                "kind": kind,
                "status": "pending",
                "created_at": created_at,
            },
            checkpoint_store=checkpoint_store,
        )
        decision = interaction_manager.request(
            kind,
            request_payload,
            task_id=state.task_id,
            request_id=request_id,
            created_at=created_at,
        )
        state.touch()
        decided_at = state.updated_at
    decision_record = {
        "request_id": request_id,
        "task_id": state.task_id,
        "kind": kind,
        "status": decision.status,
        "accepted": bool(decision.accepted),
        "response": decision.response,
        "steps": list(decision.steps),
        "created_at": created_at,
        "decided_at": decided_at,
    }
    if not any(
        str(item.get("request_id") or "") == request_id
        for item in state.interaction_history
    ):
        state.interaction_history.append(decision_record)
    state.pending_interaction = {
        **state.pending_interaction,
        "status": decision.status,
        "accepted": bool(decision.accepted),
        "response": decision.response,
        "steps": list(decision.steps),
        "decided_at": decided_at,
    }
    _save_checkpoint(checkpoint_store, state)

    state.pending_interaction = None
    if decision.accepted:
        state.status = "running"
    elif decision.status in {"timeout", "timed_out"}:
        state.status = "timed_out"
    else:
        state.status = "cancelled"
    state.touch()
    _emit_progress(
        on_progress,
        "interaction_resolved",
        state,
        {
            "request_id": request_id,
            "task_id": state.task_id,
            "kind": kind,
            "status": decision.status,
            "accepted": bool(decision.accepted),
            "response": decision.response,
        },
        checkpoint_store=checkpoint_store,
    )
    return decision


def _apply_plan_edits(plan: Plan, edited_steps: list) -> bool:
    goals = []
    for item in edited_steps[:8]:
        goal = item.get("goal") if isinstance(item, dict) else item
        if isinstance(goal, str) and goal.strip():
            goals.append(goal.strip())
    if not goals:
        return False

    updated_steps = []
    for index, goal in enumerate(goals, start=1):
        if index <= len(plan.steps):
            original = plan.steps[index - 1]
            if original.status == "completed":
                updated_steps.append(replace(original, step_id=index, status="completed"))
                continue
            if original.goal == goal:
                updated_steps.append(
                    replace(
                        original,
                        step_id=index,
                        status="pending",
                        depends_on=[item for item in original.depends_on if item < index],
                    )
                )
                continue
            updated_steps.append(
                replace(
                    original,
                    step_id=index,
                    goal=goal,
                    status="pending",
                    tool_hint=None,
                    action_hint=None,
                    inputs={},
                    depends_on=[],
                    success_criteria=[],
                    requires_authorization=False,
                )
            )
        else:
            updated_steps.append(PlanStep(step_id=index, goal=goal))
    plan.steps = updated_steps
    plan.source = "user_edited"
    plan.reason = "用户在执行前编辑了计划"
    return True


def _confirm_plan(
    state: AgentState,
    interaction_manager,
    on_progress=None,
    checkpoint_store=None,
) -> bool:
    if interaction_manager is None or state.plan is None or not state.plan.requires_confirmation:
        return True
    payload = {
        "title": "确认执行计划",
        "question": "请确认、修改或取消下面的执行计划。",
        "reason": state.plan.reason,
        "steps": [
            {
                "step_id": step.step_id,
                "goal": step.goal,
                "tool_hint": step.tool_hint,
                "requires_authorization": step.requires_authorization,
            }
            for step in state.plan.steps
        ],
    }
    decision = _request_user_interaction(
        state,
        interaction_manager,
        "plan_confirmation",
        payload,
        on_progress=on_progress,
        checkpoint_store=checkpoint_store,
    )
    if not decision.accepted:
        state.plan.status = "cancelled"
        state.final_output = "用户取消了计划执行"
        return False
    edited = _apply_plan_edits(state.plan, decision.steps)
    state.plan.requires_confirmation = False
    _emit_progress(
        on_progress,
        "plan_updated" if edited else "plan_confirmed",
        state,
        {
            "steps": [{"step_id": step.step_id, "goal": step.goal} for step in state.plan.steps],
            "edited": edited,
        },
        checkpoint_store=checkpoint_store,
    )
    return True


def run_minimal_loop(
    state: AgentState,
    tool_registry=None,
    on_progress=None,
    checkpoint_store=None,
    llm_client=None,
    planner=None,
    router=None,
    interaction_manager=None,
) -> AgentState:
    executor = Executor(tool_registry)
    tool_catalog = build_tool_catalog(executor.tool_registry)
    planner = planner or Planner(
        llm_client=llm_client,
        tool_catalog=tool_catalog,
    )
    router = router or Router(
        llm_client=llm_client,
        tool_registry=executor.tool_registry,
        tool_catalog=tool_catalog,
    )
    verifier = Verifier()
    reflection = Reflection()

    if state.missing_info and interaction_manager is None:
        state.status = "failed"
        state.final_output = "缺少任务必需信息：" + "；".join(state.missing_info)
        state.touch()
        _save_checkpoint(checkpoint_store, state)
        return state

    if state.missing_info:
        question = "请补充以下信息：" + "；".join(state.missing_info)
        decision = _request_user_interaction(
            state,
            interaction_manager,
            "missing_info",
            {"title": "补充任务信息", "question": question, "missing_info": list(state.missing_info)},
            on_progress=on_progress,
            checkpoint_store=checkpoint_store,
        )
        if not decision.accepted:
            state.final_output = "用户未提供任务所需信息"
            return state
        if not decision.response.strip():
            state.status = "failed"
            state.final_output = "用户未提供任务所需信息"
            state.touch()
            _save_checkpoint(checkpoint_store, state)
            return state
        base_input = state.execution_input or state.user_input
        state.execution_input = f"{base_input}\n\n用户补充信息：\n{decision.response.strip()}"
        state.missing_info = []

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
    if not state.plan.steps:
        state.plan.status = "failed"
        state.status = "failed"
        state.final_output = "计划没有可执行步骤"
        state.touch()
        _save_checkpoint(checkpoint_store, state)
        return state
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
    if not _confirm_plan(
        state,
        interaction_manager,
        on_progress=on_progress,
        checkpoint_store=checkpoint_store,
    ):
        return state

    completed_step_results = _completed_step_results(state.results)
    user_input_requested_steps: set[int] = set()
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
            criterion_results = verifier.check_criteria(
                state,
                step,
                result,
                plan_id=state.plan.plan_id,
                attempt=attempt + 1,
            )
            state.criterion_results.extend(criterion_results)
            failed_criteria = [item for item in criterion_results if not item.passed]
            if failed_criteria:
                check = type(check)(
                    passed=False,
                    failed_reasons=list(check.failed_reasons)
                    + [
                        f"成功标准未满足：{item.criterion}（{item.failure_reason}）"
                        for item in failed_criteria
                    ],
                    suggested_fix=list(check.suggested_fix)
                    + [f"补充可验证结果：{item.criterion}" for item in failed_criteria],
                    score=check.score,
                )
            state.checks.append(check)
            _emit_progress(
                on_progress,
                "verified",
                state,
                {
                    "step_id": step.step_id,
                    "passed": check.passed,
                    "failed_reasons": check.failed_reasons,
                    "criterion_results": [dataclass_to_dict(item) for item in criterion_results],
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
            if _is_terminal_authorization_failure(result):
                step.status = "failed"
                state.plan.status = "failed"
                state.status = "failed"
                state.final_output = "；".join(check.failed_reasons)
                state.touch()
                _emit_progress(
                    on_progress,
                    "step_done",
                    state,
                    {"step_id": step.step_id, "status": step.status},
                    checkpoint_store=checkpoint_store,
                )
                return state
            if (
                feedback.need_user_input
                and interaction_manager is not None
                and step.step_id not in user_input_requested_steps
            ):
                decision = _request_user_interaction(
                    state,
                    interaction_manager,
                    "step_input",
                    {
                        "title": "补充步骤信息",
                        "question": f"步骤「{step.goal}」无法继续：{feedback.root_cause}。请补充所需信息。",
                        "step_id": step.step_id,
                    },
                    on_progress=on_progress,
                    checkpoint_store=checkpoint_store,
                )
                if not decision.accepted:
                    state.final_output = "用户取消了当前步骤"
                    return state
                if not decision.response.strip():
                    step.status = "failed"
                    state.plan.status = "failed"
                    state.status = "failed"
                    state.final_output = "用户未提供当前步骤所需信息"
                    state.touch()
                    _emit_progress(
                        on_progress,
                        "step_done",
                        state,
                        {"step_id": step.step_id, "status": step.status},
                        checkpoint_store=checkpoint_store,
                    )
                    return state
                base_input = state.execution_input or state.user_input
                state.execution_input = f"{base_input}\n\n用户补充信息：\n{decision.response.strip()}"
                user_input_requested_steps.add(step.step_id)
                attempt += 1
                if attempt > step.max_retries:
                    step.max_retries = attempt
                continue
            attempt += 1

        if step.status != "completed":
            if feedback is not None and state.replan_count < state.max_replans and not _is_unsupported_result(result):
                feedback.need_replan = True
                old_plan = state.plan
                failure_context = {
                    "failed_step_id": step.step_id,
                    "failed_goal": step.goal,
                    "root_cause": feedback.root_cause,
                    "repair_strategy": feedback.repair_strategy,
                    "failed_reasons": list(check.failed_reasons),
                    "suggested_fix": list(check.suggested_fix),
                    "criterion_results": [
                        dataclass_to_dict(item)
                        for item in state.criterion_results
                        if item.plan_id == old_plan.plan_id and item.step_id == step.step_id
                    ],
                    "completed_steps": [
                        {"step_id": step_id, "result": step_result}
                        for step_id, step_result in sorted(completed_step_results.items())
                    ],
                    "evidence": state.evidence,
                }
                new_plan = planner.create_plan(
                    _task_from_state(state),
                    matched_skill=state.matched_skill,
                    failure_context=failure_context,
                    existing_plan=old_plan,
                )
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
                if not _confirm_plan(
                    state,
                    interaction_manager,
                    on_progress=on_progress,
                    checkpoint_store=checkpoint_store,
                ):
                    return state
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
        state.final_output = _result_text(state.results[-1])

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

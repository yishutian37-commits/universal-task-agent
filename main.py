from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from core.loop import run_minimal_loop
from core.skill_loader import SkillLoader
from core.state import AgentState
from core.task_parser import TaskParser
from memory_providers.json_memory_provider import JsonMemoryProvider


def generate_task_id() -> str:
    return "task_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def create_initial_state(task_id: str, user_input: str) -> AgentState:
    return AgentState(
        task_id=task_id,
        user_input=user_input,
        task_type="unknown",
        intent="",
    )


def apply_task_to_state(state: AgentState, task) -> None:
    state.task_type = task.task_type
    state.intent = task.intent
    state.touch()


def build_log_lines(state: AgentState) -> list[str]:
    result = state.results[-1] if state.results else None
    lines = [
        "[Main] task received",
        f"[TaskParser] task_type = {state.task_type}",
        f"[TaskParser] intent = {state.intent}",
    ]
    matched_skill_id = state.matched_skill.get("id") if state.matched_skill else "none"
    lines.append(f"[SkillLoader] matched_skill = {matched_skill_id}")

    if state.plan is not None:
        lines.append(f"[Planner] created {len(state.plan.steps)} steps")
        for index, step in enumerate(state.plan.steps):
            lines.append(f"[Loop] step {step.step_id} started: {step.goal}")
            if index < len(state.results):
                step_result = state.results[index]
                lines.append(f"[Router] selected tool = {step_result.tool_name}")
                lines.append(f"[Executor] tool = {step_result.tool_name}")
            if index < len(state.checks):
                lines.append(f"[Verifier] passed = {state.checks[index].passed}")

    for feedback in state.feedbacks:
        lines.append(f"[Reflection] failure_type = {feedback.failure_type}")
        lines.append(f"[Reflection] repair_strategy = {feedback.repair_strategy}")

    lines.append(f"[Replan] count = {state.replan_count}")
    for event in state.replan_events:
        lines.append(
            "[Replan] failed_step = "
            f"{event.get('failed_step_id')}, resume_step = {event.get('resume_step_id')}"
        )

    lines.append(f"[Memory] saved = {str(state.memory_saved).lower()}")

    lines.extend(
        [
            f"[Result] success = {result.success if result else False}",
            f"[State] status = {state.status}",
        ]
    )
    return lines


def save_log(state: AgentState, log_dir: Path) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{state.task_id}.log"
    log_path.write_text("\n".join(build_log_lines(state)) + "\n", encoding="utf-8")
    return log_path


def emit_progress(on_progress, event_type: str, state: AgentState, data: dict) -> None:
    if on_progress is None:
        return
    on_progress(
        {
            "type": event_type,
            "task_id": state.task_id,
            "data": data,
        }
    )


def run_task(
    task: str,
    output_root: Path | str = "outputs",
    task_id: str | None = None,
    task_parser=None,
    tool_registry=None,
    memory_provider=None,
    skill_loader=None,
    on_progress=None,
) -> AgentState:
    root = Path(output_root)
    state = create_initial_state(task_id or generate_task_id(), task)
    emit_progress(
        on_progress,
        "task_received",
        state,
        {"user_input": state.user_input},
    )
    parser = task_parser if task_parser is not None else TaskParser()
    parsed_task = parser.parse(state.task_id, state.user_input)
    apply_task_to_state(state, parsed_task)
    emit_progress(
        on_progress,
        "parsed",
        state,
        {"task_type": state.task_type, "intent": state.intent},
    )
    if skill_loader is False:
        state.matched_skill = None
    else:
        loader = skill_loader if skill_loader is not None else SkillLoader()
        state.matched_skill = loader.match(parsed_task)
    emit_progress(
        on_progress,
        "skill_matched",
        state,
        {"skill_id": state.matched_skill.get("id") if state.matched_skill else None},
    )
    state = run_minimal_loop(state, tool_registry=tool_registry, on_progress=on_progress)
    if memory_provider is False:
        state.memory_saved = False
    else:
        provider = memory_provider if memory_provider is not None else JsonMemoryProvider()
        provider.save_task(state)
        state.memory_saved = True
    emit_progress(
        on_progress,
        "memory_saved",
        state,
        {"saved": state.memory_saved},
    )
    state.save_json(root / "states")
    save_log(state, root / "logs")
    emit_progress(
        on_progress,
        "task_completed",
        state,
        {"status": state.status, "final_output": state.final_output},
    )
    return state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Universal Task Agent V1.1 Research Search API")
    parser.add_argument("--task", required=True, help="要执行的任务")
    parser.add_argument("--output-root", default="outputs", help="运行产物输出目录")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    state = run_task(args.task, output_root=args.output_root)
    if state.status == "completed":
        print(f"任务已完成：{state.final_output}")
    else:
        print(f"任务失败：{state.final_output}")


if __name__ == "__main__":
    main()

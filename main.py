from __future__ import annotations

import argparse
from datetime import datetime

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
    task_id: str | None = None,
    task_parser=None,
    tool_registry=None,
    memory_provider=None,
    skill_loader=None,
    on_progress=None,
) -> AgentState:
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
    emit_progress(
        on_progress,
        "task_completed",
        state,
        {"status": state.status, "final_output": state.final_output},
    )
    return state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Universal Task Agent local learning agent")
    parser.add_argument("--task", required=True, help="要执行的任务")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    state = run_task(args.task)
    if state.status == "completed":
        print(f"任务已完成：{state.final_output}")
    else:
        print(f"任务失败：{state.final_output}")


if __name__ == "__main__":
    main()

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


def create_initial_state(
    task_id: str,
    user_input: str,
    execution_input: str | None = None,
    conversation_id: str | None = None,
    workspace_path: str | None = None,
) -> AgentState:
    return AgentState(
        task_id=task_id,
        user_input=user_input,
        execution_input=execution_input,
        conversation_id=conversation_id,
        workspace_path=workspace_path,
        task_type="unknown",
        intent="",
    )


def apply_task_to_state(state: AgentState, task) -> None:
    state.task_type = task.task_type
    state.intent = task.intent
    state.constraints = list(task.constraints)
    state.missing_info = list(task.missing_info)
    state.touch()


def _save_checkpoint(checkpoint_store, state: AgentState) -> None:
    if checkpoint_store is not None:
        checkpoint_store.save(state)


def emit_progress(on_progress, event_type: str, state: AgentState, data: dict, checkpoint_store=None) -> None:
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


def run_task(
    task: str,
    task_id: str | None = None,
    display_user_input: str | None = None,
    task_parser=None,
    tool_registry=None,
    memory_provider=None,
    skill_loader=None,
    on_progress=None,
    checkpoint_store=None,
    resume_from_checkpoint: bool = False,
    conversation_id: str | None = None,
    workspace_path: str | None = None,
    interaction_manager=None,
) -> AgentState:
    execution_input = task
    saved_user_input = display_user_input if display_user_input is not None else task
    checkpoint_task_id = task_id or generate_task_id()
    loaded_state = None
    planning_client = getattr(task_parser, "llm_client", None)
    if resume_from_checkpoint and checkpoint_store is not None:
        loaded_state = checkpoint_store.load(checkpoint_task_id)

    if loaded_state is not None:
        state = loaded_state
        if not state.execution_input:
            state.execution_input = execution_input
        emit_progress(
            on_progress,
            "task_resumed",
            state,
            {"task_id": state.task_id, "current_step_id": state.current_step_id},
            checkpoint_store=checkpoint_store,
        )
    else:
        state = create_initial_state(
            checkpoint_task_id,
            saved_user_input,
            execution_input,
            conversation_id=conversation_id,
            workspace_path=workspace_path,
        )
        emit_progress(
            on_progress,
            "task_received",
            state,
            {"user_input": state.user_input},
            checkpoint_store=checkpoint_store,
        )
        parser = task_parser if task_parser is not None else TaskParser()
        planning_client = getattr(parser, "llm_client", None)
        parsed_task = parser.parse(state.task_id, execution_input)
        apply_task_to_state(state, parsed_task)
        emit_progress(
            on_progress,
            "parsed",
            state,
            {"task_type": state.task_type, "intent": state.intent},
            checkpoint_store=checkpoint_store,
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
            checkpoint_store=checkpoint_store,
        )
    state = run_minimal_loop(
        state,
        tool_registry=tool_registry,
        on_progress=on_progress,
        checkpoint_store=checkpoint_store,
        llm_client=planning_client,
        interaction_manager=interaction_manager,
    )
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
        checkpoint_store=checkpoint_store,
    )
    emit_progress(
        on_progress,
        "task_completed",
        state,
        {"status": state.status, "final_output": state.final_output},
        checkpoint_store=checkpoint_store,
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

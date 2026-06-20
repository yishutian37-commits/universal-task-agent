from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from core.loop import run_minimal_loop
from core.state import AgentState


def generate_task_id() -> str:
    return "task_" + datetime.now().strftime("%Y%m%d_%H%M%S")


def create_initial_state(task_id: str, user_input: str) -> AgentState:
    return AgentState(
        task_id=task_id,
        user_input=user_input,
        task_type="summarize",
        intent="v0.1 hard-coded summarize skeleton",
    )


def build_log_lines(state: AgentState) -> list[str]:
    result = state.results[-1] if state.results else None
    check = state.checks[-1] if state.checks else None
    return [
        "[Main] task received",
        "[State] task_type = summarize",
        "[Loop] step 1 started: 执行 V0.1 mock 工具",
        "[Executor] tool = mock_tool",
        f"[Verifier] passed = {check.passed if check else False}",
        f"[Result] success = {result.success if result else False}",
        f"[State] status = {state.status}",
    ]


def save_log(state: AgentState, log_dir: Path) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{state.task_id}.log"
    log_path.write_text("\n".join(build_log_lines(state)) + "\n", encoding="utf-8")
    return log_path


def run_task(
    task: str,
    output_root: Path | str = "outputs",
    task_id: str | None = None,
) -> AgentState:
    root = Path(output_root)
    state = create_initial_state(task_id or generate_task_id(), task)
    state = run_minimal_loop(state)
    state.save_json(root / "states")
    save_log(state, root / "logs")
    return state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Universal Task Agent V0.1")
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

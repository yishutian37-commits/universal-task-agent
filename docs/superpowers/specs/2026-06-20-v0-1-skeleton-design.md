# UTA V0.1 Skeleton Design

## Context

This spec follows `universal_task_agent_prd_v6_1_final_start.md`.

The current delivery target is `v0.1-skeleton`: a minimal, runnable UTA core without LLM integration. The goal is to make the first Agent execution path easy to read, test, log, and tag.

TAM Memory, Task Parser, Planner, Router, Reflection, JSON Memory, Skill Builder, and Skill Loader are outside this milestone.

## Scope

V0.1 must support this flow:

```text
CLI task input
-> AgentState with task_type fixed to summarize
-> hard-coded one-step Plan
-> hard-coded Action for mock_tool
-> Executor runs MockTool
-> Verifier checks ToolResult.success
-> state and log files are saved under outputs/
-> CLI prints the final mock result
```

The milestone is complete when `python main.py --task "帮我总结一段文本"` creates a completed state file, writes a readable log, and prints `任务已完成：mock result`.

## Architecture

`main.py` is the only CLI entry point. It parses `--task`, creates an `AgentState`, calls the minimal loop, saves artifacts, and prints the outcome.

`core/state.py` owns all V0.1 dataclasses: `Task`, `PlanStep`, `Plan`, `Action`, `ToolResult`, `CheckResult`, `Feedback`, and `AgentState`. It also owns state serialization helpers so nested dataclasses can be exported to JSON safely.

`tools/base_tool.py` defines the tool interface. `tools/mock_tool.py` returns a fixed successful result for the V0.1 demo. `tools/registry.py` exposes `TOOL_REGISTRY = {"mock_tool": MockTool()}`.

`core/executor.py` accepts an `Action`, looks up the tool by `tool_name`, runs it, catches exceptions, and always returns a `ToolResult`.

`core/verifier.py` performs the V0.1 minimum check: `ToolResult.success is True`. It returns a `CheckResult` and does not inspect content quality.

`core/loop.py` creates a hard-coded one-step `Plan`, sets `state.current_step_id`, creates the mock action, calls the executor, appends the result and check to state, marks the step and state as `completed` or `failed`, and returns the updated state.

## Data Flow

1. `main.py` receives the user task string.
2. `main.py` creates `AgentState(task_id=..., user_input=..., task_type="summarize", intent="v0.1 hard-coded summarize skeleton")`.
3. `run_minimal_loop(state)` creates `Plan(plan_id=..., steps=[PlanStep(step_id=1, goal="执行 V0.1 mock 工具")])`.
4. The loop creates `Action(tool_name="mock_tool", action_name="run", params={"user_input": state.user_input})`.
5. `Executor.run(action)` calls `MockTool.run(...)`.
6. `Verifier.check(result)` returns pass or fail.
7. The loop updates state and final output.
8. `main.py` writes `outputs/states/<task_id>_state.json` and `outputs/logs/<task_id>.log`.

## Error Handling

If the tool name is missing from the registry, `Executor` returns `ToolResult(success=False, error="tool_unavailable: ...")`.

If a tool raises an exception, `Executor` catches it and returns `ToolResult(success=False, error="tool_error: ...")`.

If the verifier fails, the loop marks the step as `failed`, sets `state.status = "failed"`, stores the check result, and preserves the error in the exported state.

V0.1 does not retry. The two-layer retry loop starts in later milestones when Reflection and Replan exist.

## Testing

Tests cover the readable contract of each small unit:

- `test_state.py`: `AgentState` exports nested dataclasses to JSON-compatible dictionaries.
- `test_mock_tool.py`: `MockTool` returns the fixed successful `mock result`.
- `test_executor.py`: executor succeeds with registered tools, returns `tool_unavailable` for missing tools, and catches tool exceptions.
- `test_verifier.py`: verifier passes successful tool results and fails unsuccessful ones.
- `test_loop.py`: minimal loop completes the state and records one result and one check.
- `test_main.py`: CLI execution writes state and log artifacts under a provided output directory.

The implementation uses TDD: each behavior gets a failing test before production code.

## Git And Versioning

After V0.1 passes tests and the demo command, commit the work in small PRD-aligned commits and tag:

```bash
git tag v0.1-skeleton
```

The current directory starts empty, so the project should initialize git before the first committed artifact.

## Explicit Non-Scope

V0.1 does not call LLMs, parse task types, generate dynamic plans, route tools by rules, read real files, generate real summaries, write Memory, load Skills, or integrate TAM.

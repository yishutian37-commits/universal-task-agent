# UTA V1.0 Learning Agent and Memory Visibility Design

> Status: proposed for planning
> Date: 2026-06-23

## Goal

Close the PRD v6.1 UTA V1.0 learning-agent milestone without expanding the product scope beyond the core CLI learning framework, while documenting a clear memory model that explains where short-term and long-term memory can be inspected now and how the desktop memory view should evolve after V1.0.

V1.0 implementation scope is intentionally limited to four deliverables:

1. Implement A11: one replan attempt, continuing after the failed step.
2. Update README, CHANGELOG, and visible version wording.
3. Run and document one summary demo and one table-analysis demo.
4. Tag the verified core milestone as `v1.0-learning-agent`.

Memory-system work in this design is mostly clarity and positioning for V1.0. It should not add new TAM integration, database storage, semantic retrieval, or a full desktop memory editor during the V1.0 closeout.

## Current Context

The repository has completed tags from `v0.1-skeleton` through `v0.8-skill-runtime`. The current desktop branch also contains macOS desktop app work, run history, and an LLM curl fallback. Those are useful productization changes, but the PRD defines V1.0 as the core learning framework:

```text
Task Parser -> Planner -> Agent Loop -> Router -> Executor
-> Verifier -> Reflection -> Replan -> Output -> Memory -> Skill
```

V1.0 should be produced from the clean core line, starting from `main` / `v0.8-skill-runtime`, not by placing the V1.0 tag on the desktop app branch. This keeps the PRD milestone separate from later desktop experience work.

The main missing V1.0 behavior is A11:

```text
可以重新规划一次（replan 从失败 step 后继续）
```

Current `core.loop.run_minimal_loop()` retries the same step after Reflection, but once retries are exhausted it fails the task. Current `Reflection.analyze()` always returns `need_replan=False`.

## V1.0 Boundary

V1.0 includes:

- CLI task entry with `main.py --task`.
- `summarize` and `data_analysis` task recognition.
- Planner-generated structured plans whose `PlanStep` only contains goals, not tool names.
- Two-layer loop semantics: outer plan progression and inner per-step retry.
- Router, Executor, Verifier, Reflection, JSON Memory, Skill Builder, and Skill Loader.
- One replan attempt after a step cannot be repaired by retries.
- Markdown final reports for summary and table analysis tasks.
- JSON state/log artifacts and JSON long-term memory files.
- README/CHANGELOG/version wording that accurately says V1.0.
- `v1.0-learning-agent` git tag after verification.

V1.0 excludes:

- TAM Memory integration.
- TAM Output Guard or Faithfulness Gate.
- Semantic memory retrieval.
- Automatic web search or research tasks.
- New desktop memory UI implementation.
- Editing/deleting memories.
- Multi-agent orchestration.

Desktop memory visibility can be designed here because it affects the project direction, but it should remain a post-V1.0 implementation item unless the user explicitly expands scope.

## Replan Design

### Behavior

When a plan step fails verification after its retry budget is exhausted:

1. Mark the failed step as `failed`.
2. Ask Reflection whether replan is needed.
3. If no replan is available or `state.max_replans` has already been consumed, fail the task as today.
4. If replan is available and one attempt remains:
   - Generate a new plan for the same task.
   - Preserve completed work before the failed step.
   - Continue from the failed step's position in the new plan.
   - Do not rerun earlier completed steps.
   - Record the replan event in state and progress events.

PRD allows a simplified V1.0 approach, but this design follows the stronger wording: "from failed step after continue" in the sense that prior completed steps are not rerun. The failed goal itself is replaced by the corresponding goal at the same position in the new plan. If the new plan is shorter than the failed position, the task fails with a clear final output.

### Minimal State Additions

`AgentState` already has `max_replans`. Add a small amount of explicit bookkeeping:

- `replan_count: int = 0`
- `replan_events: list[dict[str, Any]] = field(default_factory=list)`

Each event should include:

- failed step id
- failed goal
- root cause
- old plan goals
- new plan goals
- resume step id
- timestamp

This keeps replan inspectable in `state.json`, which matters for the memory story below.

### Planner Input

Keep `Planner.create_plan()` simple. It can accept optional `feedback` in implementation if needed, but V1.0 does not require a fully intelligent replan strategy. The first implementation can use deterministic fallback rules:

- For `summarize`, regenerate the standard summary plan.
- For `data_analysis`, regenerate the standard table-analysis plan.
- For matched skills, regenerate from the matched skill workflow.

The important V1.0 learning behavior is loop control, preservation of prior steps, and state visibility. Sophisticated alternative planning can wait.

### Reflection Rule

Reflection should request replan only when a step has exhausted retries and the failure is not a simple in-step repair anymore. It should still provide the same root cause and repair strategy fields for learning/debugging.

Implementation can keep the existing `Reflection.analyze()` API and let the loop decide when exhaustion makes `need_replan` meaningful, or add a keyword parameter such as `retries_exhausted=True`. The plan should choose the smallest change that keeps tests clear.

## Memory Model

### Short-Term Memory

Short-term memory is the current task state. It answers:

```text
What is the Agent doing right now?
What has it tried?
What did each tool return?
What passed or failed verification?
What feedback did Reflection create?
Did replan happen?
```

Source of truth:

- in-memory `AgentState` while the task runs
- persisted `outputs/states/<task_id>_state.json`
- persisted `outputs/logs/<task_id>.log`

Current visibility:

- CLI users can inspect `outputs/states` and `outputs/logs`.
- Desktop users can inspect previous runs through the "运行记录" view, which reads state and log files.

V1.0 requirement:

- Replan data must be visible in `state.json` and logs.
- README should explicitly explain short-term memory as State, not long-term Memory.

### Long-Term Memory

Long-term memory is cross-task JSON memory. It answers:

```text
What has UTA learned across tasks?
Which task histories exist?
Which successful patterns became lessons?
Which failures became negative rules?
Which repeated workflows are Skill candidates?
```

Source of truth:

- `memory/user_profile.json`
- `memory/task_history.json`
- `memory/lessons.json`
- `memory/negative_rules.json`
- `memory/skill_candidates.json`

In the desktop app these live under `~/.uta/memory/`; in CLI core runs they default to `memory/` unless an injected provider uses a different root.

Current visibility:

- CLI users can open the JSON files directly.
- Desktop users do not yet have a dedicated memory view.

V1.0 requirement:

- README should explain which files are long-term memory and what each file means.
- Demo validation should confirm that memory files are updated after task runs.
- No automatic semantic recall is required for V1.0.

## Desktop Memory Visibility Direction

After V1.0, add a desktop "记忆" navigation item. It should make memory understandable before making it editable.

Recommended first desktop memory view:

1. **当前任务记忆**
   - Shows live or selected-run `AgentState`.
   - Sections: plan, current step, tool results, checks, feedback, replan events, final output.
   - Uses the same state/log source as "运行记录".

2. **任务历史**
   - Reads `task_history.json`.
   - Shows task id, task type, status, updated time, final output preview.
   - Links back to the run detail when a matching state file exists.

3. **经验与规则**
   - Reads `lessons.json` and `negative_rules.json`.
   - Shows content, source task, created time, and task type.
   - Clearly labels lessons as positive reusable patterns and negative rules as things to avoid.

4. **Skill 候选**
   - Reads `skill_candidates.json`.
   - Shows task type, success count, latest task id, status, and reason.
   - This is the bridge from memory to reusable capability.

This desktop view should be read-only at first. Editing, deletion, promotion to official Skill, and source-backed memory cleanup should be separate later specs.

## Version Documentation

Update docs after A11 is implemented:

- `README.md`
  - Current milestone becomes `v1.0-learning-agent`.
  - Add a concise "V1.0 状态" section.
  - Explain short-term State vs long-term JSON Memory.
  - Include commands for summary demo and table-analysis demo.
  - Mention TAM is not part of V1.0.

- `CHANGELOG.md`
  - Add `v1.0-learning-agent`.
  - Mention replan, V1.0 demo validation, and memory documentation.

- `main.py`
  - Update CLI description from stale older version wording to V1.0 wording.

Do not update desktop-specific README as part of the V1.0 core closeout unless the implementation plan explicitly includes a note pointing desktop users to the current app package.

## Demo Validation

Run both demos in an isolated output root so validation does not pollute the user's normal memory files:

1. Summary demo:

```bash
.venv/bin/python main.py \
  --output-root /private/tmp/uta-v1-summary \
  --task "帮我总结一段文本：UTA V1.0 要跑通 Agent Loop、Verifier、Memory 和 Skill。"
```

2. Table-analysis demo:

```bash
.venv/bin/python main.py \
  --output-root /private/tmp/uta-v1-table \
  --task "分析 examples/orders.csv"
```

The implementation plan should decide whether to inject an isolated memory root for CLI demos or add a CLI option for memory root. If the existing CLI cannot isolate memory writes, the demo should still use a temporary output root and then explicitly inspect the normal memory files without discarding user data.

Acceptance for demos:

- command exits 0
- final output is Markdown-ish text
- `outputs/states/<task_id>_state.json` exists
- `outputs/logs/<task_id>.log` exists
- memory save is recorded
- table demo includes field/basic-stat/missing/anomaly sections

If live LLM credentials are unavailable, tests still need to pass, but the V1.0 tag should not be cut until a real or controlled demo path is documented. A controlled non-network demo can be implemented only if it matches existing project test-injection patterns and is clearly labeled as a smoke/demo mode.

## Tagging Strategy

Use `v1.0-learning-agent` only after:

- targeted A11 tests pass
- full test suite passes
- README and CHANGELOG accurately describe V1.0
- summary and table demos have been run and inspected
- working tree contains no accidental staged files

Because the current desktop branch includes post-core desktop work, the V1.0 implementation should be developed from `main` / `v0.8-skill-runtime` in an isolated worktree or clean branch. The tag should point at the V1.0 core commit, not the desktop app branch head.

## Testing Strategy

### Unit Tests

Add loop tests for:

- a step exhausting retries triggers exactly one replan when `max_replans=1`
- completed prior steps are not rerun after replan
- replan data is persisted on `AgentState`
- when replan is already consumed, the task fails as before
- progress events include a replan event

Add reflection tests only if the implementation changes Reflection's API.

### Regression Tests

Existing tests must continue to pass:

- summary flow
- table-analysis flow
- reflection retry
- skill workflow injection
- JSON memory provider
- desktop tests if run on the desktop branch

### Documentation Checks

Tests do not need to parse README, but implementation review should verify:

- no stale "V0.6" CLI description
- README current status says V1.0
- CHANGELOG includes V1.0
- TAM remains explicitly out of V1.0 scope

## Open Decisions for the Implementation Plan

1. Whether to add `--memory-root` to CLI for isolated demos. This is useful but not strictly required for A1-A19.
2. Whether replan is represented as a new `Plan` object only, or whether old plan snapshots are stored in `replan_events`.
3. Whether desktop memory view gets its own future spec immediately after V1.0, or waits until V1.0 tag is cut.

Recommended choices:

- Add explicit `replan_events` to `AgentState` for inspectability.
- Do not add `--memory-root` unless demo isolation needs it during implementation.
- Cut V1.0 first; then create a separate desktop memory visibility spec.

## Acceptance Criteria

This design is complete when a follow-up implementation plan can produce:

- `v1.0-learning-agent` tag on the core learning-agent line.
- A11 replan behavior covered by tests.
- README/CHANGELOG/version wording aligned with PRD V1.0.
- Summary and table-analysis demo evidence.
- A documented memory model that explains:
  - short-term memory = State/log/run history
  - long-term memory = JSON Memory files
  - Skill candidates = transition from memory to reusable capability
  - desktop memory panel = post-V1.0 read-only visibility work

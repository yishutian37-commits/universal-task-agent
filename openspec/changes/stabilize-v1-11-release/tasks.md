## 1. State and checkpoint compatibility

- [x] 1.1 Add a structured per-criterion verification result to `core/state.py`, associate it with task/plan/step, and cover JSON round-trip in `tests/test_state.py`.
- [x] 1.2 Extend pending-interaction checkpoint data with stable request identity and terminal decision metadata while keeping older checkpoints loadable with safe defaults.
- [x] 1.3 Add regression fixtures for V1.10/V1.11 checkpoints that omit the new fields and prove resume does not rerun completed steps.

## 2. Runtime tool contracts and safe rebinding

- [x] 2.1 Define backward-compatible action contract metadata on `tools/base_tool.py`, including action name, object parameter schema, default selection, and authorization requirement.
- [x] 2.2 Upgrade `core/tool_catalog.py` to expose action contracts only for registered tools; add catalog tests for explicit multi-action and legacy single-action tools.
- [x] 2.3 Make `core/planner.py` validate `tool_hint + action_hint` against the current catalog and fall back safely for invented actions or invalid parameter objects; add planner regression tests.
- [x] 2.4 Make `core/router.py` validate tool, action, and parameters immediately before creating an executable action; invalid model routes must use a validated rule fallback or return unsupported without invoking a tool.
- [x] 2.5 Change plan-edit handling in `core/loop.py` so edited/new pending steps clear stale tool, action, inputs, success criteria, and cached authorization metadata while completed steps and evidence remain intact.
- [x] 2.6 Add tests proving an edited safe goal is rebound to its new tool and an edited dangerous goal still reaches the existing single-operation authorization flow.

## 3. Evidence-backed step success verification

- [x] 3.1 Add Verifier tests for all-pass, failed, indeterminate, empty-criteria, and deterministic high-risk filesystem criteria before changing production behavior.
- [x] 3.2 Extend `core/verifier.py` with step-aware criterion evaluation that records source, evidence, and failure reason without allowing model judgments to override deterministic failures.
- [x] 3.3 Integrate criterion evaluation into `core/loop.py`; a step completes only when existing verification and all required criteria pass, while legacy steps without criteria preserve current behavior.
- [x] 3.4 Include failed criterion details in retry and Replan context, preserve the completed prefix, and add loop tests that prove completed tools are not called again.
- [x] 3.5 Persist criterion results before each checkpoint and prove a resumed task does not re-evaluate completed-step criteria.

## 4. Durable human interaction

- [x] 4.1 Make `TaskInteractionManager` register or restore a stable request id and make `respond()` idempotent and task-bound; cover duplicate, stale, foreign-task, cancel, and timeout cases.
- [x] 4.2 Persist `pending_interaction` before progress emission, record the accepted/rejected decision before clearing pending state, and replay the same interaction during checkpoint resume.
- [x] 4.3 Update `desktop/runner.py` and `desktop/api.py` so recovery context returns the pending interaction and continuing it keeps the original task, conversation, workspace, completed steps, and evidence.
- [x] 4.4 Update the desktop frontend to deduplicate replayed interactions by request id, bind response controls to the active task, and render explicit rejected/cancelled/timed-out outcomes.
- [x] 4.5 Add an integration test that simulates application termination while waiting, reconstructs the runner/manager from checkpoint, accepts the replayed request, and completes without duplicate execution.

## 5. Automated and evaluation gates

- [x] 5.1 Run targeted state, catalog, planner, router, verifier, loop, interaction, runner, API, and frontend tests after each task group.
- [x] 5.2 Run `.venv/bin/python -m pytest -q`, `node --check desktop/frontend/app.js`, and `git diff --check`; record the exact passing counts and any non-blocking warnings.
- [x] 5.3 Extend core scenarios for invalid action contracts, failed success criteria, edited-plan rebinding, and interaction restart, then run `.venv/bin/python -m evals.runner` with zero failures.
- [x] 5.4 Reconcile README, CHANGELOG, project overview, version fields, and stale backlog claims so V1.11 is described as released only after every gate passes.

## 6. Real desktop and release artifacts

- [x] 6.1 In the real desktop app, verify ordinary chat, plan confirmation/editing, missing-information continuation, evidence-driven Replan, dangerous-tool rejection, and waiting-task restart recovery.
- [x] 6.2 Rebuild the macOS application with `desktop/build/build_macos.sh` and verify the executable reports V1.11 consistently with Python, API, Info.plist, and documentation.
- [x] 6.3 Verify application launch, critical bundled resources, `codesign --verify`, ZIP integrity, archive checksum, and clean extraction on a separate temporary path.
- [x] 6.4 Review the final release scope so architecture-visualizer staging files and `task-*-review-package.diff` artifacts are excluded; only after acceptance, create the intentional V1.11 release commit and tag.

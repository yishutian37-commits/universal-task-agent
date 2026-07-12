# Task 3 Review: Unify tool registry in `tools.registry`

## Verdict

- **Spec compliance:** ✅
- **Code quality:** Approved (with noted technical debt)

## Summary of Changes

The implementation matches the brief:

- `tools/registry.py` now exports a parameterized `build_tool_registry(...)` with typed `Path | str | None` arguments and returns `dict[str, BaseTool]`.
- `desktop/runner.py` removed its local `build_tool_registry` and imports from `tools.registry`, passing desktop-specific roots.
- Full test suite passes: `441 passed, 5 deselected`.

## Test Evidence

```bash
PYTHONPATH=/Users/tianjiashu/项目 .venv/bin/pytest tests/ -q
```

```
441 passed, 5 deselected in 1.68s
```

## Issues

### Critical

None.

### Important

1. **Layering violation:** `tools/registry.py` imports `resource_path` and `uta_home` from `desktop.paths`, making the generic `tools` layer depend on the `desktop` layer. The brief explicitly required this import, so the implementation is spec-compliant, but it introduces coupling. Consider moving these path helpers to a neutral `paths` module in a future cleanup to avoid dragging desktop semantics into CLI/tool-only imports.

2. **Default CLI behavior is now cwd-dependent:** When no arguments are passed, `project_root` defaults to `Path.cwd()`. Previously the registry used tool-specific defaults (e.g., `CodeTool()` also defaulted to `Path.cwd()`, so behavior is effectively the same), but any caller that imports `tools.registry` at module load will bake in the current working directory. This is acceptable given the brief, but worth monitoring if CLI usage ever starts from a non-project directory.

### Minor

1. **Unused import:** `from typing import Any` in `tools/registry.py` is not used and can be removed.
2. **Type normalization:** `output_root` and `memory_root` accept `str` per the signature but are not coerced to `Path` inside `build_tool_registry`. `HistoryTool` currently accepts both, so this is only a minor consistency/style note.

## Recommendations

- Remove the unused `Any` import.
- Evaluate whether `desktop.paths` can be relocated so `tools.registry` does not depend on `desktop`.

No fixes are required for spec compliance.

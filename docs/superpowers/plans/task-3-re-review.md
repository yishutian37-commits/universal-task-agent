# Task 3 Re-Review: Unify tool registry in `tools.registry`

## Verdict

- **Spec compliance:** ✅
- **Code quality:** Approved (with noted technical debt)

## Summary of Changes

The updated implementation matches the brief and the fix report:

- `tools/registry.py` exports a parameterized `build_tool_registry(...)` with typed `Path | str | None` arguments and returns `dict[str, BaseTool]`.
- `desktop/runner.py` removed its local `build_tool_registry` and imports from `tools.registry`, passing desktop-specific roots.
- The two previously noted minor issues have been resolved.

## Confirmation of Fixes

| Issue | Status | Evidence |
|-------|--------|----------|
| Unused `from typing import Any` import in `tools/registry.py` | ✅ Resolved | `Any` is no longer imported in `tools/registry.py`. |
| `output_root` / `memory_root` not coerced to `Path` | ✅ Resolved | Both parameters are now wrapped with `Path(...)` when not `None`, matching `project_root` and `skills_root`. |

## Test Evidence

```bash
PYTHONPATH=/Users/tianjiashu/项目 .venv/bin/pytest tests/ -q
```

```
441 passed, 5 deselected in 1.67s
```

Targeted desktop/api tests also pass:

```bash
PYTHONPATH=/Users/tianjiashu/项目 .venv/bin/pytest tests/test_desktop_api.py tests/test_api_server.py -q
```

```
29 passed in 0.27s
```

## Remaining Issues

### Critical

None.

### Important

1. **Layering violation remains:** `tools/registry.py` still imports `resource_path` and `uta_home` from `desktop.paths`, making the generic `tools` layer depend on the `desktop` layer. This was required by the brief, so the implementation remains spec-compliant, but the coupling is unchanged and should be addressed in a future cleanup.

2. **Default CLI behavior is cwd-dependent:** When no arguments are passed, `project_root` defaults to `Path.cwd()`. This matches the brief and is consistent with the previous default behavior of `CodeTool`, but any module-load import of `tools.registry` will bake in the current working directory.

### Minor

None.

## Recommendations

- Consider relocating `desktop.paths` to a neutral shared module so `tools.registry` does not depend on `desktop`.
- Monitor CLI usage when invoked from directories other than the project root.

## Conclusion

The fix package resolves the identified minor issues without introducing new problems. The task remains spec-compliant and quality-approved, subject to the pre-existing layering technical debt noted above.

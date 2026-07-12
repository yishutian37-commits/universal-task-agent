# Task 3 Report: 统一工具注册表

## Status

Completed.

- `tools/registry.py` now exports a parameterized `build_tool_registry(...)` that is the single source of truth.
- `desktop/runner.py` no longer defines its own `build_tool_registry`; it imports from `tools.registry` and passes the desktop-specific roots.
- All targeted and full-suite tests pass.

## Questions and Resolutions

- **Q: The new `tools/registry.py` references `desktop.paths`, which creates a desktop → tools dependency. Is this acceptable?**
  - The brief explicitly required importing `resource_path` and `uta_home` from `desktop.paths` into `tools/registry.py`, so this was implemented as specified.
- **Q: `desktop/runner.py` still needs `uta_home()` in `__init__`. Should it still import it?**
  - Yes. After removing the local `build_tool_registry`, `runner.py` still uses `uta_home()` for default `output_root`/`memory_root`, so the import was kept alongside `resource_path`.

## Test Commands and Output

```bash
cd /Users/tianjiashu/项目
PYTHONPATH=/Users/tianjiashu/项目 .venv/bin/pytest tests/test_desktop_api.py tests/test_api_server.py -q
```

```
29 passed in 0.29s
```

```bash
PYTHONPATH=/Users/tianjiashu/项目 .venv/bin/pytest tests/ -q
```

```
441 passed, 5 deselected in 1.67s
```

## Commit Hash and Message

- **Hash:** `3b897f5f56265d7659234118beef0480beedb588`
- **Message:** `refactor: unify tool registry in tools.registry`

## Concerns or Deviations

- `pytest` was not available in the default shell PATH; tests were run via `.venv/bin/pytest` with `PYTHONPATH=/Users/tianjiashu/项目` so the top-level `config` module could be imported. This is an environment detail, not a code issue.
- No deviations from the brief.

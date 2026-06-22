# UTA Desktop App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a real macOS desktop app package for the current UTA Python Agent, using the existing desktop prototype as UI direction and producing `dist/UTA Desktop.app`.

**Architecture:** Add a thin `desktop/` layer around the existing CLI core. The desktop window is a pywebview native window that loads local HTML/CSS/JS, calls a Python `DesktopAPI`, runs `main.run_task()` on a background thread, receives progress events from the loop callback, and writes all runtime files under `~/.uta/` instead of the repo.

**Tech Stack:** Python, pytest, pywebview, PyInstaller, vanilla HTML/CSS/JS.

---

### Task 1: Core Progress Events

**Files:**
- Modify: `core/loop.py`
- Modify: `main.py`
- Test: `tests/test_loop.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: Write failing loop progress test**

Add a test that calls `run_minimal_loop(..., on_progress=events.append)` and expects `plan_created`, `step_started`, `tool_selected`, `tool_executed`, `verified`, and `step_done` events with the current `task_id`.

- [ ] **Step 2: Verify the test fails**

Run: `.venv/bin/python -m pytest tests/test_loop.py::test_loop_emits_progress_events -q`
Expected: FAIL because `run_minimal_loop()` does not accept `on_progress`.

- [ ] **Step 3: Implement loop event emission**

Add an optional `on_progress=None` parameter to `run_minimal_loop`. Emit event dictionaries shaped as `{"type": "...", "task_id": state.task_id, "data": {...}}`. Preserve existing behavior when the callback is omitted.

- [ ] **Step 4: Write failing run_task progress test**

Add a test that calls `run_task(..., on_progress=events.append)` with injected parser/tools and expects top-level `task_received`, `parsed`, `skill_matched`, `memory_saved`, and `task_completed` events.

- [ ] **Step 5: Implement run_task event forwarding**

Add `on_progress=None` to `run_task`, emit top-level events, and pass the callback to `run_minimal_loop`.

- [ ] **Step 6: Verify core tests**

Run: `.venv/bin/python -m pytest tests/test_loop.py tests/test_main.py -q`
Expected: PASS.

### Task 2: Desktop Backend

**Files:**
- Create: `desktop/__init__.py`
- Create: `desktop/paths.py`
- Create: `desktop/settings_store.py`
- Create: `desktop/runner.py`
- Create: `desktop/api.py`
- Create: `tests/test_desktop_settings_store.py`
- Create: `tests/test_desktop_api.py`

- [ ] **Step 1: Write settings-store tests**

Test that `SettingsStore` writes `~/.uta/config.json` through an overridable `UTA_HOME`, hides `llm_api_key` from public settings, preserves an existing key when the user saves an empty password field, clears the key when requested, and applies values to `os.environ`.

- [ ] **Step 2: Verify settings-store tests fail**

Run: `.venv/bin/python -m pytest tests/test_desktop_settings_store.py -q`
Expected: FAIL because `desktop.settings_store` does not exist.

- [ ] **Step 3: Implement paths and settings store**

Create `desktop/paths.py` for `uta_home()` and resource lookup. Create `SettingsStore` with `load()`, `save()`, `public_settings()`, and `apply_to_environment()`.

- [ ] **Step 4: Write desktop API tests**

Test that `DesktopAPI.get_settings()` hides the key, `save_settings()` persists user settings, `load_example("summarize")` returns Chinese example input, `run_task()` refuses to run without a key, and `run_task()` starts an injected runner when a key exists.

- [ ] **Step 5: Verify desktop API tests fail**

Run: `.venv/bin/python -m pytest tests/test_desktop_api.py -q`
Expected: FAIL until `DesktopAPI` exists.

- [ ] **Step 6: Implement runner and API**

Create `TaskRunner` for single-task background execution and pywebview event push. Create `DesktopAPI` as the bridge exposed to JavaScript.

- [ ] **Step 7: Verify desktop backend tests**

Run: `.venv/bin/python -m pytest tests/test_desktop_settings_store.py tests/test_desktop_api.py -q`
Expected: PASS.

### Task 3: Desktop Frontend and Launchers

**Files:**
- Create: `desktop/app.py`
- Create: `desktop/frontend/index.html`
- Create: `desktop/frontend/style.css`
- Create: `desktop/frontend/app.js`
- Create: `desktop/build/uta_app.py`
- Create: `desktop/README.md`

- [ ] **Step 1: Add pywebview launcher**

Create `desktop/app.py` with `main()` that creates a `DesktopAPI`, opens `desktop/frontend/index.html` in a pywebview window, binds the window back to the API, and starts pywebview.

- [ ] **Step 2: Add frontend shell**

Create a vanilla HTML/CSS/JS console based on the existing `desktop.html` prototype: task input, settings modal, plan list, real-time log, Markdown-ish report rendering, and `state.json` panel. JavaScript must call `window.pywebview.api`.

- [ ] **Step 3: Add packaged entry point and README**

Create `desktop/build/uta_app.py` for PyInstaller and `desktop/README.md` with development and packaging commands.

- [ ] **Step 4: Smoke import desktop modules**

Run: `.venv/bin/python -m pytest tests/test_desktop_settings_store.py tests/test_desktop_api.py -q`
Expected: PASS and no import-time pywebview dependency.

### Task 4: Packaging Config

**Files:**
- Create: `requirements-desktop.txt`
- Create: `desktop/build/uta_app.spec`
- Create: `desktop/build/build_macos.sh`
- Modify: `.gitignore`

- [ ] **Step 1: Add desktop-only dependencies**

Create `requirements-desktop.txt` with `pywebview` and `pyinstaller` so CLI learners do not need desktop dependencies.

- [ ] **Step 2: Add PyInstaller spec**

Create a macOS BUNDLE spec that includes `desktop/frontend` and `examples` as data resources, hides the console window, and declares `webview.platforms.cocoa` as a hidden import.

- [ ] **Step 3: Add build script**

Create `desktop/build/build_macos.sh` that runs tests first, builds the `.app`, and zips it as `dist/UTA Desktop-macos.zip`.

- [ ] **Step 4: Ignore generated build output**

Add `dist/`, `build/`, and `*.spec.log` style generated output patterns only if they are not already ignored.

### Task 5: Verification and Desktop Build

**Files:**
- No source edits unless verification exposes a defect.

- [ ] **Step 1: Run full test suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all tests pass.

- [ ] **Step 2: Install desktop dependencies**

Run: `.venv/bin/python -m pip install -r requirements-desktop.txt`
Expected: pywebview and PyInstaller are installed into `.venv`.

- [ ] **Step 3: Build app**

Run: `bash desktop/build/build_macos.sh`
Expected: `dist/UTA Desktop.app` and `dist/UTA Desktop-macos.zip` exist.

- [ ] **Step 4: Validate package contents**

Run: `test -d "dist/UTA Desktop.app"` and `unzip -t "dist/UTA Desktop-macos.zip"`
Expected: both commands succeed.

- [ ] **Step 5: Run CLI regression smoke**

Run: `.venv/bin/python main.py --task "帮我总结一段文本：桌面打包完成后，CLI 仍然要能正常运行。"`
Expected: command exits successfully and prints either completed or failed task output without crashing.

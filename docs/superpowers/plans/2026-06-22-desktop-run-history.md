# UTA Desktop Run History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only "运行记录" view to UTA Desktop that lists previous local task runs and opens their saved result, log, and state JSON.

**Architecture:** Add a focused `desktop.history_store.HistoryStore` that reads `~/.uta/outputs/states/*_state.json` and optional `~/.uta/outputs/logs/*.log`. Expose it through `DesktopAPI.list_runs()` and `DesktopAPI.get_run()`, then add a second frontend view in the existing pywebview single-page app.

**Tech Stack:** Python 3.12, pathlib/json, pytest, pywebview bridge, vanilla HTML/CSS/JS.

---

## File Structure

- Create `desktop/history_store.py`: read-only history file access, summary extraction, safe task id handling, detail lookup.
- Create `tests/test_desktop_history_store.py`: direct unit coverage for newest-first listing, detail lookup, missing logs, invalid JSON, and path safety.
- Modify `desktop/api.py`: construct or accept a history store and expose `list_runs()` / `get_run()`.
- Modify `tests/test_desktop_api.py`: add fake history store coverage for API delegation and controlled errors.
- Modify `desktop/frontend/index.html`: add sidebar history nav, wrap current console in a task view, add hidden history view containers.
- Modify `desktop/frontend/app.js`: add view switching, load history list, select a run, render details using existing helpers.
- Modify `desktop/frontend/style.css`: style history list and detail layout without changing the current console layout.
- Modify `tests/test_desktop_frontend_assets.py`: assert the frontend includes the history entry, containers, and bridge calls.

Implementation note: the current workspace already contains untracked desktop files from the desktop app work. Before each commit, check `git diff --cached --name-status` and stage only the files named in that task.

---

### Task 1: History Store

**Files:**
- Create: `desktop/history_store.py`
- Create: `tests/test_desktop_history_store.py`

- [ ] **Step 1: Write failing HistoryStore tests**

Create `tests/test_desktop_history_store.py`:

```python
import json
import os
import time

from desktop.history_store import HistoryStore


def write_state(root, task_id, payload):
    states = root / "states"
    states.mkdir(parents=True, exist_ok=True)
    path = states / f"{task_id}_state.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def write_log(root, task_id, text):
    logs = root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    path = logs / f"{task_id}.log"
    path.write_text(text, encoding="utf-8")
    return path


def test_history_store_lists_runs_newest_first_with_compact_summaries(tmp_path):
    old_path = write_state(
        tmp_path,
        "task_old",
        {
            "task_id": "task_old",
            "status": "completed",
            "task_type": "summarize",
            "intent": "旧任务",
            "updated_at": "2026-06-21T01:00:00",
            "final_output": "旧输出",
            "results": [{"large": "payload"}],
        },
    )
    new_path = write_state(
        tmp_path,
        "task_new",
        {
            "task_id": "task_new",
            "status": "failed",
            "task_type": "data_analysis",
            "intent": "新任务",
            "updated_at": "2026-06-21T02:00:00",
            "final_output": "新输出" * 80,
        },
    )
    now = time.time()
    os.utime(old_path, (now - 60, now - 60))
    os.utime(new_path, (now, now))

    result = HistoryStore(tmp_path).list_runs()

    assert [run["task_id"] for run in result["runs"]] == ["task_new", "task_old"]
    assert result["runs"][0]["status"] == "failed"
    assert result["runs"][0]["task_type"] == "data_analysis"
    assert result["runs"][0]["intent"] == "新任务"
    assert result["runs"][0]["updated_at"] == "2026-06-21T02:00:00"
    assert result["runs"][0]["preview"].startswith("新输出")
    assert len(result["runs"][0]["preview"]) <= 123
    assert "state" not in result["runs"][0]
    assert "results" not in result["runs"][0]


def test_history_store_get_run_returns_state_final_output_and_log(tmp_path):
    write_state(
        tmp_path,
        "task_1",
        {
            "task_id": "task_1",
            "status": "completed",
            "task_type": "summarize",
            "intent": "总结",
            "final_output": "## 摘要\n完成",
        },
    )
    write_log(tmp_path, "task_1", "[Main] task received\n")

    result = HistoryStore(tmp_path).get_run("task_1")

    assert result["ok"] is True
    assert result["task_id"] == "task_1"
    assert result["state"]["status"] == "completed"
    assert result["final_output"] == "## 摘要\n完成"
    assert result["log"] == "[Main] task received\n"


def test_history_store_get_run_succeeds_when_log_is_missing(tmp_path):
    write_state(tmp_path, "task_1", {"task_id": "task_1", "final_output": "done"})

    result = HistoryStore(tmp_path).get_run("task_1")

    assert result["ok"] is True
    assert result["log"] == ""


def test_history_store_skips_invalid_json_in_list_but_reports_selected_error(tmp_path):
    write_state(tmp_path, "task_good", {"task_id": "task_good", "final_output": "done"})
    bad_path = tmp_path / "states" / "task_bad_state.json"
    bad_path.write_text("{bad json", encoding="utf-8")

    listed = HistoryStore(tmp_path).list_runs()
    selected = HistoryStore(tmp_path).get_run("task_bad")

    assert [run["task_id"] for run in listed["runs"]] == ["task_good"]
    assert selected["ok"] is False
    assert "state JSON 无效" in selected["error"]


def test_history_store_rejects_unknown_or_unsafe_task_ids(tmp_path):
    store = HistoryStore(tmp_path)

    assert store.get_run("task_missing") == {"ok": False, "error": "任务不存在"}
    unsafe = store.get_run("../task_missing")

    assert unsafe["ok"] is False
    assert unsafe["error"] == "任务不存在"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_desktop_history_store.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'desktop.history_store'`.

- [ ] **Step 3: Implement HistoryStore**

Create `desktop/history_store.py`:

```python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class HistoryStore:
    def __init__(self, output_root: Path | str):
        self.output_root = Path(output_root)
        self.states_dir = self.output_root / "states"
        self.logs_dir = self.output_root / "logs"

    def list_runs(self) -> dict[str, Any]:
        runs: list[dict[str, Any]] = []
        for path in self._state_paths():
            state = self._read_state(path)
            if not isinstance(state, dict):
                continue
            task_id = self._task_id_from_path(path)
            runs.append(self._summary(task_id, path, state))

        runs.sort(key=lambda item: item["modified_at"], reverse=True)
        return {"ok": True, "runs": runs}

    def get_run(self, task_id: str) -> dict[str, Any]:
        path = self._state_path_for_task(task_id)
        if path is None or not path.exists():
            return {"ok": False, "error": "任务不存在"}

        state = self._read_state(path)
        if not isinstance(state, dict):
            return {"ok": False, "error": "state JSON 无效"}

        log_path = self.logs_dir / f"{task_id}.log"
        log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
        return {
            "ok": True,
            "task_id": task_id,
            "state": state,
            "log": log,
            "final_output": str(state.get("final_output") or ""),
        }

    def _state_paths(self) -> list[Path]:
        if not self.states_dir.exists():
            return []
        return sorted(self.states_dir.glob("*_state.json"))

    def _state_path_for_task(self, task_id: str) -> Path | None:
        if not task_id or "/" in task_id or "\\" in task_id:
            return None
        candidate = self.states_dir / f"{task_id}_state.json"
        try:
            candidate.resolve().relative_to(self.states_dir.resolve())
        except ValueError:
            return None
        return candidate

    def _task_id_from_path(self, path: Path) -> str:
        return path.name.removesuffix("_state.json")

    def _read_state(self, path: Path) -> dict[str, Any] | None:
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return parsed if isinstance(parsed, dict) else None

    def _summary(self, task_id: str, path: Path, state: dict[str, Any]) -> dict[str, Any]:
        final_output = str(state.get("final_output") or "")
        intent = str(state.get("intent") or "")
        preview = self._preview(final_output or intent)
        return {
            "task_id": str(state.get("task_id") or task_id),
            "status": str(state.get("status") or "unknown"),
            "task_type": str(state.get("task_type") or "unknown"),
            "intent": intent,
            "updated_at": str(state.get("updated_at") or ""),
            "modified_at": self._modified_at(path),
            "preview": preview,
        }

    def _preview(self, text: str, limit: int = 120) -> str:
        normalized = " ".join(str(text).split())
        if len(normalized) <= limit:
            return normalized
        return normalized[:limit] + "..."

    def _modified_at(self, path: Path) -> str:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
```

- [ ] **Step 4: Run HistoryStore tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/test_desktop_history_store.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit HistoryStore**

Run:

```bash
git add desktop/history_store.py tests/test_desktop_history_store.py
git diff --cached --name-status
git commit -m "feat: add desktop run history store"
```

Expected staged files:

```text
A	desktop/history_store.py
A	tests/test_desktop_history_store.py
```

---

### Task 2: DesktopAPI History Bridge

**Files:**
- Modify: `desktop/api.py`
- Modify: `tests/test_desktop_api.py`

- [ ] **Step 1: Write failing DesktopAPI history tests**

Append this fake after `FakeRunner` in `tests/test_desktop_api.py`:

```python
class FakeHistoryStore:
    def __init__(self):
        self.listed = False
        self.requested_task_ids = []

    def list_runs(self):
        self.listed = True
        return {
            "ok": True,
            "runs": [
                {
                    "task_id": "task_fake",
                    "status": "completed",
                    "task_type": "summarize",
                    "intent": "总结",
                    "updated_at": "2026-06-21T01:00:00",
                    "modified_at": "2026-06-21T01:00:00+00:00",
                    "preview": "done",
                }
            ],
        }

    def get_run(self, task_id):
        self.requested_task_ids.append(task_id)
        if task_id == "task_fake":
            return {
                "ok": True,
                "task_id": task_id,
                "state": {"task_id": task_id, "status": "completed"},
                "log": "[Main] task received\n",
                "final_output": "done",
            }
        return {"ok": False, "error": "任务不存在"}
```

Append these tests to `tests/test_desktop_api.py`:

```python
def test_desktop_api_lists_history_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    history_store = FakeHistoryStore()
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=FakeRunner(),
        history_store=history_store,
    )

    result = api.list_runs()

    assert result["ok"] is True
    assert result["runs"][0]["task_id"] == "task_fake"
    assert history_store.listed is True


def test_desktop_api_gets_history_run_detail(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    history_store = FakeHistoryStore()
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=FakeRunner(),
        history_store=history_store,
    )

    result = api.get_run("task_fake")

    assert result["ok"] is True
    assert result["final_output"] == "done"
    assert result["log"] == "[Main] task received\n"
    assert history_store.requested_task_ids == ["task_fake"]


def test_desktop_api_reports_missing_history_run(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=FakeRunner(),
        history_store=FakeHistoryStore(),
    )

    result = api.get_run("task_missing")

    assert result == {"ok": False, "error": "任务不存在"}
```

- [ ] **Step 2: Run DesktopAPI tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_desktop_api.py::test_desktop_api_lists_history_runs tests/test_desktop_api.py::test_desktop_api_gets_history_run_detail tests/test_desktop_api.py::test_desktop_api_reports_missing_history_run -q
```

Expected: FAIL with `TypeError: DesktopAPI.__init__() got an unexpected keyword argument 'history_store'`.

- [ ] **Step 3: Implement DesktopAPI history bridge**

Modify imports at the top of `desktop/api.py`:

```python
from desktop.history_store import HistoryStore
from desktop.paths import resource_path, uta_home
from desktop.runner import TaskRunner
from desktop.settings_store import SettingsStore
```

Modify `DesktopAPI.__init__`:

```python
class DesktopAPI:
    def __init__(
        self,
        settings_store: SettingsStore | None = None,
        runner: TaskRunner | None = None,
        history_store: HistoryStore | None = None,
    ):
        self.settings_store = settings_store if settings_store is not None else SettingsStore()
        self.runner = runner if runner is not None else TaskRunner(settings_store=self.settings_store)
        self.history_store = history_store if history_store is not None else HistoryStore(uta_home() / "outputs")
```

Add these methods before `get_result`:

```python
    def list_runs(self) -> dict[str, Any]:
        try:
            return self.history_store.list_runs()
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def get_run(self, task_id: str) -> dict[str, Any]:
        try:
            return self.history_store.get_run(str(task_id or ""))
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
```

- [ ] **Step 4: Run DesktopAPI tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/test_desktop_api.py tests/test_desktop_history_store.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit DesktopAPI bridge**

Run:

```bash
git add desktop/api.py tests/test_desktop_api.py
git diff --cached --name-status
git commit -m "feat: expose desktop run history api"
```

Expected staged files:

```text
A	desktop/api.py
A	tests/test_desktop_api.py
```

---

### Task 3: Frontend History View

**Files:**
- Modify: `desktop/frontend/index.html`
- Modify: `desktop/frontend/app.js`
- Modify: `desktop/frontend/style.css`
- Modify: `tests/test_desktop_frontend_assets.py`

- [ ] **Step 1: Write failing frontend asset tests**

Append these tests to `tests/test_desktop_frontend_assets.py`:

```python
def test_frontend_includes_run_history_view():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    assert 'id="openHistory"' in html
    assert "运行记录" in html
    assert 'id="taskView"' in html
    assert 'id="historyView"' in html
    assert 'id="historyList"' in html
    assert 'id="historyReport"' in html
    assert 'id="historyLogPanel"' in html
    assert 'id="historyStateJson"' in html


def test_frontend_calls_history_bridge_methods():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'callApi("list_runs")' in js
    assert 'callApi("get_run", taskId)' in js
    assert "function showHistoryView" in js
    assert "function renderHistoryList" in js
    assert "function selectHistoryRun" in js
```

- [ ] **Step 2: Run frontend asset tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_desktop_frontend_assets.py::test_frontend_includes_run_history_view tests/test_desktop_frontend_assets.py::test_frontend_calls_history_bridge_methods -q
```

Expected: FAIL because the history view markup and JavaScript functions do not exist.

- [ ] **Step 3: Add history markup**

In `desktop/frontend/index.html`, change the sidebar nav buttons to:

```html
        <button class="nav active" type="button" id="openTaskView">任务</button>
        <button class="nav" type="button" id="openHistory">运行记录</button>
        <button class="nav" type="button" id="openSettingsSide">设置</button>
```

Change the current task workspace opening tag from:

```html
        <section class="workspace">
```

to:

```html
        <section class="workspace" id="taskView">
```

Add this sibling section immediately after the task workspace:

```html
        <section class="workspace historyWorkspace hidden" id="historyView">
          <div class="historyListColumn">
            <section class="panel historyPanel">
              <div class="panelHead">
                <h3>运行记录</h3>
                <button class="button secondary compact" type="button" id="refreshHistory">刷新</button>
              </div>
              <div class="historyList" id="historyList"></div>
            </section>
          </div>

          <div class="historyDetailColumn">
            <section class="panel reportPanel">
              <div class="panelHead">
                <h3>历史结果</h3>
                <span id="historyTaskMeta">未选择</span>
              </div>
              <article class="report empty" id="historyReport">选择一条运行记录</article>
            </section>

            <section class="panel logsPanel historyLogsPanel">
              <div class="panelHead">
                <h3>历史日志</h3>
              </div>
              <div class="logs" id="historyLogPanel"></div>
            </section>

            <details class="stateBox">
              <summary>历史 state.json</summary>
              <pre id="historyStateJson">{
  "status": "idle",
  "task_id": null
}</pre>
            </details>
          </div>
        </section>
```

- [ ] **Step 4: Add history JavaScript**

In `desktop/frontend/app.js`, add these elements to `els`:

```javascript
  openTaskView: document.getElementById("openTaskView"),
  openHistory: document.getElementById("openHistory"),
  taskView: document.getElementById("taskView"),
  historyView: document.getElementById("historyView"),
  refreshHistory: document.getElementById("refreshHistory"),
  historyList: document.getElementById("historyList"),
  historyTaskMeta: document.getElementById("historyTaskMeta"),
  historyReport: document.getElementById("historyReport"),
  historyLogPanel: document.getElementById("historyLogPanel"),
  historyStateJson: document.getElementById("historyStateJson"),
```

Add `historyRuns: []` to `state`:

```javascript
  historyRuns: []
```

Add these functions after `loadExample()`:

```javascript
function setActiveNav(button) {
  document.querySelectorAll(".nav").forEach((item) => {
    item.classList.toggle("active", item === button);
  });
}

function showTaskView() {
  els.taskView.classList.remove("hidden");
  els.historyView.classList.add("hidden");
  setActiveNav(els.openTaskView);
}

async function showHistoryView() {
  els.taskView.classList.add("hidden");
  els.historyView.classList.remove("hidden");
  setActiveNav(els.openHistory);
  await loadHistoryRuns();
}

async function loadHistoryRuns() {
  try {
    const result = await callApi("list_runs");
    if (!result.ok) {
      showToast("读取运行记录失败", result.error || "未知错误");
      return;
    }
    state.historyRuns = result.runs || [];
    renderHistoryList(state.historyRuns);
    if (state.historyRuns.length > 0) {
      await selectHistoryRun(state.historyRuns[0].task_id);
    } else {
      renderEmptyHistoryDetail();
    }
  } catch (error) {
    showToast("读取运行记录失败", error.message);
  }
}

function renderHistoryList(runs) {
  if (!runs.length) {
    els.historyList.innerHTML = '<div class="emptyState">暂无运行记录</div>';
    return;
  }
  els.historyList.innerHTML = runs.map((run) => `
    <button class="historyItem" type="button" data-task-id="${escapeHtml(run.task_id)}">
      <span><strong>${escapeHtml(run.task_id)}</strong><small>${escapeHtml(run.task_type || "unknown")} · ${escapeHtml(run.status || "unknown")}</small></span>
      <small>${escapeHtml(run.preview || run.intent || "无输出")}</small>
    </button>
  `).join("");
  els.historyList.querySelectorAll(".historyItem").forEach((button) => {
    button.addEventListener("click", () => selectHistoryRun(button.dataset.taskId));
  });
}

async function selectHistoryRun(taskId) {
  try {
    const result = await callApi("get_run", taskId);
    if (!result.ok) {
      showToast("读取详情失败", result.error || "未知错误");
      return;
    }
    els.historyList.querySelectorAll(".historyItem").forEach((item) => {
      item.classList.toggle("active", item.dataset.taskId === taskId);
    });
    const runState = result.state || {};
    els.historyTaskMeta.textContent = `${runState.status || "unknown"} · ${runState.task_type || "unknown"}`;
    els.historyReport.className = "report";
    els.historyReport.innerHTML = renderMarkdown(result.final_output || "");
    els.historyLogPanel.textContent = result.log || "";
    els.historyStateJson.textContent = JSON.stringify(runState, null, 2);
  } catch (error) {
    showToast("读取详情失败", error.message);
  }
}

function renderEmptyHistoryDetail() {
  els.historyTaskMeta.textContent = "未选择";
  els.historyReport.className = "report empty";
  els.historyReport.textContent = "暂无运行记录";
  els.historyLogPanel.textContent = "";
  els.historyStateJson.textContent = JSON.stringify({ status: "idle", task_id: null }, null, 2);
}
```

Update `bindEvents()` with:

```javascript
  els.openTaskView.addEventListener("click", showTaskView);
  els.openHistory.addEventListener("click", showHistoryView);
  els.refreshHistory.addEventListener("click", loadHistoryRuns);
```

- [ ] **Step 5: Add history CSS**

Append to `desktop/frontend/style.css`:

```css
.hidden {
  display: none;
}

.historyWorkspace {
  grid-template-columns: minmax(300px, 0.72fr) minmax(460px, 1.28fr);
}

.historyListColumn,
.historyDetailColumn {
  min-height: 0;
  display: grid;
  gap: 16px;
}

.historyPanel {
  min-height: 560px;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  overflow: hidden;
}

.historyList {
  min-height: 0;
  overflow: auto;
  padding: 12px;
  display: grid;
  align-content: start;
  gap: 10px;
}

.historyItem {
  width: 100%;
  min-height: 74px;
  padding: 11px;
  display: grid;
  gap: 6px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  text-align: left;
}

.historyItem:hover,
.historyItem.active {
  border-color: var(--accent);
}

.historyItem strong,
.historyItem small {
  display: block;
  overflow-wrap: anywhere;
}

.historyItem small,
#historyTaskMeta {
  color: var(--muted);
  font-family: var(--mono);
  font-size: 12px;
}

.emptyState {
  padding: 24px 12px;
  color: var(--muted);
  text-align: center;
}

.historyLogsPanel {
  min-height: 220px;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  overflow: hidden;
}
```

- [ ] **Step 6: Run frontend asset tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/test_desktop_frontend_assets.py -q
```

Expected: PASS.

- [ ] **Step 7: Run selected desktop tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_desktop_history_store.py tests/test_desktop_api.py tests/test_desktop_frontend_assets.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit frontend history view**

Run:

```bash
git add desktop/frontend/index.html desktop/frontend/app.js desktop/frontend/style.css tests/test_desktop_frontend_assets.py
git diff --cached --name-status
git commit -m "feat: add desktop run history view"
```

Expected staged files:

```text
A	desktop/frontend/index.html
A	desktop/frontend/app.js
A	desktop/frontend/style.css
A	tests/test_desktop_frontend_assets.py
```

---

### Task 4: Verification

**Files:**
- No source edits unless verification exposes a defect.

- [ ] **Step 1: Run full test suite**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected: `141 passed` or higher, with zero failures. The exact count may be higher if additional tests are added during execution.

- [ ] **Step 2: Verify history API manually with temporary files**

Run:

```bash
UTA_HOME=/private/tmp/uta-history-smoke .venv/bin/python - <<'PY'
import json
import os
from pathlib import Path

home = Path(os.environ["UTA_HOME"])
states = home / "outputs" / "states"
logs = home / "outputs" / "logs"
states.mkdir(parents=True, exist_ok=True)
logs.mkdir(parents=True, exist_ok=True)
(states / "task_smoke_state.json").write_text(json.dumps({
    "task_id": "task_smoke",
    "status": "completed",
    "task_type": "summarize",
    "intent": "smoke",
    "final_output": "## 摘要\n历史记录 smoke"
}, ensure_ascii=False), encoding="utf-8")
(logs / "task_smoke.log").write_text("[Main] task received\n", encoding="utf-8")

from desktop.api import DesktopAPI

api = DesktopAPI()
listed = api.list_runs()
detail = api.get_run("task_smoke")
print(listed["ok"], listed["runs"][0]["task_id"])
print(detail["ok"], detail["final_output"].splitlines()[0], detail["log"].strip())
PY
```

Expected output:

```text
True task_smoke
True ## 摘要 [Main] task received
```

- [ ] **Step 3: Verify git status and staged state**

Run:

```bash
git status --short
git diff --cached --name-status
```

Expected: no staged files left after task commits. Unrelated pre-existing dirty files may remain; do not revert them.

- [ ] **Step 4: Final commit if verification required fixes**

If Step 1 or Step 2 exposed a defect and source files were changed, run:

```bash
git add desktop/history_store.py desktop/api.py desktop/frontend/index.html desktop/frontend/app.js desktop/frontend/style.css tests/test_desktop_history_store.py tests/test_desktop_api.py tests/test_desktop_frontend_assets.py
git diff --cached --name-status
git commit -m "fix: stabilize desktop run history"
```

Expected: only history-related files are staged and committed.

# UTA Desktop Run History Design

> Status: approved for planning
> Date: 2026-06-22

## Goal

Add a lightweight "运行记录" view to UTA Desktop so users can review previous local runs from `~/.uta/outputs` without leaving the app.

The first version only supports viewing history and opening details. It does not support search, deletion, export, or opening folders.

## Current Context

UTA Desktop is a single-window pywebview app. The frontend in `desktop/frontend/` calls `window.pywebview.api`, which is backed by `desktop.api.DesktopAPI`.

Task execution already writes:

- state files under `~/.uta/outputs/states/<task_id>_state.json`
- logs under `~/.uta/outputs/logs/<task_id>.log`
- task metadata and final output inside the saved state JSON

The history feature should read these files. It should not change the task loop, memory provider, LLM client, or packaging architecture.

## User Experience

The sidebar adds a new "运行记录" navigation item between "任务" and "设置".

When the user selects "运行记录", the main area switches from the task console to a history view:

- left side: recent runs, newest first
- right side: selected run details

Each list item shows:

- task id
- status
- task type
- last updated time if present
- a short preview from the final output or intent

The details panel shows:

- task id, status, task type, and intent
- rendered final output using the existing Markdown-ish renderer
- log text from the matching `.log` file
- full `state.json` in a collapsible or scrollable pre block

If there are no saved runs, the history view shows an empty state instead of an error.

## API Design

Add a small history reader, preferably `desktop/history_store.py`, with two responsibilities:

- `list_runs()`: read `states/*_state.json`, return compact summaries sorted by file modified time descending
- `get_run(task_id)`: read a single state file and optional matching log file

Expose these through `DesktopAPI`:

```python
def list_runs(self) -> dict[str, Any]:
    ...

def get_run(self, task_id: str) -> dict[str, Any]:
    ...
```

`list_runs()` response:

```json
{
  "ok": true,
  "runs": [
    {
      "task_id": "task_20260621_055703",
      "status": "completed",
      "task_type": "summarize",
      "intent": "总结文本",
      "updated_at": "2026-06-21T05:57:27",
      "modified_at": "2026-06-21T05:57:27",
      "preview": "## 摘要..."
    }
  ]
}
```

`get_run(task_id)` response:

```json
{
  "ok": true,
  "task_id": "task_20260621_055703",
  "state": {},
  "log": "...",
  "final_output": "..."
}
```

If a matching log file does not exist, `get_run()` returns an empty `log` string and still succeeds.

If the task id is unknown, `get_run()` returns `{"ok": false, "error": "任务不存在"}`.

## Data Handling

History is read-only.

The reader should derive task ids from filenames ending in `_state.json`. It should only resolve files inside the configured output root, so arbitrary path input cannot escape into other directories.

Invalid JSON files should not break the entire history view. `list_runs()` should skip unreadable or invalid state files, while `get_run(task_id)` should return a clear error for an invalid selected state.

Summaries should avoid sending large full state payloads. The full JSON is only returned by `get_run()`.

## Frontend Design

The existing single-page frontend remains vanilla HTML, CSS, and JS.

Add:

- a sidebar button with id like `openHistory`
- a task console container for the current task UI
- a history container hidden by default
- a run list element
- a run detail result panel
- a log panel for historical logs
- a state JSON panel for historical state

Navigation toggles which view is visible and updates the active sidebar item. Selecting "运行记录" calls `list_runs()`. Selecting a run calls `get_run(task_id)`.

The history detail can reuse existing helpers:

- `renderMarkdown()` for final output
- `escapeHtml()` for safe text rendering
- `showToast()` for API errors

## Error Handling

The frontend should display toast errors for API failures and keep the current view stable.

Expected states:

- no runs: show a readable empty state
- missing log: show an empty log area
- invalid selected state: show the API error
- bridge not ready: same behavior as current settings and task actions

## Testing

Use TDD for implementation.

Backend tests:

- `HistoryStore.list_runs()` returns newest-first compact summaries
- `HistoryStore.get_run()` returns state, final output, and log
- missing log succeeds with an empty string
- invalid or unknown task id returns a controlled error through `DesktopAPI`
- `DesktopAPI.list_runs()` and `DesktopAPI.get_run()` delegate to the history reader

Frontend asset tests:

- sidebar includes the "运行记录" entry
- frontend JS calls `list_runs` and `get_run`
- history view has separate list, result, log, and state containers

Regression tests:

- existing desktop API tests still pass
- existing frontend layout tests still pass
- full pytest suite passes before completion

## Out Of Scope

- deleting runs
- searching or filtering runs
- exporting reports
- opening Finder or output folders
- changing where current tasks write output
- editing or replaying historical tasks

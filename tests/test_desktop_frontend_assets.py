from pathlib import Path


FRONTEND_ROOT = Path("desktop/frontend")


def test_frontend_does_not_draw_duplicate_traffic_lights():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert 'class="traffic"' not in html
    assert ".traffic" not in css


def test_frontend_keeps_plan_and_logs_in_separate_scroll_regions():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert "grid-template-rows: auto auto auto;" in css
    assert ".leftColumn {\n  align-content: start;" in css
    assert ".grow {\n  min-height: 300px;\n  max-height: 360px;" in css
    assert ".logsPanel {\n  min-height: 0;\n  display: grid;" in css
    assert ".logs {\n  min-height: 0;\n  height: auto;" in css


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


def test_frontend_includes_memory_view():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    assert 'id="openMemory"' in html
    assert "记忆" in html
    assert 'id="memoryView"' in html
    assert 'id="memoryShortTerm"' in html
    assert 'id="memoryTaskHistory"' in html
    assert 'id="memoryLessons"' in html
    assert 'id="memoryNegativeRules"' in html
    assert 'id="memorySkillCandidates"' in html


def test_frontend_calls_memory_bridge_method():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'callApi("get_memory_overview")' in js
    assert "function showMemoryView" in js
    assert "function renderMemoryOverview" in js


def test_frontend_handles_replanned_progress_event():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'event.type === "replanned"' in js
    assert "replan" in js.lower()


def test_frontend_preserves_history_log_whitespace():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert ".historyLogsPanel .logs" in css
    assert "white-space: pre-wrap;" in css

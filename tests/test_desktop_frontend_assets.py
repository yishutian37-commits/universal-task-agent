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

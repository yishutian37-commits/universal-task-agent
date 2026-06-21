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

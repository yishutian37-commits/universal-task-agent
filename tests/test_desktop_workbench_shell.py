from pathlib import Path


FRONTEND_ROOT = Path("desktop/frontend")


def test_workbench_loads_shell_before_app():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    assert '<script src="shell.js"></script>' in html
    assert html.index('src="shell.js"') < html.index('src="app.js"')


def test_shell_exposes_workbench_state_helpers():
    js = (FRONTEND_ROOT / "shell.js").read_text(encoding="utf-8")

    assert "window.UTAShell" in js
    assert "function groupConversations" in js
    assert "function activatePage" in js
    assert "function setTaskPanelOpen" in js
    assert "function activateTaskTab" in js

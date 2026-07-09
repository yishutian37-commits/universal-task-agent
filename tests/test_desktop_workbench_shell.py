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


def test_sidebar_is_conversation_first_and_keeps_capability_entries():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    assert 'id="newConversation"' in html
    assert 'id="conversationSearch"' in html
    assert 'id="conversationList"' in html
    assert 'data-page-target="knowledge"' in html
    assert 'data-page-target="memory"' in html
    assert 'data-page-target="capabilities"' in html
    assert 'id="openHistory"' not in html
    assert 'id="historyView"' not in html


def test_app_loads_and_opens_conversations_from_sidebar():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'callApi("list_conversations")' in js
    assert 'callApi("new_conversation")' in js
    assert 'callApi("get_conversation", conversationId)' in js
    assert "function loadConversationSidebar" in js
    assert "function renderConversationSidebar" in js
    assert "function startNewConversation" in js
    assert "function openConversation" in js


def test_window_layout_uses_the_full_height_after_titlebar_removal():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert 'class="titlebar"' not in html
    assert ".window {\n  height: 100%;\n  display: grid;\n  grid-template-rows: minmax(0, 1fr);\n}" in css


def test_workbench_has_center_conversation_and_contextual_task_panel():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    assert 'id="conversationTitle"' in html
    assert 'id="workspaceSelector"' in html
    assert 'id="chatMessages"' in html
    assert 'id="taskInput"' in html
    assert 'id="chatDetailPanel"' in html
    for name in ["progress", "files", "changes", "artifacts", "diagnostics"]:
        assert f'data-task-tab="{name}"' in html
        assert f'data-task-panel="{name}"' in html


def test_logs_and_state_are_diagnostics_only():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    diagnostics = html.split('data-task-panel="diagnostics"', 1)[1]
    assert 'id="logPanel"' in diagnostics
    assert 'id="stateJson"' in diagnostics


def test_shell_syncs_task_tab_aria_state():
    js = (FRONTEND_ROOT / "shell.js").read_text(encoding="utf-8")

    assert 'button.setAttribute("aria-selected", String(active));' in js
    assert 'panel.setAttribute("aria-hidden", String(!active));' in js

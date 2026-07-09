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

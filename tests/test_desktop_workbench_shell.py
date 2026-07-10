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


def test_secondary_capability_pages_keep_titles_routes_and_data_nodes():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    for page_name, title, view_id, loader in [
        ("knowledge", "知识库", "knowledgeView", "loadKnowledgeBase"),
        ("memory", "记忆中心", "memoryView", "loadMemoryOverview"),
        ("capabilities", "技能与工具", "skillsView", "loadSkillOverview"),
    ]:
        assert f'<h1>{title}</h1>' in html
        assert f'id="{view_id}" data-page="{page_name}"' in html
        assert f'if (pageName === "{page_name}") await {loader}();' in js


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


def test_workbench_uses_neutral_tokens_without_gradients():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert "--app-bg: #f5f5f3;" in css
    assert "--sidebar-bg: #ecece8;" in css
    assert "--panel-bg: #ffffff;" in css
    assert "--action: #2f64d6;" in css
    assert "linear-gradient" not in css
    assert "fonts.googleapis.com" not in (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")


def test_workbench_has_stable_three_column_and_drawer_layouts():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert "grid-template-columns: 260px minmax(0, 1fr);" in css
    assert "grid-template-columns: minmax(0, 1fr) 340px;" in css
    assert ".chatWorkspace {\n  position: relative;\n  height: 100%;\n  min-height: 0;\n  padding: 0;\n  display: grid;\n  grid-template-columns: minmax(0, 1fr);\n  gap: 0;\n  overflow: hidden;\n}" in css
    assert "@media (max-width: 1179px)" in css
    assert ".taskPanel" in css
    assert "position: absolute;" in css


def test_frontend_conversation_surface_keeps_composer_at_bottom():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert ".conversationSurface" in css
    assert "grid-template-rows: auto minmax(0, 1fr) auto;" in css
    assert ".chatMessages" in css
    assert "overflow-y: auto;" in css
    assert ".chatComposer" in css

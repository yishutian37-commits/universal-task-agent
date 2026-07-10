from pathlib import Path


FRONTEND_ROOT = Path("desktop/frontend")


def test_workbench_loads_shell_before_app():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    assert '<script src="shell.js"></script>' in html
    assert html.index('src="shell.js"') < html.index('src="app.js"')


def test_shell_exposes_workbench_state_helpers():
    js = (FRONTEND_ROOT / "shell.js").read_text(encoding="utf-8")

    assert "root.UTAShell = shell" in js
    assert "function groupConversations" in js
    assert "function activatePage" in js
    assert "function setTaskPanelOpen" in js
    assert "function activateTaskTab" in js
    assert "function activateMemoryTab" in js
    assert "function handleMemoryTabKeydown" in js
    assert "function groupMemoryFacts" in js
    assert "function compactMemoryText" in js
    assert "function dedupeMemoryLessons" in js


def test_memory_center_has_four_accessible_tabs_and_dedicated_panels():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    assert 'class="workspace memoryCenterWorkspace hidden" id="memoryView"' in html
    assert 'class="memoryTabs" role="tablist" aria-label="记忆中心"' in html
    for name in ["long-term", "session", "learning", "archive"]:
        assert f'id="memoryTab-{name}"' in html
        assert f'aria-controls="memoryPanel-{name}"' in html
        assert f'data-memory-tab="{name}"' in html
        assert f'id="memoryPanel-{name}"' in html
        assert f'aria-labelledby="memoryTab-{name}"' in html
        assert f'data-memory-panel="{name}"' in html


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


def test_task_panel_toggle_and_tabs_have_complete_keyboard_aria_contract():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    js = (FRONTEND_ROOT / "shell.js").read_text(encoding="utf-8")
    app = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    toggle = html.split('id="toggleTaskPanel"', 1)[1].split(">", 1)[0]
    assert 'aria-controls="chatDetailPanel"' in toggle
    assert 'aria-expanded="false"' in toggle
    for name in ["progress", "files", "changes", "artifacts", "diagnostics"]:
        tab = html.split(f'id="taskTab-{name}"', 1)[1].split(">", 1)[0]
        assert f'tabindex="{0 if name == "progress" else -1}"' in tab
    assert "function handleTaskTabKeydown" in js
    assert 'button.tabIndex = active ? 0 : -1;' in js
    assert '["ArrowLeft", "ArrowRight", "Home", "End"]' in js
    assert 'toggle.setAttribute("aria-expanded", String(open));' in js
    assert "window.UTAShell.handleTaskTabKeydown(event)" in app


def test_conversation_sidebar_marks_the_current_conversation():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert "const active = conversation.conversation_id === state.conversationId;" in js
    assert 'class="conversationItem${active ? " active" : ""}"' in js
    assert 'aria-current="${active ? "true" : "false"}"' in js


def test_plan_and_handoff_use_the_same_761_and_760_pixel_boundary():
    plan = Path("docs/superpowers/plans/2026-07-10-uta-codex-workbench-phase-1-shell.md").read_text(encoding="utf-8")
    handoff = Path("docs/superpowers/progress/2026-07-10-uta-codex-workbench-phase-1-handoff.md").read_text(encoding="utf-8")

    assert "761px-1179px 右侧任务抽屉" in plan
    assert "760px 及以下可折叠会话侧栏" in plan
    assert "@media (max-width: 760px)" in plan
    assert "@media (max-width: 759px)" not in plan
    assert "761px 至 1179px 任务面板变为抽屉" in handoff
    assert "760px 及以下侧栏收窄" in handoff
    assert not handoff.endswith("\n\n")


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
    assert "@media (max-width: 760px)" in css
    drawer_media = css.split("@media (max-width: 1179px)", 1)[1].split("@media (max-width: 760px)", 1)[0]

    assert "grid-template-columns: 260px minmax(0, 1fr);" in css
    assert "grid-template-columns: minmax(0, 1fr) 340px;" in css
    assert ".chatWorkspace {\n  position: relative;\n  height: 100%;\n  min-height: 0;\n  padding: 0;\n  display: grid;\n  grid-template-columns: minmax(0, 1fr);\n  gap: 0;\n  overflow: hidden;\n}" in css
    assert "@media (max-width: 1179px)" in css
    assert ".taskPanel {\n    position: absolute;\n    z-index: 20;\n    top: 0;\n    right: 0;\n    bottom: 0;" in drawer_media


def test_secondary_workspaces_collapse_to_one_column_without_changing_chat_drawer():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")
    assert "@media (max-width: 760px)" in css
    drawer_media = css.split("@media (max-width: 1179px)", 1)[1].split("@media (max-width: 760px)", 1)[0]

    assert ".workspace:not(.chatWorkspace) {\n    grid-template-columns: minmax(0, 1fr);\n    align-content: start;\n    align-items: start;\n  }" in drawer_media
    assert ".chatWorkspace,\n  .chatWorkspace.task-panel-open {\n    grid-template-columns: minmax(0, 1fr);\n  }" in drawer_media


def test_frontend_conversation_surface_keeps_composer_at_bottom():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert ".conversationSurface" in css
    assert "grid-template-rows: auto minmax(0, 1fr) auto;" in css
    assert ".chatMessages" in css
    assert "overflow-y: auto;" in css
    assert ".chatComposer" in css

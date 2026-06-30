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


def test_frontend_uses_checklist_markers_for_step_status():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert "function stepMarkerFor" in js
    assert '"[ ]"' in js
    assert '"[x]"' in js
    assert '"[...]"' in js
    assert '"[!]"' in js
    assert "kind === \"done\" ? \"✓\"" not in js
    assert "grid-template-columns: 52px minmax(0, 1fr) auto;" in css


def test_frontend_preserves_history_log_whitespace():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert ".historyLogsPanel .logs" in css
    assert "white-space: pre-wrap;" in css


def test_frontend_markdown_renderer_handles_common_markdown():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert 'trimmed.startsWith("# ")' in js
    assert "function renderInlineMarkdown" in js
    assert "<strong>" in js
    assert 'ensureList("ol")' in js
    assert ".report h1" in css
    assert ".report ol" in css


def test_frontend_includes_chat_surface_and_detail_panel():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    assert 'id="chatMessages"' in html
    assert 'id="taskInput"' in html
    assert 'id="runTask"' in html
    assert 'id="chatDetailPanel"' in html
    assert 'id="planList"' in html
    assert 'id="logPanel"' in html
    assert 'id="stateJson"' in html
    assert "执行详情" in html


def test_frontend_chat_styles_exist():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert ".chatWorkspace" in css
    assert ".chatMessages" in css
    assert ".chatMessage.user" in css
    assert ".chatMessage.assistant" in css
    assert ".chatComposer" in css
    assert ".detailColumn" in css


def test_frontend_chat_layout_keeps_messages_above_bottom_composer():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert ".chatColumn {\n  grid-template-rows: minmax(0, 1fr);\n}" in css
    assert ".chatPanel {\n  height: 100%;" in css
    assert "  display: grid;\n  grid-template-rows: auto minmax(0, 1fr) auto;" in css
    assert ".chatMessages {\n  min-height: 0;" in css
    assert ".chatComposer {\n  border-top: 1px solid var(--border);\n  background: var(--surface);" in css
    assert ".chatComposer {\n  border-top: 1px solid var(--border);\n  background: var(--surface);\n  margin-top: auto;" not in css
    assert "flex-shrink: 0;" in css
    assert 'els.taskInput.value = "";' in js
    assert "chatPanel.style.height" not in js
    assert "chatMessages.style.height" not in js
    assert "fixChatLayout" not in js


def test_frontend_hidden_report_cannot_create_extra_chat_row():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert 'class="report empty hidden" id="report"' in html
    assert ".hidden {\n  display: none !important;" in css


def test_frontend_single_column_keeps_chat_panel_viewport_bound():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert "@media (max-width: 1060px)" in css
    assert ".chatColumn {\n    height: calc(100vh - 154px);\n    min-height: 640px;\n  }" in css
    assert ".chatPanel {\n    height: 100%;\n    min-height: 0;\n  }" in css
    assert ".chatPanel {\n    height: auto;" not in css


def test_frontend_chat_messages_stay_near_composer_while_running():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert ".chatMessages {\n  min-height: 0;\n  overflow-y: auto;\n  padding: 18px;\n  display: flex;" in css
    assert "  flex-direction: column;" in css
    assert ".chatMessages > .chatMessage:first-child" not in css


def test_frontend_calls_chat_bridge_methods_and_updates_messages():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'callApi("run_chat_message"' in js
    assert 'callApi("sync_chat_result"' in js
    assert "function addChatMessage" in js
    assert "function updateAssistantMessage" in js
    assert "function renderChatMessages" in js
    assert "pendingAssistantId" in js


def test_frontend_shows_progress_inside_assistant_message():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert "function appendAssistantProgress" in js
    assert "function renderMessageProgress" in js
    assert 'appendAssistantProgress(state.taskId, "收到任务，正在解析...")' in js
    assert 'appendAssistantProgress(state.taskId, `开始步骤 ${data.step_id}：${data.goal}`)' in js
    assert ".messageProgress" in css
    assert ".progressLine" in css


def test_frontend_handles_direct_chat_replies():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert "result.direct" in js
    assert "updatePendingAssistant({ content: result.message" in js


def test_frontend_task_completed_updates_assistant_message_not_report_panel_only():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'event.type === "task_completed"' in js
    assert "updateAssistantMessage" in js
    assert "renderMarkdown(state.reportText)" in js


def test_frontend_can_load_conversation_history():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'callApi("list_conversations")' in js
    assert 'callApi("get_conversation", conversationId)' in js
    assert "function loadConversationHistory" in js
    assert "function selectConversation" in js

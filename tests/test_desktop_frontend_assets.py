from pathlib import Path


FRONTEND_ROOT = Path("desktop/frontend")


def test_frontend_does_not_draw_duplicate_traffic_lights():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert 'class="traffic"' not in html
    assert ".traffic" not in css


def test_frontend_keeps_task_details_in_tabbed_panel():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    for name in ["progress", "files", "changes", "artifacts", "diagnostics"]:
        assert f'data-task-tab="{name}"' in html
        assert f'data-task-panel="{name}"' in html


def test_frontend_task_panel_has_minimum_functional_layout():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert ".conversationSurface {\n  min-width: 0;\n  min-height: 0;\n  height: 100%;\n  display: grid;\n  grid-template-rows: auto minmax(0, 1fr) auto;\n  overflow: hidden;\n}" in css
    assert ".chatWorkspace.task-panel-open {\n  grid-template-columns: minmax(0, 1fr) minmax(320px, 0.82fr);\n}" in css
    assert ".taskPanel {\n  min-width: 0;\n  min-height: 0;\n  display: grid;\n  grid-template-rows: auto auto minmax(0, 1fr);\n  overflow: hidden;\n}" in css
    assert ".taskPanel.collapsed {\n  display: none;\n}" in css
    assert ".chatMessages {\n  min-height: 0;\n  overflow-y: auto;" in css
    assert ".chatComposer {\n  border-top: 1px solid var(--border);\n  background: var(--surface);\n  min-height: 0;\n}" in css


def test_frontend_task_tabs_have_stable_aria_relationships():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    for name in ["progress", "files", "changes", "artifacts", "diagnostics"]:
        selected = "true" if name == "progress" else "false"
        hidden = "false" if name == "progress" else "true"
        assert f'id="taskTab-{name}" role="tab" aria-selected="{selected}" aria-controls="taskPanel-{name}"' in html
        assert f'id="taskPanel-{name}" role="tabpanel" aria-labelledby="taskTab-{name}" aria-hidden="{hidden}"' in html


def test_frontend_task_panel_and_stop_control_follow_run_lifecycle():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
    reset_start = js.index("function resetRunSurface")
    run_start = js.index("async function runTask", reset_start)
    direct_start = js.index("if (result.direct)", run_start)
    task_start = js.index("state.running = true", direct_start)
    progress_start = js.index("async function handleProgress")
    completed_start = js.index('if (event.type === "task_completed")', progress_start)
    error_start = js.index('if (event.type === "error")', completed_start)
    cancelled_start = js.index('if (event.type === "cancelled")', error_start)

    assert "setTaskPanelOpen(false);" in js[reset_start:run_start]
    assert "setTaskPanelOpen(false);" in js[direct_start:task_start]
    assert "setStopTaskVisible(false);" in js[reset_start:run_start]
    assert "setStopTaskVisible(false);" in js[direct_start:task_start]
    assert "setStopTaskVisible(true);" in js[task_start:js.index("} catch", task_start)]
    assert "setStopTaskVisible(false);" in js[completed_start:error_start]
    assert "setStopTaskVisible(false);" in js[error_start:]
    assert "setStopTaskVisible(false);" in js[cancelled_start:]
    assert "function setStopTaskVisible" in js
    assert "async function stopTask" in js
    assert 'callApi("cancel_task", state.taskId)' in js
    assert 'els.stopTask.addEventListener("click", stopTask);' in js


def test_frontend_does_not_revive_tasks_that_finish_before_api_return():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert "terminalTaskIds: new Set()" in js
    assert "state.terminalTaskIds.add(terminalTaskId);" in js
    assert "if (state.terminalTaskIds.has(result.task_id))" in js
    run_start = js.index("async function runTask")
    return_start = js.index('const result = await callApi("run_chat_message"', run_start)
    early_terminal_start = js.index("if (state.terminalTaskIds.has(result.task_id))", return_start)
    running_start = js.index("state.running = true", return_start)

    assert early_terminal_start < running_start
    assert "setTaskPanelOpen(true);" not in js[early_terminal_start:running_start]
    assert "setStopTaskVisible(true);" not in js[early_terminal_start:running_start]


def test_frontend_syncs_all_terminal_events_and_retries_after_api_return():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert "syncedTaskIds: new Set()" in js
    assert "syncingTaskIds: new Set()" in js
    assert "taskConversationIds: new Map()" in js
    assert "async function syncTerminalTask" in js
    helper_start = js.index("async function syncTerminalTask")
    progress_start = js.index("async function handleProgress")
    completed_start = js.index('if (event.type === "task_completed")', progress_start)
    error_start = js.index('if (event.type === "error")', completed_start)
    cancelled_start = js.index('if (event.type === "cancelled")', error_start)
    run_start = js.index("async function runTask")
    return_start = js.index('const result = await callApi("run_chat_message"', run_start)
    running_start = js.index("state.running = true", return_start)

    assert "const conversationId = state.taskConversationIds.get(taskId);" in js[helper_start:progress_start]
    assert 'await callApi("sync_chat_result", conversationId, taskId);' in js[helper_start:progress_start]
    assert "state.syncedTaskIds.add(taskId);" in js[helper_start:progress_start]
    assert "state.syncedTaskIds.add(taskId);" not in js[:js.index('await callApi("sync_chat_result", conversationId, taskId);', helper_start)]
    assert "await syncTerminalTask(state.taskId);" in js[completed_start:error_start]
    assert "await syncTerminalTask(state.taskId);" in js[error_start:cancelled_start]
    assert "await syncTerminalTask(state.taskId);" in js[cancelled_start:]
    assert "state.taskConversationIds.set(result.task_id, result.conversation_id);" in js[return_start:running_start]
    assert "await syncTerminalTask(state.taskId);" in js[return_start:running_start]


def test_frontend_marks_terminal_sync_only_after_a_non_running_success():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert "async function syncTerminalTask" in js
    helper_start = js.index("async function syncTerminalTask")
    helper_end = js.index("const MEMORY_KIND_GROUPS", helper_start)
    helper = js[helper_start:helper_end]

    assert 'const result = await callApi("sync_chat_result", conversationId, taskId);' in helper
    assert 'if (result.ok !== true || result.status === "running") {' in helper
    assert "shouldRetry = true;" in helper
    assert "return false;" in helper
    assert "state.syncedTaskIds.add(taskId);" in helper
    assert "await loadConversationSidebar();" in helper
    assert "return true;" in helper
    assert helper.index('if (result.ok !== true || result.status === "running") {') < helper.index("state.syncedTaskIds.add(taskId);")
    assert "return false;" in helper
    assert "finally" in helper
    assert "state.syncingTaskIds.delete(taskId);" in helper


def test_frontend_guards_late_run_results_after_conversation_switch():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert "conversationRevision: 0" in js
    assert "function advanceConversationRevision" in js
    start_new = js.index("async function startNewConversation")
    open_start = js.index("async function openConversation")
    run_start = js.index("async function runTask")
    return_start = js.index('const result = await callApi("run_chat_message"', run_start)
    task_mapping = js.index("state.taskConversationIds.set(result.task_id, result.conversation_id);", return_start)
    error_branch = js.index("if (!result.ok)", return_start)
    catch_start = js.index("} catch (error)", return_start)
    finally_start = js.index("} finally", catch_start)

    assert "advanceConversationRevision();" in js[start_new:open_start]
    assert "advanceConversationRevision();" in js[open_start:run_start]
    revision_start = js.index("function advanceConversationRevision")
    revision_end = start_new
    assert "state.messages = [];" in js[revision_start:revision_end]
    assert "state.pendingAssistantId = null;" in js[revision_start:revision_end]
    assert "setStatus(\"ready\", \"就绪\");" in js[revision_start:revision_end]
    assert "terminalSyncTimers" not in js[js.index("function advanceConversationRevision"):js.index("async function startNewConversation")]

    assert "const requestRevision = state.conversationRevision;" in js[return_start - 500:return_start]
    assert "const requestAssistant = assistant;" in js[return_start - 500:return_start]
    revision_guard = js.index("state.conversationRevision !== requestRevision", task_mapping)
    stale_direct_start = js.index("if (result.direct)", revision_guard)
    current_direct_start = js.index("if (result.direct)", stale_direct_start + 1)
    assert task_mapping < revision_guard
    assert revision_guard < stale_direct_start < current_direct_start
    assert "await loadConversationSidebar();" in js[revision_guard:current_direct_start]
    assert "await syncTerminalTask(result.task_id);" in js[task_mapping:revision_guard + 300]
    stale_error_end = js.index('setStatus("error", "未运行")', error_branch)
    assert "await loadConversationSidebar();" in js[error_branch:stale_error_end]
    assert "showToast" not in js[error_branch:stale_error_end]
    assert "els.taskInput.value = \"\";" in js[stale_direct_start:current_direct_start]
    assert js.index('els.taskInput.value = "";', revision_guard) < current_direct_start
    assert "state.conversationRevision !== requestRevision" in js[catch_start:finally_start]
    assert "state.conversationRevision === requestRevision" in js[finally_start:js.index("async function resumeTask", finally_start)]


def test_frontend_clears_shared_composer_only_when_activating_a_conversation():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    revision_start = js.index("function advanceConversationRevision")
    revision_end = js.index("function showToast", revision_start)
    revision = js[revision_start:revision_end]
    reset_start = js.index("function resetRunSurface")
    reset_end = js.index("async function runTask", reset_start)
    reset = js[reset_start:reset_end]
    run_start = js.index("async function runTask")
    task_mapping = js.index("state.taskConversationIds.set(result.task_id, result.conversation_id);", run_start)
    stale_guard = js.index("state.conversationRevision !== requestRevision", task_mapping)
    stale_return = js.index("return;", stale_guard)
    input_clear = js.index('els.taskInput.value = "";', stale_return)

    assert "els.taskInput.value = \"\";" in revision
    assert "resetRunSurface();" in revision
    assert "els.taskInput.readOnly = false;" in reset
    assert "els.runTask.disabled = false;" in reset
    assert "els.resumeTask.disabled = false;" in reset
    for name in [
        "terminalTaskIds",
        "syncedTaskIds",
        "syncingTaskIds",
        "taskConversationIds",
        "terminalSyncTimers",
        "terminalSyncAttempts",
    ]:
        assert name not in revision

    assert stale_return < input_clear
    assert 'els.taskInput.value = "";' not in js[stale_guard:stale_return]
    assert task_mapping < stale_guard
    assert "await syncTerminalTask(result.task_id);" in js[task_mapping:stale_return]


def test_frontend_retries_terminal_sync_with_bounded_deduplicated_backoff():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert "const TERMINAL_SYNC_RETRY_DELAYS = [80, 200, 500, 1000];" in js
    assert "terminalSyncTimers: new Map()" in js
    assert "terminalSyncAttempts: new Map()" in js
    assert "function scheduleTerminalSyncRetry" in js
    assert "function clearTerminalSyncRetry" in js
    helper_start = js.index("async function syncTerminalTask")
    helper_end = js.index("const MEMORY_KIND_GROUPS", helper_start)
    helper = js[helper_start:helper_end]
    scheduler_start = js.index("function scheduleTerminalSyncRetry")
    scheduler_end = helper_start
    scheduler = js[scheduler_start:scheduler_end]
    reset_start = js.index("function resetRunSurface")
    run_start = js.index("async function runTask", reset_start)
    direct_start = js.index("if (result.direct)", run_start)
    running_start = js.index("state.running = true", direct_start)

    assert "state.terminalSyncTimers.has(taskId) || state.syncingTaskIds.has(taskId)" in scheduler
    assert "const delay = TERMINAL_SYNC_RETRY_DELAYS[attempt];" in scheduler
    assert "setTimeout(async () =>" in scheduler
    assert "state.terminalSyncTimers.set(taskId, timer);" in scheduler
    assert "会话同步未完成" in scheduler
    assert "shouldRetry = true;" in helper
    assert "scheduleTerminalSyncRetry(taskId);" in helper
    assert "clearTerminalSyncRetry(taskId);" in helper
    assert helper.index("clearTerminalSyncRetry(taskId);") < helper.index("state.syncedTaskIds.add(taskId);")
    assert "clearTerminalSyncRetry" not in js[reset_start:run_start]
    assert "clearTerminalSyncRetry" not in js[direct_start:running_start]


def test_frontend_includes_memory_view():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    assert 'id="openMemory"' in html
    assert "记忆" in html
    assert 'id="memoryView"' in html
    assert 'id="memoryConversationShortTerm"' in html
    assert 'id="memoryLongTermGroups"' in html
    assert 'id="compressCurrentConversation"' in html
    assert 'class="panel memoryPanel longTermMemoryPanel"' in html
    assert "短期会话记忆" in html
    assert "长期记忆总览" in html
    assert "压缩当前会话" in html
    assert 'id="memoryTaskHistory"' in html
    assert 'id="memoryLessons"' in html
    assert 'id="memoryNegativeRules"' in html
    assert 'id="memorySkillCandidates"' in html


def test_frontend_calls_memory_bridge_method():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'callApi("get_memory_overview")' in js
    assert 'callApi("compress_conversation"' in js
    assert "function showCapabilityPage" in js
    assert "function renderMemoryOverview" in js
    assert "function renderConversationShortTermMemory" in js
    assert "function renderLongTermMemoryGroups" in js
    assert "function renderMemoryFact" in js
    assert "const MEMORY_KIND_GROUPS" in js
    assert "renderLongTermFacts" not in js
    assert "function compressCurrentConversation" in js


def test_frontend_groups_long_term_memory_instead_of_flat_list():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert "用户画像" in js
    assert "偏好" in js
    assert "工作习惯" in js
    assert "项目事实" in js
    assert "明确约束" in js
    assert "决策记录" in js
    assert "待确认问题" in js
    assert 'class="memoryGroup' in js
    assert 'class="memoryFact"' in js
    assert 'class="memoryDetails"' in js
    assert "<summary>来源详情</summary>" in js
    assert "#memoryLongTermGroups" in css
    assert ".memoryGroup" in css
    assert ".memoryDetails" in css


def test_frontend_long_term_memory_panel_has_room_to_render_groups():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert ".longTermMemoryPanel {\n  grid-column: 1 / -1;" in css
    assert ".longTermMemoryPanel {\n  grid-column: 1 / -1;\n  overflow: visible;" in css
    assert "#memoryLongTermGroups {\n  max-height: none;" in css
    assert "grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));" in css


def test_frontend_memory_view_has_bottom_scroll_clearance_for_long_overview():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert "#memoryView {\n  align-items: start;\n  align-content: start;\n  padding-bottom: 72px;\n  scroll-padding-bottom: 72px;" in css
    assert "#memoryLongTermGroups {\n  max-height: none;\n  overflow: visible;\n  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));" in css
    assert "row-gap: 14px;" in css


def test_frontend_memory_view_panels_expand_instead_of_clipping_cards():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert "#memoryView {\n  align-items: start;\n  align-content: start;" in css
    assert "#memoryView .memoryPanel {\n  grid-template-rows: auto auto;\n  overflow: visible;" in css
    assert "#memoryView .memoryBlock {\n  max-height: none;\n  overflow: visible;" in css


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


def test_frontend_includes_manual_authorization_modal():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'id="dangerousToolsStatus"' in html
    assert "工具授权" in html
    assert 'id="dangerousToolsEnabled"' in html
    assert 'id="authorizationModal"' in html
    assert 'id="approveAuthorization"' in html
    assert 'id="rejectAuthorization"' in html
    assert "function updateDangerousToolsStatus" in js
    assert "result.open_settings" in js
    assert 'event.type === "authorization_required"' in js
    assert 'callApi("authorize_operation", requestId)' in js
    assert 'callApi("reject_authorization", requestId' in js
    assert "payload.code" in js
    assert "payload.trash_path" in js


def test_frontend_uses_a_single_sidebar_dangerous_tools_status_entry():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    assert html.count('id="dangerousToolsStatus"') == 1
    assert html.index('id="dangerousToolsStatus"') < html.index('<main class="main">')


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
    assert "本轮任务" in html


def test_frontend_chat_styles_exist():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert ".chatWorkspace" in css
    assert ".chatMessages" in css
    assert ".chatMessage.user" in css
    assert ".chatMessage.assistant" in css
    assert ".chatComposer" in css
    assert ".detailColumn" in css


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


def test_frontend_keeps_execution_progress_out_of_assistant_messages():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert "function renderMessageProgress" not in js
    assert "function renderPlan" in js
    assert "function markStep" in js
    assert "els.taskActivity.textContent = line" in js


def test_frontend_handles_direct_chat_replies():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert "result.direct" in js
    assert "requestAssistant" in js
    assert "content: result.message || \"已回复。\"" in js


def test_frontend_refreshes_sidebar_after_chat_conversation_writes():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
    direct_start = js.index("if (result.direct)")
    direct_end = js.index("state.running = true", direct_start)
    progress_start = js.index("async function handleProgress")
    completed_start = js.index('if (event.type === "task_completed")', progress_start)
    completed_end = js.index('if (event.type === "error")', completed_start)

    assert "await loadConversationSidebar();" in js[direct_start:direct_end]
    assert "await syncTerminalTask(state.taskId);" in js[completed_start:completed_end]


def test_frontend_task_completed_updates_assistant_message_not_report_panel_only():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'event.type === "task_completed"' in js
    assert "updateAssistantMessage" in js
    assert "renderMarkdown(state.reportText)" in js


def test_frontend_uses_dark_command_deck_theme_without_remote_fonts():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert "fonts.googleapis.com" not in html
    assert "fonts.gstatic.com" not in html
    assert "--surface-0: #0e0e18;" in css
    assert "--surface-1: #14141f;" in css
    assert "--surface-2: #1a1a28;" in css
    assert "--accent-glow: rgba(116, 123, 255, 0.12);" in css
    assert "background: var(--bg);" in css
    assert "--sans: -apple-system, BlinkMacSystemFont" in css


def test_frontend_sidebar_nav_has_icons_without_breaking_ids():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    for nav_id in [
        "newConversation",
        "openMemory",
        "openKnowledge",
        "openSkills",
        "openSettingsSide",
    ]:
        assert f'id="{nav_id}"' in html
    assert html.count('class="navIcon"') >= 4
    assert ".nav.active::before" in css


def test_frontend_preserves_current_memory_nodes_during_redesign():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    assert 'id="memoryLongTermGroups"' in html
    assert 'id="memoryConversationShortTerm"' in html
    assert 'id="compressCurrentConversation"' in html
    assert "长期记忆总览" in html
    assert "短期会话记忆" in html
    assert "压缩当前会话" in html


def test_frontend_dark_memory_cards_do_not_clip_titles():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert ".memoryCard {" in css
    assert "overflow-wrap: anywhere;" in css
    assert "#memoryView .memoryPanel {\n  grid-template-rows: auto auto;\n  overflow: visible;" in css
    assert "#memoryView .memoryBlock {\n  max-height: none;\n  overflow: visible;" in css
    assert ".memoryGroupHead" in css
    assert "min-width: 0;" in css


def test_frontend_sidebar_keeps_conversations_and_capability_entries():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    for element_id in ["newConversation", "conversationList", "openKnowledge", "openMemory", "openSkills", "openSettingsSide"]:
        assert f'id="{element_id}"' in html
    assert "知识库" in html
    assert "记忆中心" in html
    assert "技能与工具" in html


def test_frontend_can_load_conversations_into_sidebar():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'callApi("list_conversations")' in js
    assert 'callApi("get_conversation", conversationId)' in js
    assert "function loadConversationSidebar" in js
    assert "function renderConversationSidebar" in js
    assert "function openConversation" in js

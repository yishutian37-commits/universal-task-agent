from pathlib import Path
import re


FRONTEND_ROOT = Path("desktop/frontend")


def css_rule(css: str, selector: str) -> str:
    match = re.search(rf"{re.escape(selector)}\s*\{{([^}}]*)\}}", css)
    assert match is not None, f"missing CSS rule: {selector}"
    return match.group(1)


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


def test_frontend_task_evidence_tabs_render_live_and_recovered_records():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert 'id="taskFilesList"' in html
    assert 'id="taskChangesList"' in html
    assert 'id="taskArtifactsList"' in html
    assert "function renderTaskEvidence" in js
    assert "window.UTAShell.mergeTaskEvidence" in js
    assert 'event.type === "file_recorded"' in js
    assert 'event.type === "file_changed"' in js
    assert 'event.type === "artifact_created"' in js
    assert "result.state && result.state.evidence" in js
    assert 'data-copy-evidence-path=' in js
    assert ".taskEvidenceList" in css
    assert ".taskEvidenceItem" in css


def test_frontend_task_panel_has_minimum_functional_layout():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert ".conversationSurface {\n  min-width: 0;\n  min-height: 0;\n  height: 100%;\n  display: grid;\n  grid-template-rows: auto minmax(0, 1fr) auto;\n  background: var(--panel-bg);\n  overflow: hidden;\n}" in css
    assert ".chatWorkspace.task-panel-open {\n  grid-template-columns: minmax(0, 1fr) 340px;\n}" in css
    assert ".taskPanel {\n  min-width: 0;\n  min-height: 0;\n  display: grid;\n  grid-template-rows: auto auto minmax(0, 1fr);\n  border-left: 1px solid var(--border);\n  background: var(--panel-subtle);\n  overflow: hidden;\n}" in css
    assert ".taskPanel.collapsed {\n  display: none;\n}" in css
    assert ".chatMessages {\n  min-height: 0;\n  overflow-y: auto;" in css
    assert ".chatComposer {\n  width: min(820px, calc(100% - 48px));\n  margin: 0 auto 20px;\n  border: 1px solid var(--border-strong);\n  border-radius: var(--radius-lg);\n  background: var(--panel-bg);\n}" in css


def test_frontend_task_tabs_have_stable_aria_relationships():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    for name in ["progress", "files", "changes", "artifacts", "diagnostics"]:
        selected = "true" if name == "progress" else "false"
        hidden = "false" if name == "progress" else "true"
        tab = html.split(f'id="taskTab-{name}"', 1)[1].split(">", 1)[0]
        assert 'role="tab"' in tab
        assert f'aria-selected="{selected}"' in tab
        assert f'aria-controls="taskPanel-{name}"' in tab
        assert f'id="taskPanel-{name}" role="tabpanel" aria-labelledby="taskTab-{name}" aria-hidden="{hidden}"' in html


def test_frontend_task_panel_and_stop_control_follow_run_lifecycle():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
    reset_start = js.index("function resetRunSurface")
    run_start = js.index("async function runTask", reset_start)
    progress_start = js.index("async function handleProgress")
    completed_start = js.index('if (event.type === "task_completed")', progress_start)
    error_start = js.index('if (event.type === "error")', completed_start)
    cancelled_start = js.index('if (event.type === "cancelled")', error_start)
    stop_start = js.index("async function stopTask")
    stop_end = js.index("function stepMarkerFor", stop_start)
    stop = js[stop_start:stop_end]

    assert "setTaskPanelOpen(false);" in js[reset_start:run_start]
    assert "setStopTaskVisible(false);" in js[reset_start:run_start]
    assert "setStopTaskVisible(false);" in js[completed_start:error_start]
    assert "setStopTaskVisible(false);" in js[error_start:]
    assert "setStopTaskVisible(false);" in js[cancelled_start:]
    assert "function setStopTaskVisible" in js
    assert "async function stopTask" in js
    assert "const taskId = state.taskId;" in stop
    assert "if (!taskId || !runLifecycle.beginCancel(taskId)) return;" in stop
    assert 'callApi("cancel_task", taskId)' in stop
    assert "runLifecycle.confirmCancel(taskId);" in stop
    assert "runLifecycle.failCancel(taskId)" in stop
    assert stop.index('setStatus("running", "正在停止");') < stop.index('await callApi("cancel_task", taskId)')
    assert 'els.stopTask.addEventListener("click", stopTask);' in js


def test_frontend_binds_and_replays_events_that_arrive_before_api_return():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
    run_start = js.index("async function runTask")
    request_start = js.index("runLifecycle.beginRequest", run_start)
    return_start = js.index('const result = await callApi("run_chat_message"', run_start)
    binding_start = js.index("runLifecycle.bindTask", return_start)
    replay_start = js.index("for (const earlyEvent of binding.events)", binding_start)

    assert request_start < return_start < binding_start < replay_start
    assert "await handleProgress(earlyEvent);" in js[replay_start:js.index("} catch", replay_start)]
    assert "terminalTaskIds" not in js


def test_frontend_routes_events_before_any_visible_task_update():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
    progress_start = js.index("async function handleProgress")
    progress_end = js.index("async function refreshResult", progress_start)
    progress = js[progress_start:progress_end]

    assert "const route = runLifecycle.routeEvent(event);" in progress
    assert 'route.disposition === "buffered" || route.disposition === "ignored"' in progress
    assert "const taskId = route.taskId;" in progress
    assert "const context = route.context;" in progress
    assert 'route.disposition === "visible"' in progress
    assert "isRunContextVisible(context)" in progress
    assert progress.index("const route = runLifecycle.routeEvent(event);") < progress.index("addLog(sourceFor(event), messageFor(event));")
    assert "state.taskId = event.task_id" not in progress


def test_frontend_syncs_and_refreshes_terminal_events_by_routed_task_id():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
    helper_start = js.index("async function syncTerminalTask")
    progress_start = js.index("async function handleProgress")
    completed_start = js.index('if (event.type === "task_completed")', progress_start)
    error_start = js.index('if (event.type === "error")', completed_start)
    cancelled_start = js.index('if (event.type === "cancelled")', error_start)
    refresh_start = js.index("async function refreshResult", cancelled_start)

    assert "const context = runLifecycle.getTaskContext(taskId);" in js[helper_start:progress_start]
    assert "const conversationId = context && context.conversationId;" in js[helper_start:progress_start]
    assert 'await callApi("sync_chat_result", conversationId, taskId);' in js[helper_start:progress_start]
    assert "terminalSync.syncedTaskIds.add(taskId);" in js[helper_start:progress_start]
    for branch in [js[completed_start:error_start], js[error_start:cancelled_start], js[cancelled_start:refresh_start]]:
        assert "await syncTerminalTask(taskId);" in branch
        assert "await refreshResult(taskId);" in branch
    assert "async function refreshResult(taskId)" in js[refresh_start:]
    assert 'callApi("get_result", taskId)' in js[refresh_start:]
    assert "syncTerminalTask(state.taskId)" not in js
    assert "refreshResult()" not in js


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
    assert "terminalSync.syncedTaskIds.add(taskId);" in helper
    assert "await loadConversationSidebar();" in helper
    assert "return true;" in helper
    assert helper.index('if (result.ok !== true || result.status === "running") {') < helper.index("terminalSync.syncedTaskIds.add(taskId);")
    assert "return false;" in helper
    assert "finally" in helper
    assert "terminalSync.syncingTaskIds.delete(taskId);" in helper


def test_frontend_guards_late_run_results_after_conversation_switch():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert "conversationRevision: 0" in js
    assert "function advanceConversationRevision" in js
    start_new = js.index("async function startNewConversation")
    open_start = js.index("async function openConversation")
    run_start = js.index("async function runTask")
    return_start = js.index('const result = await callApi("run_chat_message"', run_start)
    task_mapping = js.index("runLifecycle.bindTask", return_start)
    catch_start = js.index("} catch (error)", return_start)
    finally_start = js.index("} finally", catch_start)

    assert "advanceConversationRevision();" in js[start_new:open_start]
    assert "advanceConversationRevision();" in js[open_start:run_start]
    assert "if (runLifecycle.isBusy())" in js[start_new:open_start]
    assert "if (runLifecycle.isBusy())" in js[open_start:run_start]
    revision_start = js.index("function advanceConversationRevision")
    revision_end = start_new
    assert "state.messages = [];" in js[revision_start:revision_end]
    assert "setStatus(\"ready\", \"就绪\");" in js[revision_start:revision_end]

    assert "const requestRevision = state.conversationRevision;" in js[run_start:return_start]
    assert "const requestContext = runLifecycle.beginRequest" in js[run_start:return_start]
    revision_guard = js.index("if (state.conversationRevision !== requestRevision)", task_mapping)
    replay_start = js.index("for (const earlyEvent of binding.events)", task_mapping)
    assert task_mapping < replay_start < revision_guard
    assert "await loadConversationSidebar();" in js[revision_guard:catch_start]
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

    assert "els.taskInput.value = \"\";" in revision
    assert "resetRunSurface();" in revision
    assert "els.taskInput.readOnly = false;" in reset
    assert "els.runTask.disabled = false;" in reset
    assert "els.resumeTask.disabled = false;" in reset
    assert "runLifecycle" not in revision


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

    assert "terminalSync.terminalSyncTimers.has(taskId) || terminalSync.syncingTaskIds.has(taskId)" in scheduler
    assert "const delay = TERMINAL_SYNC_RETRY_DELAYS[attempt];" in scheduler
    assert "setTimeout(async () =>" in scheduler
    assert "terminalSync.terminalSyncTimers.set(taskId, timer);" in scheduler
    assert "会话同步未完成" in scheduler
    assert "shouldRetry = true;" in helper
    assert "scheduleTerminalSyncRetry(taskId);" in helper
    assert "clearTerminalSyncRetry(taskId);" in helper
    assert helper.index("clearTerminalSyncRetry(taskId);") < helper.index("terminalSync.syncedTaskIds.add(taskId);")
    assert "clearTerminalSyncRetry" not in js[reset_start:run_start]


def test_frontend_includes_memory_view():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    assert 'id="openMemory"' in html
    assert "记忆" in html
    assert 'class="workspace memoryCenterWorkspace hidden" id="memoryView"' in html
    for name in ["long-term", "session", "learning", "archive"]:
        assert f'id="memoryTab-{name}"' in html
        assert f'role="tab"' in html
        assert f'aria-controls="memoryPanel-{name}"' in html
        assert f'data-memory-tab="{name}"' in html
        assert f'id="memoryPanel-{name}"' in html
        assert f'role="tabpanel"' in html
        assert f'aria-labelledby="memoryTab-{name}"' in html
        assert f'data-memory-panel="{name}"' in html
    assert 'id="memoryConversationShortTerm"' in html
    assert 'id="memoryLongTermKinds"' in html
    assert 'id="memoryLongTermFacts"' in html
    assert 'id="compressCurrentConversation"' in html
    assert 'id="refreshMemory"' in html
    assert "当前会话" in html
    assert "长期记忆" in html
    assert "压缩当前会话" in html
    assert 'id="memoryLessons"' in html
    assert 'id="memoryNegativeRules"' in html
    assert 'id="memorySkillCandidates"' in html
    assert 'id="memoryArchiveList"' in html
    assert 'id="memoryArchiveDetail"' in html


def test_frontend_calls_memory_bridge_method():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'callApi("get_memory_overview")' in js
    assert 'callApi("compress_conversation"' in js
    assert "function showCapabilityPage" in js
    assert "function renderMemoryOverview" in js
    assert "function renderConversationShortTermMemory" in js
    assert "function renderMemoryLongTerm" in js
    assert "function renderMemoryLearning" in js
    assert "function renderMemoryArchive" in js
    assert "function renderMemoryFact" in js
    assert "function setMemoryTab" in js
    assert "const MEMORY_KIND_GROUPS" in js
    assert "function compressCurrentConversation" in js
    assert "createMemoryOperationLifecycle" in js
    assert "memoryOperations.beginLoad" in js
    assert "memoryOperations.isLoadCurrent" in js
    assert "memoryOperations.beginCompression" in js
    assert "memoryOperations.finishCompression" in js


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
    assert "window.UTAShell.groupMemoryFacts(facts)" in js
    assert 'data-memory-kind=' in js
    assert 'class="memoryFact"' in js
    assert 'class="memoryDetails"' in js
    assert "<summary>来源详情</summary>" in js
    assert ".memoryLongTermLayout" in css
    assert ".memoryKindList" in css
    assert ".memoryDetails" in css


def test_frontend_long_term_memory_panel_has_room_to_render_groups():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert ".memoryLongTermLayout,\n.memoryArchiveLayout {\n  min-height: 0;\n  display: grid;\n  grid-template-columns: 260px minmax(0, 1fr);" in css
    assert ".memoryLearningLayout {\n  min-height: 0;\n  display: grid;\n  grid-template-columns: repeat(3, minmax(0, 1fr));" in css
    assert ".memoryKindList,\n.memoryLongTermFacts" in css
    assert "min-height: 0;\n  overflow: auto;" in css


def test_frontend_memory_view_has_bottom_scroll_clearance_for_long_overview():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert ".memoryCenterWorkspace {\n  grid-template-columns: minmax(0, 1fr);\n  grid-template-rows: auto auto minmax(0, 1fr);\n  overflow: hidden;" in css
    assert "#memoryView .memoryBlock {\n  max-height: none;\n  overflow: visible;" not in css
    assert "@media (max-width: 1179px)" in css
    assert "@media (max-width: 960px)" in css
    assert "max-height: min(32vh, 240px);" in css


def test_frontend_memory_view_panels_expand_instead_of_clipping_cards():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert ".memoryTabPanel {\n  min-height: 0;\n  overflow: hidden;" in css
    assert ".memoryPanel {\n  min-height: 0;\n  display: grid;\n  grid-template-rows: auto minmax(0, 1fr);\n  overflow: hidden;" in css
    assert ".memoryBlock {\n  min-height: 0;\n  overflow: auto;" in css


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
    assert 'id="desktopAccessEnabled"' in html
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
    assert "settings.desktop_access_enabled" in js
    assert "desktop_access_enabled: els.desktopAccessEnabled.checked" in js


def test_modals_keep_scrollable_bodies_between_stable_headers_and_footers():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    settings = html.split('id="settingsModal"', 1)[1].split('</form>', 1)[0]
    authorization = html.split('id="authorizationModal"', 1)[1].split('</section>', 1)[0]
    assert 'class="modalBody settingsBody"' in settings
    assert settings.index("<header>") < settings.index('class="modalBody settingsBody"') < settings.index("<footer>")
    assert 'class="authorizationBody"' in authorization
    assert authorization.index("<header>") < authorization.index('class="authorizationBody"') < authorization.index("<footer>")


def test_modal_backdrop_and_scroll_contract_stays_above_the_narrow_task_drawer():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")
    backdrop = css_rule(css, ".modalBackdrop")
    modal = css_rule(css, ".modal")
    settings_body = css_rule(css, ".settingsBody")
    authorization_body = css_rule(css, ".authorizationBody")
    drawer_media = css.split("@media (max-width: 1179px)", 1)[1].split("@media (max-width: 760px)", 1)[0]
    drawer = css_rule(drawer_media, ".taskPanel")

    assert "inset: 0;" in backdrop
    assert "z-index: 100;" in backdrop
    assert int(re.search(r"z-index:\s*(\d+)", backdrop).group(1)) > int(re.search(r"z-index:\s*(\d+)", drawer).group(1))
    assert "max-height: calc(100dvh - 48px);" in modal
    assert "display: grid;" in modal
    assert "grid-template-rows: auto minmax(0, 1fr) auto;" in modal
    assert "overflow: hidden;" in modal
    for body in [settings_body, authorization_body]:
        assert "min-height: 0;" in body
        assert "overflow-y: auto;" in body


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
    assert ".taskPanel" in css


def test_frontend_hidden_report_cannot_create_extra_chat_row():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert 'class="report empty hidden" id="report"' in html
    assert ".hidden {\n  display: none !important;" in css


def test_frontend_narrow_layout_keeps_chat_surface_and_drawer_viewport_bound():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert "@media (max-width: 1179px)" in css
    assert ".taskPanel {\n    position: absolute;" in css
    assert "bottom: 0;" in css
    assert "@media (max-width: 760px)" in css
    assert ".app {\n    grid-template-columns: 72px minmax(0, 1fr);\n  }" in css


def test_frontend_chat_messages_stay_near_composer_while_running():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert ".chatMessages {\n  min-height: 0;\n  overflow-y: auto;\n  padding: 24px max(24px, calc((100% - 820px) / 2));\n  display: flex;" in css
    assert "  flex-direction: column;" in css
    assert ".chatMessages > .chatMessage:first-child" not in css


def test_frontend_failed_messages_keep_a_visible_danger_border():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert ".chatMessage.failed .messageBubble {\n  border-left: 3px solid var(--danger);\n  background: var(--danger-dim);\n}" in css


def test_frontend_status_indicators_do_not_use_decorative_glow():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    for selector in [".status.running i", ".status.done i", ".status.error i"]:
        rule = css.split(selector, 1)[1].split("}", 1)[0]
        assert "box-shadow" not in rule


def test_frontend_calls_chat_bridge_methods_and_updates_messages():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'callApi("run_chat_message"' in js
    assert 'callApi("sync_chat_result"' in js
    assert "function addChatMessage" in js
    assert "function updateAssistantForContext" in js
    assert "function renderChatMessages" in js
    assert "const runLifecycle = window.UTAShell.createRunLifecycle();" in js


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
    direct_end = js.index("const binding = runLifecycle.bindTask", direct_start)
    progress_start = js.index("async function handleProgress")
    completed_start = js.index('if (event.type === "task_completed")', progress_start)
    completed_end = js.index('if (event.type === "error")', completed_start)

    assert "await loadConversationSidebar();" in js[direct_start:direct_end]
    assert "await syncTerminalTask(taskId);" in js[completed_start:completed_end]


def test_frontend_task_completed_updates_assistant_message_not_report_panel_only():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'event.type === "task_completed"' in js
    assert "updateAssistantForContext" in js
    assert "renderMarkdown(state.reportText)" in js


def test_frontend_uses_neutral_workbench_theme_without_remote_fonts():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert "fonts.googleapis.com" not in html
    assert "fonts.gstatic.com" not in html
    assert "--app-bg: #f5f5f3;" in css
    assert "--sidebar-bg: #ecece8;" in css
    assert "--panel-bg: #ffffff;" in css
    assert "--action: #2f64d6;" in css
    assert "linear-gradient" not in css


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
    assert ".nav.active" in css


def test_frontend_preserves_current_memory_nodes_during_redesign():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    assert 'id="memoryLongTermKinds"' in html
    assert 'id="memoryLongTermFacts"' in html
    assert 'id="memoryConversationShortTerm"' in html
    assert 'id="compressCurrentConversation"' in html
    assert "长期记忆" in html
    assert "当前会话" in html
    assert "压缩当前会话" in html


def test_frontend_dark_memory_cards_do_not_clip_titles():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert ".memoryCard {" in css
    assert "overflow-wrap: anywhere;" in css
    assert ".memoryPanel {\n  min-height: 0;" in css
    assert ".memoryBlock {\n  min-height: 0;\n  overflow: auto;" in css
    assert ".memoryKindButton" in css
    assert "min-width: 0;" in css


def test_frontend_memory_rendering_reuses_shell_helpers_and_keeps_controls_in_sync():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    for helper in [
        "activateMemoryTab",
        "handleMemoryTabKeydown",
        "groupMemoryFacts",
        "compactMemoryText",
        "dedupeMemoryLessons",
        "memoryTaskTypeLabel",
        "memoryTaskStatusLabel",
        "memorySkillStatusLabel",
        "localizeMemoryTaskText",
    ]:
        assert f"window.UTAShell.{helper}" in js
    assert "state.memoryOverview = memory;" in js
    assert "state.memoryTab" in js
    assert "state.memoryLongTermKind" in js
    assert "state.memoryArchiveTaskId" in js
    assert "memoryOperations.isCompressionActive()" in js
    assert "累计 ${escapeHtml(lesson.occurrence_count || 1)} 次" in js
    assert "els.memoryArchiveDetail.innerHTML = renderMarkdown" in js
    assert "window.UTAShell.compactMemoryText" in js


def test_frontend_sidebar_keeps_conversations_and_capability_entries():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    for element_id in ["newConversation", "conversationList", "openKnowledge", "openMemory", "openSkills", "openSettingsSide"]:
        assert f'id="{element_id}"' in html
    assert "知识库" in html
    assert "记忆中心" in html
    assert "技能与工具" in html


def test_frontend_sidebar_actions_keep_names_when_labels_are_hidden():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    for element_id, label in [
        ("newConversation", "新任务"),
        ("openKnowledge", "知识库"),
        ("openMemory", "记忆中心"),
        ("openSkills", "技能与工具"),
        ("openSettingsSide", "设置与授权"),
    ]:
        button = html.split(f'id="{element_id}"', 1)[1].split("</button>", 1)[0]
        assert f'aria-label="{label}"' in button
        assert f'title="{label}"' in button


def test_frontend_can_load_conversations_into_sidebar():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'callApi("list_conversations")' in js
    assert 'callApi("get_conversation", conversationId)' in js
    assert "function loadConversationSidebar" in js
    assert "function renderConversationSidebar" in js
    assert "function openConversation" in js


def test_frontend_requires_workspace_for_tasks_and_can_open_native_folder_picker():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    selector = html.split('id="workspaceSelector"', 1)[1].split("</button>", 1)[0]
    assert "disabled" not in selector
    assert "选择工作文件夹" in selector
    assert "workspacePath" in js
    assert "async function selectWorkspace" in js
    assert 'callApi("select_workspace")' in js
    assert 'callApi("get_message_requirements", text)' in js
    assert 'els.workspaceSelector.addEventListener("click", selectWorkspace);' in js
    assert 'showToast("任务运行中", "请先停止当前任务再切换工作区");' in js
    assert "text-overflow: ellipsis" in css_rule(css, ".workspaceSelector")


def test_frontend_messages_are_selectable_and_have_copy_action():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert 'class="messageCopy"' in js
    assert 'data-copy-message-id=' in js
    assert 'data-copy-selectable="true"' in js
    assert "async function copyMessage" in js
    assert "navigator.clipboard.writeText" in js
    assert "user-select: text;" in css_rule(css, ".messageBubble,\n.messageBubble *")
    assert 'id="selectionContextMenu"' in html
    assert 'id="copySelection"' in html
    assert "function selectedMessageText" in js
    assert 'document.addEventListener("contextmenu"' in js
    assert "window.getSelection()" in js
    assert 'target.closest(\'[data-copy-selectable="true"]\')' in js
    assert 'els.copySelection.addEventListener("click"' in js


def test_frontend_can_delete_history_conversation_and_reset_current_view():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert 'class="conversationDelete"' in js
    assert 'aria-label="删除会话"' in js
    assert "async function deleteConversation" in js
    assert 'callApi("delete_conversation", conversationId)' in js
    assert "window.confirm" in js
    assert "state.conversationId = null;" in js
    assert ".conversationDelete" in css


def test_knowledge_workspace_uses_dedicated_layout_without_history_card_leakage():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert 'class="workspace knowledgeWorkspace hidden"' in html
    assert 'class="knowledgeDocList" id="kbDocList"' in html
    assert 'class="panel knowledgeQueryPanel"' in html
    assert 'class="report empty knowledgeAnswer"' in html
    assert 'class="logs knowledgeSources"' in html
    assert 'class="knowledgeDocItem"' in js
    assert 'class="historyItem" data-doc-id' not in js
    assert 'class="knowledgeDocPath" title=' in js
    assert ".knowledgeDocPath" in css
    assert "text-overflow: ellipsis" in css
    assert ".knowledgeAnswer" in css


def test_knowledge_ingest_uses_native_file_and_folder_pickers():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'id="kbIngestPath"' not in html
    assert 'id="kbIngestFilesBtn"' in html
    assert 'id="kbIngestFolderBtn"' in html
    assert "支持 Markdown 和纯文本，可多选" in html
    assert 'callApi("select_knowledge_files")' in js
    assert 'callApi("select_knowledge_folder")' in js
    assert "async function ingestKnowledgePaths" in js
    assert 'callApi("rag_ingest", path)' in js


def test_knowledge_document_titles_can_shrink_inside_their_dedicated_items():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    title_rule = css[css.index(".knowledgeDocMain strong"):css.index("}", css.index(".knowledgeDocMain strong"))]
    assert "overflow-wrap: anywhere;" in title_rule

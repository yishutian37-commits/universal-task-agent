const els = {
  bridgeState: document.getElementById("bridgeState"),
  keyState: document.getElementById("keyState"),
  chatMessages: document.getElementById("chatMessages"),
  chatDetailPanel: document.getElementById("chatDetailPanel"),
  newConversation: document.getElementById("newConversation"),
  conversationSearch: document.getElementById("conversationSearch"),
  conversationList: document.getElementById("conversationList"),
  conversationTitle: document.getElementById("conversationTitle"),
  openMemory: document.getElementById("openMemory"),
  openKnowledge: document.getElementById("openKnowledge"),
  openSkills: document.getElementById("openSkills"),
  taskView: document.getElementById("taskView"),
  memoryView: document.getElementById("memoryView"),
  knowledgeView: document.getElementById("knowledgeView"),
  skillsView: document.getElementById("skillsView"),
  refreshMemory: document.getElementById("refreshMemory"),
  refreshSkills: document.getElementById("refreshSkills"),
  memoryConversationShortTerm: document.getElementById("memoryConversationShortTerm"),
  memoryLongTermKinds: document.getElementById("memoryLongTermKinds"),
  memoryLongTermFacts: document.getElementById("memoryLongTermFacts"),
  compressCurrentConversation: document.getElementById("compressCurrentConversation"),
  memoryLessons: document.getElementById("memoryLessons"),
  memoryNegativeRules: document.getElementById("memoryNegativeRules"),
  memorySkillCandidates: document.getElementById("memorySkillCandidates"),
  memoryArchiveList: document.getElementById("memoryArchiveList"),
  memoryArchiveDetail: document.getElementById("memoryArchiveDetail"),
  statusPill: document.getElementById("statusPill"),
  statusText: document.getElementById("statusText"),
  taskIdLabel: document.getElementById("taskIdLabel"),
  taskInput: document.getElementById("taskInput"),
  runTask: document.getElementById("runTask"),
  resumeTask: document.getElementById("resumeTask"),
  stopTask: document.getElementById("stopTask"),
  toggleTaskPanel: document.getElementById("toggleTaskPanel"),
  closeTaskPanel: document.getElementById("closeTaskPanel"),
  loadExample: document.getElementById("loadExample"),
  clearTask: document.getElementById("clearTask"),
  clearLogs: document.getElementById("clearLogs"),
  planMeta: document.getElementById("planMeta"),
  planList: document.getElementById("planList"),
  taskActivity: document.getElementById("taskActivity"),
  logPanel: document.getElementById("logPanel"),
  report: document.getElementById("report"),
  copyReport: document.getElementById("copyReport"),
  stateJson: document.getElementById("stateJson"),
  settingsModal: document.getElementById("settingsModal"),
  settingsForm: document.getElementById("settingsForm"),
  openSettingsSide: document.getElementById("openSettingsSide"),
  closeSettings: document.getElementById("closeSettings"),
  dangerousToolsStatus: document.getElementById("dangerousToolsStatus"),
  baseUrl: document.getElementById("baseUrl"),
  modelName: document.getElementById("modelName"),
  apiKey: document.getElementById("apiKey"),
  sslVerify: document.getElementById("sslVerify"),
  dangerousToolsEnabled: document.getElementById("dangerousToolsEnabled"),
  clearKey: document.getElementById("clearKey"),
  authorizationModal: document.getElementById("authorizationModal"),
  authorizationSummary: document.getElementById("authorizationSummary"),
  authorizationDetails: document.getElementById("authorizationDetails"),
  approveAuthorization: document.getElementById("approveAuthorization"),
  rejectAuthorization: document.getElementById("rejectAuthorization"),
  toast: document.getElementById("toast"),
  toastTitle: document.getElementById("toastTitle"),
  toastBody: document.getElementById("toastBody"),
  kbMode: document.getElementById("kbMode"),
  kbIngestPath: document.getElementById("kbIngestPath"),
  kbIngestBtn: document.getElementById("kbIngestBtn"),
  kbRefreshBtn: document.getElementById("kbRefreshBtn"),
  kbDocList: document.getElementById("kbDocList"),
  kbStats: document.getElementById("kbStats"),
  kbQuestion: document.getElementById("kbQuestion"),
  kbAskBtn: document.getElementById("kbAskBtn"),
  kbQueryBtn: document.getElementById("kbQueryBtn"),
  kbAskMeta: document.getElementById("kbAskMeta"),
  kbAnswer: document.getElementById("kbAnswer"),
  kbSources: document.getElementById("kbSources"),
  runtimeSkillList: document.getElementById("runtimeSkillList"),
  vendorSkillPackList: document.getElementById("vendorSkillPackList"),
  skillPackMeta: document.getElementById("skillPackMeta"),
  skillErrorList: document.getElementById("skillErrorList")
};

const state = {
  activeExample: "summarize",
  taskId: null,
  conversationId: null,
  messages: [],
  pendingAuthorization: null,
  reportText: "",
  conversations: [],
  activePage: "conversation",
  taskPanelOpen: false,
  taskPanelTab: "progress",
  conversationRevision: 0,
  memoryOverview: null,
  memoryTab: "long-term",
  memoryLongTermKind: "identity",
  memoryArchiveTaskId: null
};

const runLifecycle = window.UTAShell.createRunLifecycle();
const memoryOperations = window.UTAShell.createMemoryOperationLifecycle();
const terminalSync = {
  syncedTaskIds: new Set(),
  syncingTaskIds: new Set(),
  terminalSyncTimers: new Map(),
  terminalSyncAttempts: new Map()
};

const TERMINAL_SYNC_RETRY_DELAYS = [80, 200, 500, 1000];

function setTaskPanelOpen(isOpen) {
  state.taskPanelOpen = window.UTAShell.setTaskPanelOpen(isOpen);
}

function setTaskPanelTab(tabName) {
  state.taskPanelTab = window.UTAShell.activateTaskTab(tabName);
}

function setMemoryTab(tabName) {
  state.memoryTab = window.UTAShell.activateMemoryTab(tabName);
}

function renderTaskPanelEmptyStates() {
  els.chatDetailPanel.classList.toggle("has-task", Boolean(state.taskId));
}

function setStopTaskVisible(isVisible) {
  els.stopTask.classList.toggle("hidden", !isVisible);
  els.stopTask.disabled = !isVisible;
}

function isRunContextVisible(context) {
  if (!context || !runLifecycle.isCurrentTask(context.taskId)) return false;
  if (state.conversationRevision !== context.conversationRevision) return false;
  return !context.conversationId || state.conversationId === context.conversationId;
}

function unlockComposerIfIdle() {
  if (runLifecycle.isBusy()) return;
  els.taskInput.readOnly = false;
  els.runTask.disabled = false;
  els.resumeTask.disabled = false;
}

function addTaskDiagnostic(taskId, source, message) {
  const context = runLifecycle.getTaskContext(taskId);
  if (context && isRunContextVisible(context)) addLog(source, message);
}

function clearTerminalSyncRetry(taskId) {
  if (terminalSync.terminalSyncTimers.has(taskId)) {
    clearTimeout(terminalSync.terminalSyncTimers.get(taskId));
    terminalSync.terminalSyncTimers.delete(taskId);
  }
  terminalSync.terminalSyncAttempts.delete(taskId);
}

function scheduleTerminalSyncRetry(taskId) {
  if (!taskId || terminalSync.syncedTaskIds.has(taskId)) return;
  if (terminalSync.terminalSyncTimers.has(taskId) || terminalSync.syncingTaskIds.has(taskId)) return;

  const attempt = terminalSync.terminalSyncAttempts.get(taskId) || 0;
  if (attempt >= TERMINAL_SYNC_RETRY_DELAYS.length) {
    addTaskDiagnostic(taskId, "Sync", `任务 ${taskId} 的会话同步未完成，请稍后刷新会话。`);
    return;
  }

  const delay = TERMINAL_SYNC_RETRY_DELAYS[attempt];
  terminalSync.terminalSyncAttempts.set(taskId, attempt + 1);
  const timer = setTimeout(async () => {
    terminalSync.terminalSyncTimers.delete(taskId);
    await syncTerminalTask(taskId);
  }, delay);
  terminalSync.terminalSyncTimers.set(taskId, timer);
}

async function syncTerminalTask(taskId) {
  const context = runLifecycle.getTaskContext(taskId);
  const conversationId = context && context.conversationId;
  if (!taskId || !runLifecycle.isTerminalTask(taskId) || !conversationId) return false;
  if (terminalSync.syncedTaskIds.has(taskId)) return true;
  if (terminalSync.syncingTaskIds.has(taskId)) return false;

  terminalSync.syncingTaskIds.add(taskId);
  let shouldRetry = false;
  try {
    const result = await callApi("sync_chat_result", conversationId, taskId);
    if (result.ok !== true || result.status === "running") {
      shouldRetry = true;
      return false;
    }
    clearTerminalSyncRetry(taskId);
    terminalSync.syncedTaskIds.add(taskId);
    await loadConversationSidebar();
    return true;
  } catch (error) {
    shouldRetry = true;
    if (context && isRunContextVisible(context)) showToast("会话同步失败", error.message);
    return false;
  } finally {
    terminalSync.syncingTaskIds.delete(taskId);
    if (shouldRetry) scheduleTerminalSyncRetry(taskId);
  }
}

const MEMORY_KIND_GROUPS = [
  { kind: "identity", title: "用户画像", empty: "还没有形成稳定的用户画像。" },
  { kind: "preference", title: "偏好", empty: "还没有记录明确偏好。" },
  { kind: "work_habit", title: "工作习惯", empty: "还没有记录工作习惯。" },
  { kind: "project", title: "项目事实", empty: "还没有记录项目事实。" },
  { kind: "constraint", title: "明确约束", empty: "还没有记录明确约束。" },
  { kind: "decision", title: "决策记录", empty: "还没有记录已做决定。" },
  { kind: "open_question", title: "待确认问题", empty: "暂时没有待确认问题。" }
];

function api() {
  return window.pywebview && window.pywebview.api ? window.pywebview.api : null;
}

async function callApi(method, ...args) {
  const bridge = api();
  if (!bridge || typeof bridge[method] !== "function") {
    throw new Error("桌面桥尚未就绪");
  }
  return bridge[method](...args);
}

function setStatus(kind, text) {
  els.statusPill.className = `status ${kind}`;
  els.statusText.textContent = text;
}

function advanceConversationRevision() {
  state.conversationRevision += 1;
  state.messages = [];
  els.taskInput.value = "";
  resetRunSurface();
  setStatus("ready", "就绪");
}

function currentMemoryConversationContext() {
  return {
    conversationId: state.conversationId || "",
    conversationRevision: state.conversationRevision
  };
}

function syncMemoryCompressionControl() {
  const isCompressing = memoryOperations.isCompressionActive();
  els.compressCurrentConversation.disabled = !state.conversationId || isCompressing;
  els.compressCurrentConversation.textContent = isCompressing ? "压缩中" : "压缩当前会话";
}

function showToast(title, body) {
  els.toastTitle.textContent = title;
  els.toastBody.textContent = body;
  els.toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => els.toast.classList.remove("show"), 2800);
}

function addChatMessage(role, content, status = "completed", taskId = null) {
  const message = {
    id: `${Date.now()}_${Math.random().toString(16).slice(2)}`,
    role,
    content,
    status,
    taskId
  };
  state.messages.push(message);
  renderChatMessages();
  return message;
}

function updateAssistantForContext(context, patch) {
  if (!isRunContextVisible(context)) return;
  const message = state.messages.find((item) => item.id === context.assistantId);
  if (!message) return;
  Object.assign(message, patch);
  renderChatMessages();
}

function appendAssistantProgress(taskId, line) {
  if (!taskId || !line) return;
  els.taskActivity.textContent = line;
}

function renderChatMessages() {
  if (!els.chatMessages) return;
  if (!state.messages.length) {
    els.chatMessages.innerHTML = `
      <article class="chatMessage assistant">
        <div class="messageBubble">你好，我是 UTA。把任务发给我，我会在右侧展示拆解步骤和执行状态。</div>
      </article>
    `;
    return;
  }
  els.chatMessages.innerHTML = state.messages.map((message) => `
    <article class="chatMessage ${escapeHtml(message.role)} ${escapeHtml(message.status || "")}" data-message-id="${escapeHtml(message.id)}">
      <div class="messageBubble">
        ${message.role === "assistant" ? renderMarkdown(message.content || "") : escapeHtml(message.content || "")}
      </div>
    </article>
  `).join("");
  els.chatMessages.scrollTop = els.chatMessages.scrollHeight;
}

function updateKeyState(settings) {
  els.keyState.textContent = settings.has_api_key ? "Key：已配置" : "Key：未配置";
}

function updateDangerousToolsStatus(settings) {
  const enabled = settings.dangerous_tools_enabled === true;
  if (!els.dangerousToolsStatus) return;
  els.dangerousToolsStatus.textContent = enabled ? "工具授权：开启" : "工具授权：关闭";
  els.dangerousToolsStatus.classList.toggle("enabled", enabled);
}

function openSettings() {
  els.settingsModal.classList.add("open");
  els.baseUrl.focus();
}

function closeSettings() {
  els.settingsModal.classList.remove("open");
}

function showAuthorizationModal(payload) {
  state.pendingAuthorization = payload || null;
  const requestId = payload && payload.request_id ? payload.request_id : "";
  els.authorizationSummary.textContent = payload.summary || "请求执行高风险操作";
  const rows = [
    ["请求 ID", requestId],
    ["工具", payload.tool_name || ""],
    ["风险等级", payload.risk_level || ""],
    ["影响", payload.impact || ""],
    ["工作目录", payload.cwd || ""],
    ["文件路径", payload.path || ""],
    ["回收站路径", payload.trash_path || ""],
    ["命令", payload.command || ""],
    ["Python 代码", payload.code || ""],
    ["写入模式", payload.mode || ""],
    ["内容预览", payload.content_preview || ""]
  ].filter((row) => row[1]);
  els.authorizationDetails.innerHTML = rows.map(([label, value]) => `
    <dt>${escapeHtml(label)}</dt>
    <dd>${escapeHtml(String(value))}</dd>
  `).join("");
  els.authorizationModal.classList.add("open");
}

function closeAuthorizationModal() {
  els.authorizationModal.classList.remove("open");
  state.pendingAuthorization = null;
}

async function approveAuthorization() {
  const requestId = state.pendingAuthorization && state.pendingAuthorization.request_id;
  if (!requestId) return;
  const result = await callApi("authorize_operation", requestId);
  if (!result.ok) {
    showToast("授权失败", result.error || "未知错误");
    return;
  }
  closeAuthorizationModal();
  showToast("已授权", "操作继续执行");
}

async function rejectAuthorization() {
  const requestId = state.pendingAuthorization && state.pendingAuthorization.request_id;
  if (!requestId) return;
  const result = await callApi("reject_authorization", requestId, "用户拒绝授权");
  if (!result.ok) {
    showToast("拒绝失败", result.error || "未知错误");
    return;
  }
  closeAuthorizationModal();
  showToast("已拒绝", "操作不会执行");
}

async function loadSettings() {
  try {
    const settings = await callApi("get_settings");
    els.baseUrl.value = settings.llm_base_url || "";
    els.modelName.value = settings.llm_model || "";
    els.sslVerify.checked = settings.llm_ssl_verify !== false;
    els.dangerousToolsEnabled.checked = settings.dangerous_tools_enabled === true;
    updateKeyState(settings);
    updateDangerousToolsStatus(settings);
    els.bridgeState.textContent = "已连接";
  } catch (error) {
    els.bridgeState.textContent = "未连接";
    showToast("桌面桥未就绪", error.message);
  }
}

async function saveSettings(event) {
  event.preventDefault();
  const result = await callApi("save_settings", {
    llm_base_url: els.baseUrl.value,
    llm_model: els.modelName.value,
    llm_api_key: els.apiKey.value,
    llm_ssl_verify: els.sslVerify.checked,
    dangerous_tools_enabled: els.dangerousToolsEnabled.checked
  });
  if (!result.ok) {
    showToast("保存失败", result.error || "未知错误");
    return;
  }
  els.apiKey.value = "";
  closeSettings();
  await loadSettings();
  showToast("设置已保存", "配置已写入 ~/.uta/config.json");
}

async function clearKey() {
  const result = await callApi("save_settings", { clear_api_key: true });
  if (!result.ok) {
    showToast("清除失败", result.error || "未知错误");
    return;
  }
  await loadSettings();
  showToast("Key 已清除", "再次运行前需要重新填写 API Key");
}

async function loadExample() {
  const result = await callApi("load_example", state.activeExample);
  if (!result.ok) {
    showToast("载入失败", result.error || "未知错误");
    return;
  }
  els.taskInput.value = result.input;
  showToast("示例已载入", result.title);
}

async function loadConversationSidebar() {
  try {
    const result = await callApi("list_conversations");
    if (!result.ok) throw new Error(result.error || "读取会话失败");
    state.conversations = result.conversations || [];
    renderConversationSidebar(state.conversations);
  } catch (error) {
    showToast("读取会话失败", error.message);
  }
}

function showConversationView() {
  state.activePage = window.UTAShell.activatePage("conversation");
}

async function showCapabilityPage(pageName) {
  state.activePage = window.UTAShell.activatePage(pageName);
  if (pageName === "knowledge") await loadKnowledgeBase();
  if (pageName === "memory") await loadMemoryOverview();
  if (pageName === "capabilities") await loadSkillOverview();
}

function renderConversationSidebar(conversations) {
  const query = (els.conversationSearch.value || "").trim().toLowerCase();
  const visible = conversations.filter((conversation) => {
    const text = `${conversation.title || ""} ${conversation.preview || ""}`.toLowerCase();
    return !query || text.includes(query);
  });
  const groups = window.UTAShell.groupConversations(visible);
  const html = Object.entries(groups).map(([label, items]) => {
    if (!items.length) return "";
    const rows = items.map((conversation) => {
      const active = conversation.conversation_id === state.conversationId;
      return `
        <button class="conversationItem${active ? " active" : ""}" type="button" aria-current="${active ? "true" : "false"}" data-conversation-id="${escapeHtml(conversation.conversation_id)}">
          <strong>${escapeHtml(conversation.title || "新对话")}</strong>
          <small>${escapeHtml(conversation.preview || "暂无消息")}</small>
        </button>
      `;
    }).join("");
    return `<section class="conversationGroup"><h2>${label}</h2>${rows}</section>`;
  }).join("");
  els.conversationList.innerHTML = html || '<div class="emptyState">暂无匹配会话</div>';
  els.conversationList.querySelectorAll("[data-conversation-id]").forEach((button) => {
    button.addEventListener("click", () => openConversation(button.dataset.conversationId));
  });
}

async function startNewConversation() {
  if (runLifecycle.isBusy()) {
    showToast("任务运行中", "请先停止当前任务");
    return;
  }
  const result = await callApi("new_conversation");
  if (!result.ok) {
    showToast("新建失败", result.error || "未知错误");
    return;
  }
  state.conversationId = result.conversation.conversation_id;
  advanceConversationRevision();
  els.conversationTitle.textContent = "新任务";
  showConversationView();
  renderChatMessages();
  await loadConversationSidebar();
  els.taskInput.focus();
}

async function openConversation(conversationId) {
  if (runLifecycle.isBusy()) {
    showToast("任务运行中", "请先停止当前任务");
    return;
  }
  const result = await callApi("get_conversation", conversationId);
  if (!result.ok) {
    showToast("读取会话失败", result.error || "未知错误");
    return;
  }
  const conversation = result.conversation || {};
  state.conversationId = conversation.conversation_id;
  advanceConversationRevision();
  state.messages = (conversation.messages || []).map((message) => ({
    id: message.message_id || `${message.role}_${message.created_at || ""}`,
    role: message.role || "assistant",
    content: message.content || "",
    status: message.status || "completed",
    taskId: message.task_id || null,
    progress: []
  }));
  els.conversationTitle.textContent = conversation.title || "新对话";
  showConversationView();
  renderChatMessages();
  renderConversationSidebar(state.conversations);
}

// ---- 知识库 ----

async function loadKnowledgeBase() {
  try {
    const statsResult = await callApi("rag_stats");
    if (!statsResult.ok) {
      els.kbMode.textContent = "不可用";
      showToast("知识库错误", statsResult.error || "未知错误");
      return;
    }
    els.kbMode.textContent = statsResult.mode === "http" ? "HTTP 模式" : "内嵌模式";
    const s = statsResult.stats;
    els.kbStats.innerHTML = `文档：<strong>${s.documents}</strong> · 片段：<strong>${s.chunks}</strong> · 维度：<strong>${s.dim}</strong>`;
    await loadKnowledgeDocs();
  } catch (error) {
    els.kbMode.textContent = "错误";
    showToast("知识库加载失败", error.message);
  }
}

async function loadKnowledgeDocs() {
  try {
    const result = await callApi("rag_list_docs");
    if (!result.ok || !result.docs || !result.docs.length) {
      els.kbDocList.innerHTML = '<div class="emptyState">暂无文档，请摄入文件</div>';
      return;
    }
    els.kbDocList.innerHTML = result.docs.map((doc) => `
      <div class="knowledgeDocItem" data-doc-id="${escapeHtml(doc.doc_id)}">
        <div class="knowledgeDocMain">
          <strong>${escapeHtml(doc.title || doc.source)}</strong>
          <small>${escapeHtml(doc.type || "?")} · ${doc.chunk_count} 片段</small>
          <small class="knowledgeDocPath" title="${escapeHtml(doc.source)}">${escapeHtml(doc.source)}</small>
        </div>
        <button class="button ghost compact kbDelBtn" type="button" data-doc-id="${escapeHtml(doc.doc_id)}" title="删除此文档">删除</button>
      </div>
    `).join("");
    els.kbDocList.querySelectorAll(".kbDelBtn").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const docId = btn.dataset.docId;
        const r = await callApi("rag_delete", docId);
        if (r.ok !== false) {
          showToast("已删除", docId);
          await loadKnowledgeBase();
        }
      });
    });
  } catch (error) {
    showToast("读取文档失败", error.message);
  }
}

async function ingestKnowledge() {
  const path = els.kbIngestPath.value.trim();
  if (!path) {
    showToast("请输入路径", "输入文件或目录路径");
    return;
  }
  els.kbIngestBtn.disabled = true;
  els.kbMode.textContent = "摄入中...";
  try {
    const result = await callApi("rag_ingest", path);
    if (result.ok === false) {
      showToast("摄入失败", result.error || "未知错误");
    } else {
      const count = result.chunk_count || (result.ingested ? result.ingested.length : 0);
      showToast("摄入成功", `${count} 个片段已加入知识库`);
      els.kbIngestPath.value = "";
      await loadKnowledgeBase();
    }
  } catch (error) {
    showToast("摄入失败", error.message);
  } finally {
    els.kbIngestBtn.disabled = false;
  }
}

async function askKnowledge() {
  const question = els.kbQuestion.value.trim();
  if (!question) {
    showToast("请输入问题", "在上方输入框中输入你的问题");
    return;
  }
  els.kbAskBtn.disabled = true;
  els.kbQueryBtn.disabled = true;
  els.kbAskMeta.textContent = "检索中...";
  els.kbAnswer.className = "report knowledgeAnswer";
  els.kbAnswer.textContent = "正在检索并生成答案...";
  els.kbSources.innerHTML = "";
  try {
    const result = await callApi("rag_ask", question);
    renderKnowledgeResult(result, true);
  } catch (error) {
    els.kbAnswer.textContent = "错误：" + error.message;
  } finally {
    els.kbAskBtn.disabled = false;
    els.kbQueryBtn.disabled = false;
  }
}

async function queryKnowledge() {
  const question = els.kbQuestion.value.trim();
  if (!question) {
    showToast("请输入问题", "在上方输入框中输入你的问题");
    return;
  }
  els.kbAskBtn.disabled = true;
  els.kbQueryBtn.disabled = true;
  els.kbAskMeta.textContent = "检索中...";
  els.kbAnswer.className = "report knowledgeAnswer";
  els.kbAnswer.textContent = "正在检索...";
  els.kbSources.innerHTML = "";
  try {
    const result = await callApi("rag_query", question);
    renderKnowledgeResult(result, false);
  } catch (error) {
    els.kbAnswer.textContent = "错误：" + error.message;
  } finally {
    els.kbAskBtn.disabled = false;
    els.kbQueryBtn.disabled = false;
  }
}

function renderKnowledgeResult(result, isAsk) {
  if (result.ok === false) {
    els.kbAskMeta.textContent = "失败";
    els.kbAnswer.textContent = result.error || "未知错误";
    return;
  }
  els.kbAskMeta.textContent = "完成";
  if (isAsk && result.answer) {
    els.kbAnswer.innerHTML = renderMarkdown(result.answer);
  } else {
    els.kbAnswer.textContent = "仅检索模式，结果见下方来源片段。";
  }
  const sources = result.sources || result.chunks || [];
  if (sources.length) {
    els.kbSources.innerHTML = sources.map((s, i) => `
      <p class="logLine"><b>[${i + 1}]</b> score=${(s.score || 0).toFixed(3)} · ${escapeHtml(s.source || "?")}<br/>${escapeHtml((s.text || "").slice(0, 150))}</p>
    `).join("");
  } else {
    els.kbSources.innerHTML = '<p class="logLine">无检索结果</p>';
  }
}

async function loadMemoryOverview() {
  const loadContext = memoryOperations.beginLoad(currentMemoryConversationContext());
  try {
    const result = await callApi("get_memory_overview");
    if (!memoryOperations.isLoadCurrent(loadContext, currentMemoryConversationContext())) return;
    if (!result.ok) {
      showToast("读取记忆失败", result.error || "未知错误");
      return;
    }
    let currentConversation = null;
    if (loadContext.conversationId) {
      const conversationResult = await callApi("get_conversation", loadContext.conversationId);
      if (!memoryOperations.isLoadCurrent(loadContext, currentMemoryConversationContext())) return;
      if (conversationResult.ok) currentConversation = conversationResult.conversation || null;
    }
    if (!memoryOperations.isLoadCurrent(loadContext, currentMemoryConversationContext())) return;
    renderMemoryOverview(result, currentConversation);
  } catch (error) {
    if (memoryOperations.isLoadCurrent(loadContext, currentMemoryConversationContext())) {
      showToast("读取记忆失败", error.message);
    }
  } finally {
    memoryOperations.finishLoad(loadContext);
  }
}

function renderMemoryOverview(memory, currentConversation = null) {
  state.memoryOverview = memory;
  renderMemoryLongTerm(memory.long_term_facts || []);
  renderConversationShortTermMemory(currentConversation);
  renderMemoryLearning(memory);
  renderMemoryArchive(memory.task_history || []);
  setMemoryTab(state.memoryTab);
}

function renderConversationShortTermMemory(conversation) {
  syncMemoryCompressionControl();
  if (!conversation) {
    els.memoryConversationShortTerm.innerHTML = '<div class="emptyState">当前没有选中的会话。先发送消息，或从会话历史中打开一条会话。</div>';
    return;
  }
  const shortTerm = conversation.short_term || {};
  const summary = shortTerm.summary || "这个会话还没有生成短期摘要。";
  els.memoryConversationShortTerm.innerHTML = `
    <article class="memoryCard">
      <strong>${escapeHtml(conversation.title || "新对话")}</strong>
      <small>会话 ID：${escapeHtml(conversation.conversation_id || "")}</small>
      <small>短期摘要：${escapeHtml(summary)}</small>
      <small>已压缩到第 ${escapeHtml(shortTerm.compressed_until_index || 0)} 条消息 · 最近保留 ${escapeHtml(shortTerm.recent_message_limit || 12)} 条 · token 估算 ${escapeHtml(shortTerm.token_estimate || 0)}</small>
      <small>更新时间：${escapeHtml(shortTerm.updated_at || "尚未压缩")}</small>
    </article>
  `;
}

function renderMemoryLongTerm(facts) {
  const grouped = window.UTAShell.groupMemoryFacts(facts);
  const knownKinds = new Set(MEMORY_KIND_GROUPS.map((group) => group.kind));
  const groups = MEMORY_KIND_GROUPS.concat(
    Object.keys(grouped)
      .filter((kind) => !knownKinds.has(kind))
      .map((kind) => ({ kind, title: kind, empty: "暂无记忆。" }))
  );
  if (!groups.some((group) => group.kind === state.memoryLongTermKind)) {
    state.memoryLongTermKind = groups[0].kind;
  }
  els.memoryLongTermKinds.innerHTML = groups.map((group) => {
    const active = group.kind === state.memoryLongTermKind;
    return `
      <button class="memoryKindButton ${active ? "active" : ""}" type="button" aria-pressed="${active}" data-memory-kind="${escapeHtml(group.kind)}">
        <span>${escapeHtml(group.title)}</span><small>${(grouped[group.kind] || []).length}</small>
      </button>
    `;
  }).join("");

  const selectedGroup = groups.find((group) => group.kind === state.memoryLongTermKind);
  const selectedFacts = grouped[state.memoryLongTermKind] || [];
  els.memoryLongTermFacts.innerHTML = selectedFacts.length
    ? selectedFacts.slice().reverse().map(renderMemoryFact).join("")
    : `<div class="emptyState">${escapeHtml(selectedGroup.empty)}</div>`;
  els.memoryLongTermKinds.querySelectorAll("[data-memory-kind]").forEach((button) => {
    button.addEventListener("click", () => {
      state.memoryLongTermKind = button.dataset.memoryKind;
      renderMemoryLongTerm(state.memoryOverview?.long_term_facts || []);
    });
  });
}

function renderMemoryFact(fact) {
  const confidence = Number.isFinite(Number(fact.confidence)) ? `${Math.round(Number(fact.confidence) * 100)}%` : "未知";
  return `
    <article class="memoryFact">
      <p>${escapeHtml(fact.content || "")}</p>
      <details class="memoryDetails">
        <summary>来源详情</summary>
        <small>置信度：${escapeHtml(confidence)}</small>
        <small>来源会话：${escapeHtml(fact.source_conversation_id || "")}</small>
        <small>首次出现：${escapeHtml(fact.first_seen_at || "")}</small>
        <small>最近出现：${escapeHtml(fact.last_seen_at || "")}</small>
      </details>
    </article>
  `;
}

async function compressCurrentConversation() {
  if (!state.conversationId) {
    showToast("没有当前会话", "先发送一条消息，或从会话历史中打开一条会话。");
    return;
  }
  const compressionOwner = memoryOperations.beginCompression(currentMemoryConversationContext());
  if (!compressionOwner) {
    showToast("正在压缩", "已有会话正在压缩，请稍候。");
    return;
  }
  syncMemoryCompressionControl();
  try {
    const result = await callApi("compress_conversation", compressionOwner.conversationId);
    if (!result.ok) {
      showToast("压缩失败", result.error || "未知错误");
      return;
    }
    showToast(result.compressed ? "压缩完成" : "无需压缩", result.message || `已压缩到第 ${result.compressed_until_index || 0} 条消息`);
    await loadMemoryOverview();
  } catch (error) {
    showToast("压缩失败", error.message);
  } finally {
    if (memoryOperations.finishCompression(compressionOwner)) syncMemoryCompressionControl();
  }
}

function renderMemoryLearning(memory) {
  const lessons = window.UTAShell.dedupeMemoryLessons(memory.lessons || []);
  els.memoryLessons.innerHTML = lessons.length
    ? lessons.slice().reverse().map((lesson) => `
      <article class="memoryCard">
        <strong>${escapeHtml(window.UTAShell.memoryTaskTypeLabel(lesson.task_type))}</strong>
        <p>${escapeHtml(lesson.content || "")}</p>
        <small>累计 ${escapeHtml(lesson.occurrence_count || 1)} 次 · ${escapeHtml(lesson.created_at || "")}</small>
      </article>
    `).join("")
    : '<div class="emptyState">暂无经验</div>';

  const negativeRules = memory.negative_rules || [];
  els.memoryNegativeRules.innerHTML = negativeRules.length
    ? negativeRules.slice().reverse().map((rule) => `
      <article class="memoryCard">
        <strong>${escapeHtml(window.UTAShell.memoryTaskTypeLabel(rule.task_type))}</strong>
        <p>${escapeHtml(rule.content || "")}</p>
        <small>${escapeHtml(rule.created_at || "")}</small>
      </article>
    `).join("")
    : '<div class="emptyState">暂无负向规则</div>';

  const candidates = memory.skill_candidates || [];
  els.memorySkillCandidates.innerHTML = candidates.length
    ? candidates.slice().reverse().map((candidate) => `
      <article class="memoryCard">
        <strong>${escapeHtml(window.UTAShell.memoryTaskTypeLabel(candidate.task_type))}</strong>
        <p>${escapeHtml(candidate.reason || "")}</p>
        <small>${escapeHtml(window.UTAShell.memorySkillStatusLabel(candidate.status))} · 成功 ${escapeHtml(candidate.success_count || 0)} 次 · ${escapeHtml(candidate.updated_at || "")}</small>
      </article>
    `).join("")
    : '<div class="emptyState">暂无 Skill 候选</div>';
}

function renderMemoryArchive(tasks) {
  const sortedTasks = (tasks || []).slice().sort((left, right) => {
    const leftTime = Date.parse(left.updated_at || left.created_at || "") || 0;
    const rightTime = Date.parse(right.updated_at || right.created_at || "") || 0;
    return rightTime - leftTime;
  });
  if (!sortedTasks.length) {
    state.memoryArchiveTaskId = null;
    els.memoryArchiveList.innerHTML = '<div class="emptyState">暂无归档任务</div>';
    els.memoryArchiveDetail.innerHTML = '<div class="emptyState">选择任务后查看详情</div>';
    return;
  }
  if (!sortedTasks.some((task) => task.task_id === state.memoryArchiveTaskId)) {
    state.memoryArchiveTaskId = sortedTasks[0].task_id;
  }
  els.memoryArchiveList.innerHTML = sortedTasks.map((task) => {
    const active = task.task_id === state.memoryArchiveTaskId;
    const preview = task.user_input || task.intent || task.final_output_preview || task.task_id;
    return `
      <button class="memoryArchiveItem ${active ? "active" : ""}" type="button" aria-pressed="${active}" data-memory-task-id="${escapeHtml(task.task_id)}">
        <strong>${escapeHtml(window.UTAShell.compactMemoryText(preview, 72) || task.task_id)}</strong>
        <small>${escapeHtml(window.UTAShell.memoryTaskTypeLabel(task.task_type))} · ${escapeHtml(window.UTAShell.memoryTaskStatusLabel(task.status))}</small>
        <small>${escapeHtml(task.updated_at || task.created_at || "")}</small>
      </button>
    `;
  }).join("");

  const selectedTask = sortedTasks.find((task) => task.task_id === state.memoryArchiveTaskId);
  const detailMarkdown = [
    `## ${selectedTask.user_input || selectedTask.intent || selectedTask.task_id}`,
    `**任务 ID：** ${selectedTask.task_id}`,
    `**类型：** ${window.UTAShell.memoryTaskTypeLabel(selectedTask.task_type)}`,
    `**状态：** ${window.UTAShell.memoryTaskStatusLabel(selectedTask.status)}`,
    `**创建时间：** ${selectedTask.created_at || ""}`,
    `**更新时间：** ${selectedTask.updated_at || ""}`,
    `### 意图\n${selectedTask.intent || "无"}`,
    `### 最终输出\n${selectedTask.final_output_preview || "无输出预览"}`
  ].join("\n\n");
  els.memoryArchiveDetail.innerHTML = renderMarkdown(detailMarkdown);
  els.memoryArchiveList.querySelectorAll("[data-memory-task-id]").forEach((button) => {
    button.addEventListener("click", () => {
      state.memoryArchiveTaskId = button.dataset.memoryTaskId;
      renderMemoryArchive(state.memoryOverview?.task_history || []);
    });
  });
}

async function loadSkillOverview() {
  try {
    const result = await callApi("get_skill_overview");
    if (!result.ok) {
      showToast("读取技能包失败", result.error || "未知错误");
      return;
    }
    renderSkillOverview(result);
  } catch (error) {
    showToast("读取技能包失败", error.message);
  }
}

function renderSkillOverview(result) {
  const runtimeSkills = result.runtime_skills || [];
  const vendorPacks = result.vendor_packs || [];
  const errors = result.errors || [];
  els.skillPackMeta.textContent = `${runtimeSkills.length} 个 Skill · ${vendorPacks.length} 个规则包`;
  els.runtimeSkillList.innerHTML = renderRuntimeSkills(runtimeSkills);
  els.vendorSkillPackList.innerHTML = renderVendorPacks(vendorPacks);
  els.skillErrorList.innerHTML = renderSkillErrors(errors);
}

function renderRuntimeSkills(skills) {
  if (!skills.length) {
    return '<div class="emptyState">暂无运行时 Skill</div>';
  }
  return skills.map((skill) => {
    const keywords = (skill.trigger_keywords || []).join("、") || "无关键词";
    const workflow = (skill.workflow || []).join(" → ") || "无 workflow";
    return `
      <article class="memoryCard">
        <strong>${escapeHtml(skill.id || skill.name || "skill")}</strong>
        <small>${escapeHtml(skill.name || "")} · ${escapeHtml(skill.task_type || "unknown")} · ${skill.enabled ? "已启用" : "已停用"} · priority ${escapeHtml(skill.priority ?? 0)}</small>
        <small>关键词：${escapeHtml(keywords)}</small>
        <small>流程：${escapeHtml(workflow)}</small>
        <small>${escapeHtml(skill.source_path || "")}</small>
      </article>
    `;
  }).join("");
}

function renderVendorPacks(packs) {
  if (!packs.length) {
    return '<div class="emptyState">暂无 vendor 规则包</div>';
  }
  return packs.map((pack) => {
    const skillNames = (pack.skills || []).join("、") || "无子 skill";
    return `
      <article class="memoryCard">
        <strong>${escapeHtml(pack.name || "vendor")}</strong>
        <small>${pack.has_readme ? "README 已打包" : "缺少 README"} · ${escapeHtml(pack.skill_count || 0)} 个子 Skill</small>
        <small>${escapeHtml(skillNames)}</small>
        <small>${escapeHtml(pack.path || "")}</small>
      </article>
    `;
  }).join("");
}

function renderSkillErrors(errors) {
  if (!errors.length) {
    return '<div class="emptyState">未发现加载问题</div>';
  }
  return errors.map((error) => `
    <article class="memoryCard">
      <strong>${escapeHtml(error.path || "skill")}</strong>
      <small>${escapeHtml(error.error || "未知错误")}</small>
    </article>
  `).join("");
}

function resetRunSurface() {
  setTaskPanelOpen(false);
  setStopTaskVisible(false);
  els.taskInput.readOnly = false;
  els.runTask.disabled = false;
  els.resumeTask.disabled = false;
  state.taskId = null;
  els.planList.innerHTML = "";
  els.logPanel.innerHTML = "";
  els.planMeta.textContent = "0 步";
  els.taskActivity.textContent = "尚未开始";
  els.taskIdLabel.textContent = "未运行";
  if (els.report) {
    els.report.className = "report empty hidden";
    els.report.textContent = "等待任务运行";
  }
  els.stateJson.textContent = JSON.stringify({ status: "idle", task_id: null }, null, 2);
  els.copyReport.disabled = true;
  state.reportText = "";
  renderTaskPanelEmptyStates();
}

async function runTask() {
  if (runLifecycle.isBusy()) {
    showToast("任务运行中", "当前版本一次只运行一个任务");
    return;
  }

  const text = els.taskInput.value.trim();
  if (!text) {
    showToast("请输入消息", "消息不能为空");
    return;
  }

  const requestRevision = state.conversationRevision;
  const requestConversationId = state.conversationId;
  resetRunSurface();
  addChatMessage("user", text, "completed");
  const assistant = addChatMessage("assistant", "正在分析任务...", "running");
  const requestAssistant = assistant;
  const requestContext = runLifecycle.beginRequest({
    conversationId: requestConversationId || "",
    conversationRevision: requestRevision,
    assistantId: assistant.id
  });
  if (!requestContext) {
    showToast("任务运行中", "当前版本一次只运行一个任务");
    return;
  }
  setStatus("running", "运行中");
  els.taskInput.readOnly = true;
  els.runTask.disabled = true;
  els.resumeTask.disabled = true;

  try {
    const result = await callApi("run_chat_message", requestConversationId || "", text);
    if (!result.ok) {
      const requestIsCurrent = runLifecycle.isCurrentRequest(requestContext.requestId);
      runLifecycle.finishRequest(requestContext.requestId);
      if (!requestIsCurrent || state.conversationRevision !== requestRevision) {
        await loadConversationSidebar();
        return;
      }
      setStatus("error", "未运行");
      Object.assign(requestAssistant, { content: result.error || "未知错误", status: "failed" });
      renderChatMessages();
      showToast("无法运行", result.error || "未知错误");
      if ((result.error || "").includes("Key") || result.open_settings) openSettings();
      return;
    }
    if (result.direct) {
      runLifecycle.finishRequest(requestContext.requestId);
      if (state.conversationRevision !== requestRevision) {
        await loadConversationSidebar();
        return;
      }
      els.taskInput.value = "";
      setTaskPanelOpen(false);
      setStopTaskVisible(false);
      state.conversationId = result.conversation_id;
      Object.assign(requestAssistant, { content: result.message || "已回复。", status: "completed" });
      renderChatMessages();
      setStatus("done", "已回复");
      await loadConversationSidebar();
      return;
    }

    const binding = runLifecycle.bindTask(requestContext.requestId, {
      taskId: result.task_id,
      conversationId: result.conversation_id
    });
    if (!binding.ok) {
      await loadConversationSidebar();
      return;
    }
    const requestIsStale = state.conversationRevision !== requestRevision;
    if (!requestIsStale) {
      els.taskInput.value = "";
      state.conversationId = binding.context.conversationId;
      state.taskId = binding.context.taskId;
      requestAssistant.taskId = binding.context.taskId;
      renderChatMessages();
      els.taskIdLabel.textContent = binding.context.taskId;
      renderTaskPanelEmptyStates();
      setTaskPanelTab("progress");
      setTaskPanelOpen(true);
    }
    for (const earlyEvent of binding.events) {
      await handleProgress(earlyEvent);
    }
    if (state.conversationRevision !== requestRevision) {
      await loadConversationSidebar();
      return;
    }
    if (!runLifecycle.isTerminalTask(binding.context.taskId)) {
      setStopTaskVisible(true);
    }
  } catch (error) {
    const requestIsCurrent = runLifecycle.isCurrentRequest(requestContext.requestId);
    if (requestIsCurrent) runLifecycle.finishRequest(requestContext.requestId);
    if (state.conversationRevision !== requestRevision) {
      await loadConversationSidebar();
      return;
    }
    setStatus("error", "失败");
    Object.assign(requestAssistant, { content: error.message, status: "failed" });
    renderChatMessages();
    showToast("运行失败", error.message);
  } finally {
    if (state.conversationRevision === requestRevision) unlockComposerIfIdle();
  }
}

async function resumeTask() {
  if (runLifecycle.isBusy()) {
    showToast("任务运行中", "当前版本一次只运行一个任务");
    return;
  }
  const taskId = window.prompt("输入要恢复的 task_id");
  if (!taskId || !taskId.trim()) return;

  resetRunSurface();
  const resumeTaskId = taskId.trim();
  state.taskId = resumeTaskId;
  const assistant = addChatMessage("assistant", `正在从 checkpoint 恢复：${resumeTaskId}`, "running", resumeTaskId);
  const requestContext = runLifecycle.beginRequest({
    conversationId: state.conversationId || "",
    conversationRevision: state.conversationRevision,
    assistantId: assistant.id
  });
  const binding = runLifecycle.bindTask(requestContext.requestId, {
    taskId: resumeTaskId,
    conversationId: state.conversationId || ""
  });
  const context = binding.context;
  setStatus("running", "恢复中");
  els.taskIdLabel.textContent = resumeTaskId;
  els.taskInput.readOnly = true;
  els.runTask.disabled = true;
  els.resumeTask.disabled = true;

  try {
    const result = await callApi("resume_task", resumeTaskId);
    if (!result.ok) {
      runLifecycle.finishTask(resumeTaskId, "failed");
      setStatus("error", "恢复失败");
      updateAssistantForContext(context, { content: result.error || "恢复失败", status: "failed" });
      showToast("恢复失败", result.error || "checkpoint 不存在");
      return;
    }
    state.taskId = resumeTaskId;
    els.taskIdLabel.textContent = resumeTaskId;
    renderTaskPanelEmptyStates();
    if (!runLifecycle.isTerminalTask(resumeTaskId)) {
      setTaskPanelTab("progress");
      setTaskPanelOpen(true);
      setStopTaskVisible(true);
    }
  } catch (error) {
    runLifecycle.finishTask(resumeTaskId, "failed");
    setStatus("error", "恢复失败");
    updateAssistantForContext(context, { content: error.message, status: "failed" });
    showToast("恢复失败", error.message);
  } finally {
    unlockComposerIfIdle();
  }
}

async function stopTask() {
  const taskId = state.taskId;
  if (!taskId || !runLifecycle.beginCancel(taskId)) return;
  const context = runLifecycle.getTaskContext(taskId);
  els.stopTask.disabled = true;
  setStatus("running", "正在停止");
  try {
    const result = await callApi("cancel_task", taskId);
    if (!result.ok) {
      if (runLifecycle.failCancel(taskId) && isRunContextVisible(context)) {
        setStatus("running", "运行中");
        setStopTaskVisible(true);
        showToast("无法停止", result.error || "停止任务失败");
      }
      return;
    }
    runLifecycle.confirmCancel(taskId);
  } catch (error) {
    if (runLifecycle.failCancel(taskId) && isRunContextVisible(context)) {
      setStatus("running", "运行中");
      setStopTaskVisible(true);
      showToast("无法停止", error.message);
    }
  }
}

function stepMarkerFor(kind) {
  if (kind === "done") return "[x]";
  if (kind === "failed") return "[!]";
  if (kind === "active") return "[...]";
  return "[ ]";
}

function renderPlan(steps) {
  els.planMeta.textContent = `${steps.length} 步`;
  els.planList.innerHTML = steps.map((step) => `
    <div class="step" data-step-id="${step.step_id}">
      <span class="stepIcon">${stepMarkerFor("pending")}</span>
      <span><strong>${escapeHtml(step.goal)}</strong><small>pending</small></span>
      <small></small>
    </div>
  `).join("");
}

function markStep(stepId, kind, label, toolName) {
  const row = els.planList.querySelector(`[data-step-id="${stepId}"]`);
  if (!row) return;
  row.classList.remove("active", "done", "failed");
  if (kind) row.classList.add(kind);
  row.querySelector(".stepIcon").textContent = stepMarkerFor(kind);
  row.querySelector("small").textContent = label;
  const tool = row.querySelector("small:last-child");
  if (toolName) tool.textContent = toolName;
}

function addLog(source, message) {
  const row = document.createElement("p");
  row.className = "logLine";
  row.innerHTML = `<b>[${escapeHtml(source)}]</b> ${escapeHtml(message)}`;
  els.logPanel.appendChild(row);
  els.logPanel.scrollTop = els.logPanel.scrollHeight;
}

function sourceFor(event) {
  const map = {
    task_received: "Main",
    parsed: "TaskParser",
    skill_matched: "SkillLoader",
    plan_created: "Planner",
    plan_resumed: "Checkpoint",
    step_started: "Loop",
    tool_selected: "Router",
    tool_executed: "Executor",
    verified: "Verifier",
    reflection: "Reflection",
    replanned: "Replan",
    step_done: "Loop",
    memory_saved: "Memory",
    task_completed: "Result",
    cancelled: "Runner",
    authorization_required: "Authorization",
    error: "Error"
  };
  return map[event.type] || event.type;
}

function messageFor(event) {
  const data = event.data || {};
  if (event.type === "task_received") return "收到任务";
  if (event.type === "parsed") return `类型 ${data.task_type}，意图 ${data.intent}`;
  if (event.type === "skill_matched") return `匹配 Skill：${data.skill_id || "none"}`;
  if (event.type === "plan_created") return `生成 ${data.steps.length} 个步骤`;
  if (event.type === "plan_resumed") return `恢复到步骤 ${data.resume_step_id || "完成检查"}`;
  if (event.type === "step_started") return `开始步骤 ${data.step_id}：${data.goal}`;
  if (event.type === "tool_selected") return `步骤 ${data.step_id} 路由到 ${data.tool_name}`;
  if (event.type === "tool_executed") return `工具 ${data.tool_name} 执行 ${data.success ? "成功" : "失败"}`;
  if (event.type === "verified") return `步骤 ${data.step_id} 校验 ${data.passed ? "通过" : "未通过"}`;
  if (event.type === "reflection") return `${data.failure_type}，${data.repair_strategy}`;
  if (event.type === "replanned") return `从步骤 ${data.resume_step_id} 继续`;
  if (event.type === "step_done") return `步骤 ${data.step_id} ${data.status}`;
  if (event.type === "memory_saved") return `保存状态：${data.saved ? "true" : "false"}`;
  if (event.type === "task_completed") return `任务结束：${data.status}`;
  if (event.type === "cancelled") return "任务已停止";
  if (event.type === "authorization_required") return data.summary || "等待用户授权";
  if (event.type === "error") return data.message || "未知错误";
  return JSON.stringify(data);
}

async function handleProgress(event) {
  const route = runLifecycle.routeEvent(event);
  if (route.disposition === "buffered" || route.disposition === "ignored") return;
  const taskId = route.taskId;
  const context = route.context;
  const visible = route.disposition === "visible" && isRunContextVisible(context);
  if (!visible) {
    if (route.terminal) {
      await syncTerminalTask(taskId);
      await refreshResult(taskId);
    }
    return;
  }

  addLog(sourceFor(event), messageFor(event));
  const data = event.data || {};

  if (event.type === "task_received") {
    appendAssistantProgress(taskId, "收到任务，正在解析...");
  }
  if (event.type === "parsed") {
    appendAssistantProgress(taskId, `识别任务：${data.task_type || "unknown"}`);
    updateAssistantForContext(context, { content: "已理解任务，正在制定执行步骤...", status: "running" });
  }
  if (event.type === "skill_matched" && data.skill_id) {
    appendAssistantProgress(taskId, `匹配 Skill：${data.skill_id}`);
  }
  if (event.type === "plan_created" || event.type === "plan_resumed") {
    renderPlan(data.steps || []);
    appendAssistantProgress(
      taskId,
      event.type === "plan_resumed"
        ? `从步骤 ${data.resume_step_id || "完成检查"} 恢复`
        : `生成 ${(data.steps || []).length} 个步骤`
    );
    updateAssistantForContext(context, {
      content: event.type === "plan_resumed"
        ? `已从 checkpoint 恢复，正在继续执行...`
        : `已拆解为 ${(data.steps || []).length} 个步骤，正在执行...`,
      status: "running"
    });
  }
  if (event.type === "step_started") {
    appendAssistantProgress(taskId, `开始步骤 ${data.step_id}：${data.goal}`);
    markStep(data.step_id, "active", "running");
  }
  if (event.type === "tool_selected") {
    appendAssistantProgress(taskId, `调用工具：${data.tool_name}`);
    markStep(data.step_id, "active", "tool", data.tool_name);
  }
  if (event.type === "authorization_required") {
    appendAssistantProgress(taskId, `等待授权：${data.summary || data.tool_name || "高风险操作"}`);
    updateAssistantForContext(context, {
      content: "需要你手动授权后才能继续执行这个高风险操作。",
      status: "running"
    });
    showAuthorizationModal(data);
  }
  if (event.type === "replanned") markStep(data.failed_step_id, "active", "重新规划");
  if (event.type === "verified") {
    appendAssistantProgress(taskId, `校验${data.passed ? "通过" : "未通过"}：步骤 ${data.step_id}`);
  }
  if (event.type === "step_done") {
    appendAssistantProgress(taskId, `步骤 ${data.step_id}：${data.status}`);
    markStep(data.step_id, data.status === "completed" ? "done" : "failed", data.status);
  }

  if (event.type === "task_completed") {
    setStopTaskVisible(false);
    unlockComposerIfIdle();
    setStatus(data.status === "completed" ? "done" : "error", data.status === "completed" ? "已完成" : "失败");
    state.reportText = data.final_output || "";
    updateAssistantForContext(context, {
      content: state.reportText || "未生成输出",
      status: data.status === "completed" ? "completed" : "failed"
    });
    if (els.report) {
      els.report.className = "report hidden";
      els.report.innerHTML = renderMarkdown(state.reportText);
    }
    els.copyReport.disabled = !state.reportText;
    await syncTerminalTask(taskId);
    await refreshResult(taskId);
  }

  if (event.type === "error") {
    setStopTaskVisible(false);
    unlockComposerIfIdle();
    setStatus("error", "失败");
    updateAssistantForContext(context, { content: data.message || "任务失败", status: "failed" });
    await syncTerminalTask(taskId);
    await refreshResult(taskId);
  }

  if (event.type === "cancelled") {
    setStopTaskVisible(false);
    unlockComposerIfIdle();
    setStatus("done", "已停止");
    updateAssistantForContext(context, { content: "任务已停止", status: "completed" });
    await syncTerminalTask(taskId);
    await refreshResult(taskId);
  }
}

async function refreshResult(taskId) {
  const context = runLifecycle.getTaskContext(taskId);
  if (!taskId || !context) return;
  try {
    const result = await callApi("get_result", taskId);
    if (!isRunContextVisible(context)) return;
    els.stateJson.textContent = JSON.stringify(result.state || result, null, 2);
  } catch (error) {
    if (!isRunContextVisible(context)) return;
    els.stateJson.textContent = JSON.stringify({ error: error.message }, null, 2);
  }
}

function renderMarkdown(text) {
  if (!text) return "<p>无输出</p>";
  const lines = text.split(/\r?\n/);
  let html = "";
  let listType = null;
  const closeList = () => {
    if (!listType) return;
    html += `</${listType}>`;
    listType = null;
  };
  const ensureList = (type) => {
    if (listType === type) return;
    closeList();
    html += `<${type}>`;
    listType = type;
  };
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const orderedMatch = trimmed.match(/^(\d+)[.、]\s+(.+)$/);
    if (trimmed.startsWith("# ")) {
      closeList();
      html += `<h1>${renderInlineMarkdown(trimmed.slice(2))}</h1>`;
    } else if (trimmed.startsWith("## ")) {
      closeList();
      html += `<h2>${renderInlineMarkdown(trimmed.slice(3))}</h2>`;
    } else if (trimmed.startsWith("### ")) {
      closeList();
      html += `<h3>${renderInlineMarkdown(trimmed.slice(4))}</h3>`;
    } else if (trimmed.startsWith("- ")) {
      ensureList("ul");
      html += `<li>${renderInlineMarkdown(trimmed.slice(2))}</li>`;
    } else if (orderedMatch) {
      ensureList("ol");
      html += `<li>${renderInlineMarkdown(orderedMatch[2])}</li>`;
    } else {
      closeList();
      html += `<p>${renderInlineMarkdown(trimmed)}</p>`;
    }
  }
  closeList();
  return html;
}

function renderInlineMarkdown(value) {
  return escapeHtml(value)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function bindEvents() {
  els.newConversation.addEventListener("click", startNewConversation);
  els.conversationSearch.addEventListener("input", () => renderConversationSidebar(state.conversations));
  els.openKnowledge.addEventListener("click", () => showCapabilityPage("knowledge"));
  els.openMemory.addEventListener("click", () => showCapabilityPage("memory"));
  els.openSkills.addEventListener("click", () => showCapabilityPage("capabilities"));
  els.kbIngestBtn.addEventListener("click", ingestKnowledge);
  els.kbRefreshBtn.addEventListener("click", loadKnowledgeBase);
  els.kbAskBtn.addEventListener("click", askKnowledge);
  els.kbQueryBtn.addEventListener("click", queryKnowledge);
  els.refreshMemory.addEventListener("click", loadMemoryOverview);
  els.compressCurrentConversation.addEventListener("click", compressCurrentConversation);
  els.refreshSkills.addEventListener("click", loadSkillOverview);
  els.openSettingsSide.addEventListener("click", openSettings);
  els.dangerousToolsStatus.addEventListener("click", openSettings);
  els.closeSettings.addEventListener("click", closeSettings);
  els.settingsModal.addEventListener("click", (event) => {
    if (event.target === els.settingsModal) closeSettings();
  });
  els.settingsForm.addEventListener("submit", saveSettings);
  els.clearKey.addEventListener("click", clearKey);
  els.approveAuthorization.addEventListener("click", approveAuthorization);
  els.rejectAuthorization.addEventListener("click", rejectAuthorization);
  els.loadExample.addEventListener("click", loadExample);
  els.clearTask.addEventListener("click", () => {
    els.taskInput.value = "";
    els.taskInput.focus();
  });
  els.clearLogs.addEventListener("click", () => {
    els.logPanel.innerHTML = "";
  });
  els.runTask.addEventListener("click", runTask);
  els.resumeTask.addEventListener("click", resumeTask);
  els.stopTask.addEventListener("click", stopTask);
  els.toggleTaskPanel.addEventListener("click", () => setTaskPanelOpen(!state.taskPanelOpen));
  els.closeTaskPanel.addEventListener("click", () => setTaskPanelOpen(false));
  document.querySelectorAll("[data-task-tab]").forEach((button) => {
    button.addEventListener("click", () => setTaskPanelTab(button.dataset.taskTab));
    button.addEventListener("keydown", (event) => {
      const nextTab = window.UTAShell.handleTaskTabKeydown(event);
      if (nextTab) state.taskPanelTab = nextTab;
    });
  });
  document.querySelectorAll("[data-memory-tab]").forEach((button) => {
    button.addEventListener("click", () => setMemoryTab(button.dataset.memoryTab));
    button.addEventListener("keydown", (event) => {
      const nextTab = window.UTAShell.handleMemoryTabKeydown(event);
      if (nextTab) state.memoryTab = nextTab;
    });
  });
  els.taskInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      runTask();
    }
  });
  els.copyReport.addEventListener("click", async () => {
    if (!state.reportText) return;
    await navigator.clipboard.writeText(state.reportText);
    showToast("已复制", "报告已写入剪贴板");
  });
  document.querySelectorAll(".segment").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeExample = button.dataset.example;
      document.querySelectorAll(".segment").forEach((item) => item.classList.toggle("active", item === button));
    });
  });
}

window.onProgress = handleProgress;
bindEvents();
resetRunSurface();
renderChatMessages();

async function initializeDesktop() {
  await loadSettings();
  await loadConversationSidebar();
}

window.addEventListener("pywebviewready", initializeDesktop);
setTimeout(() => { if (api()) initializeDesktop(); }, 500);

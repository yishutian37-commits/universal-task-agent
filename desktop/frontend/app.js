const els = {
  bridgeState: document.getElementById("bridgeState"),
  keyState: document.getElementById("keyState"),
  chatMessages: document.getElementById("chatMessages"),
  chatDetailPanel: document.getElementById("chatDetailPanel"),
  openTaskView: document.getElementById("openTaskView"),
  openHistory: document.getElementById("openHistory"),
  openMemory: document.getElementById("openMemory"),
  openKnowledge: document.getElementById("openKnowledge"),
  openSkills: document.getElementById("openSkills"),
  taskView: document.getElementById("taskView"),
  historyView: document.getElementById("historyView"),
  memoryView: document.getElementById("memoryView"),
  knowledgeView: document.getElementById("knowledgeView"),
  skillsView: document.getElementById("skillsView"),
  refreshHistory: document.getElementById("refreshHistory"),
  refreshMemory: document.getElementById("refreshMemory"),
  refreshSkills: document.getElementById("refreshSkills"),
  historyList: document.getElementById("historyList"),
  historyTaskMeta: document.getElementById("historyTaskMeta"),
  historyReport: document.getElementById("historyReport"),
  historyLogPanel: document.getElementById("historyLogPanel"),
  historyStateJson: document.getElementById("historyStateJson"),
  memoryShortTerm: document.getElementById("memoryShortTerm"),
  memoryTaskHistory: document.getElementById("memoryTaskHistory"),
  memoryLessons: document.getElementById("memoryLessons"),
  memoryNegativeRules: document.getElementById("memoryNegativeRules"),
  memorySkillCandidates: document.getElementById("memorySkillCandidates"),
  statusPill: document.getElementById("statusPill"),
  statusText: document.getElementById("statusText"),
  taskIdLabel: document.getElementById("taskIdLabel"),
  taskInput: document.getElementById("taskInput"),
  runTask: document.getElementById("runTask"),
  loadExample: document.getElementById("loadExample"),
  clearTask: document.getElementById("clearTask"),
  clearLogs: document.getElementById("clearLogs"),
  planMeta: document.getElementById("planMeta"),
  planList: document.getElementById("planList"),
  logPanel: document.getElementById("logPanel"),
  report: document.getElementById("report"),
  copyReport: document.getElementById("copyReport"),
  stateJson: document.getElementById("stateJson"),
  settingsModal: document.getElementById("settingsModal"),
  settingsForm: document.getElementById("settingsForm"),
  openSettings: document.getElementById("openSettings"),
  openSettingsSide: document.getElementById("openSettingsSide"),
  closeSettings: document.getElementById("closeSettings"),
  baseUrl: document.getElementById("baseUrl"),
  modelName: document.getElementById("modelName"),
  apiKey: document.getElementById("apiKey"),
  sslVerify: document.getElementById("sslVerify"),
  clearKey: document.getElementById("clearKey"),
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
  running: false,
  taskId: null,
  conversationId: null,
  messages: [],
  pendingAssistantId: null,
  reportText: "",
  historyRuns: []
};

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
    taskId,
    progress: []
  };
  state.messages.push(message);
  renderChatMessages();
  return message;
}

function updateAssistantMessage(taskId, patch) {
  const message = [...state.messages].reverse().find((item) => item.role === "assistant" && item.taskId === taskId);
  if (!message) return;
  Object.assign(message, patch);
  renderChatMessages();
}

function updatePendingAssistant(patch) {
  const message = state.messages.find((item) => item.id === state.pendingAssistantId);
  if (!message) return;
  Object.assign(message, patch);
  renderChatMessages();
}

function appendAssistantProgress(taskId, line) {
  const message = [...state.messages].reverse().find((item) => item.role === "assistant" && item.taskId === taskId);
  if (!message || !line) return;
  if (!Array.isArray(message.progress)) message.progress = [];
  message.progress.push(line);
  renderChatMessages();
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
        ${message.role === "assistant" ? renderMessageProgress(message) : ""}
      </div>
    </article>
  `).join("");
  els.chatMessages.scrollTop = els.chatMessages.scrollHeight;
}

function renderMessageProgress(message) {
  const progress = Array.isArray(message.progress) ? message.progress : [];
  if (!progress.length) return "";
  return `
    <div class="messageProgress">
      ${progress.slice(-12).map((line) => `<p class="progressLine">${escapeHtml(line)}</p>`).join("")}
    </div>
  `;
}

function updateKeyState(settings) {
  els.keyState.textContent = settings.has_api_key ? "Key：已配置" : "Key：未配置";
}

function openSettings() {
  els.settingsModal.classList.add("open");
  els.baseUrl.focus();
}

function closeSettings() {
  els.settingsModal.classList.remove("open");
}

async function loadSettings() {
  try {
    const settings = await callApi("get_settings");
    els.baseUrl.value = settings.llm_base_url || "";
    els.modelName.value = settings.llm_model || "";
    els.sslVerify.checked = settings.llm_ssl_verify !== false;
    updateKeyState(settings);
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
    llm_ssl_verify: els.sslVerify.checked
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

function setActiveNav(button) {
  document.querySelectorAll(".nav").forEach((item) => {
    item.classList.toggle("active", item === button);
  });
}

function showTaskView() {
  els.taskView.classList.remove("hidden");
  els.historyView.classList.add("hidden");
  els.memoryView.classList.add("hidden");
  els.knowledgeView.classList.add("hidden");
  els.skillsView.classList.add("hidden");
  setActiveNav(els.openTaskView);
}

async function showHistoryView() {
  els.taskView.classList.add("hidden");
  els.historyView.classList.remove("hidden");
  els.memoryView.classList.add("hidden");
  els.knowledgeView.classList.add("hidden");
  els.skillsView.classList.add("hidden");
  setActiveNav(els.openHistory);
  await loadConversationHistory();
}

async function showMemoryView() {
  els.taskView.classList.add("hidden");
  els.historyView.classList.add("hidden");
  els.memoryView.classList.remove("hidden");
  els.knowledgeView.classList.add("hidden");
  els.skillsView.classList.add("hidden");
  setActiveNav(els.openMemory);
  await loadMemoryOverview();
}

async function showKnowledgeView() {
  els.taskView.classList.add("hidden");
  els.historyView.classList.add("hidden");
  els.memoryView.classList.add("hidden");
  els.knowledgeView.classList.remove("hidden");
  els.skillsView.classList.add("hidden");
  setActiveNav(els.openKnowledge);
  await loadKnowledgeBase();
}

async function showSkillsView() {
  els.taskView.classList.add("hidden");
  els.historyView.classList.add("hidden");
  els.memoryView.classList.add("hidden");
  els.knowledgeView.classList.add("hidden");
  els.skillsView.classList.remove("hidden");
  setActiveNav(els.openSkills);
  await loadSkillOverview();
}

async function loadHistoryRuns() {
  try {
    const result = await callApi("list_runs");
    if (!result.ok) {
      showToast("读取运行记录失败", result.error || "未知错误");
      return;
    }
    state.historyRuns = result.runs || [];
    renderHistoryList(state.historyRuns);
    if (state.historyRuns.length > 0) {
      await selectHistoryRun(state.historyRuns[0].task_id);
    } else {
      renderEmptyHistoryDetail();
    }
  } catch (error) {
    showToast("读取运行记录失败", error.message);
  }
}

function renderHistoryList(runs) {
  if (!runs.length) {
    els.historyList.innerHTML = '<div class="emptyState">暂无运行记录</div>';
    return;
  }
  els.historyList.innerHTML = runs.map((run) => `
    <button class="historyItem" type="button" data-task-id="${escapeHtml(run.task_id)}">
      <span><strong>${escapeHtml(run.task_id)}</strong><small>${escapeHtml(run.task_type || "unknown")} · ${escapeHtml(run.status || "unknown")}</small></span>
      <small>${escapeHtml(run.preview || run.intent || "无输出")}</small>
    </button>
  `).join("");
  els.historyList.querySelectorAll(".historyItem").forEach((button) => {
    button.addEventListener("click", () => selectHistoryRun(button.dataset.taskId));
  });
}

async function selectHistoryRun(taskId) {
  try {
    const result = await callApi("get_run", taskId);
    if (!result.ok) {
      showToast("读取详情失败", result.error || "未知错误");
      return;
    }
    els.historyList.querySelectorAll(".historyItem").forEach((item) => {
      item.classList.toggle("active", item.dataset.taskId === taskId);
    });
    const runState = result.state || {};
    els.historyTaskMeta.textContent = `${runState.status || "unknown"} · ${runState.task_type || "unknown"}`;
    els.historyReport.className = "report";
    els.historyReport.innerHTML = renderMarkdown(result.final_output || "");
    els.historyLogPanel.textContent = result.log || "";
    els.historyStateJson.textContent = JSON.stringify(runState, null, 2);
  } catch (error) {
    showToast("读取详情失败", error.message);
  }
}

function renderEmptyHistoryDetail() {
  els.historyTaskMeta.textContent = "未选择";
  els.historyReport.className = "report empty";
  els.historyReport.textContent = "暂无运行记录";
  els.historyLogPanel.textContent = "";
  els.historyStateJson.textContent = JSON.stringify({ status: "idle", task_id: null }, null, 2);
}

async function loadConversationHistory() {
  try {
    const result = await callApi("list_conversations");
    if (!result.ok) {
      showToast("读取会话失败", result.error || "未知错误");
      return;
    }
    renderConversationList(result.conversations || []);
    renderEmptyConversationDetail();
  } catch (error) {
    showToast("读取会话失败", error.message);
  }
}

function renderConversationList(conversations) {
  if (!conversations.length) {
    els.historyList.innerHTML = '<div class="emptyState">暂无会话</div>';
    return;
  }
  els.historyList.innerHTML = conversations.map((conversation) => `
    <button class="historyItem" type="button" data-conversation-id="${escapeHtml(conversation.conversation_id)}">
      <span><strong>${escapeHtml(conversation.title || "新对话")}</strong><small>${escapeHtml(conversation.updated_at || "")} · ${escapeHtml(conversation.message_count || 0)} 条消息</small></span>
      <small>${escapeHtml(conversation.preview || "无输出")}</small>
    </button>
  `).join("");
  els.historyList.querySelectorAll(".historyItem").forEach((button) => {
    button.addEventListener("click", () => selectConversation(button.dataset.conversationId));
  });
}

async function selectConversation(conversationId) {
  try {
    const result = await callApi("get_conversation", conversationId);
    if (!result.ok) {
      showToast("读取会话失败", result.error || "未知错误");
      return;
    }
    const conversation = result.conversation || {};
    state.conversationId = conversation.conversation_id;
    state.messages = (conversation.messages || []).map((message) => ({
      id: `${message.role || "message"}_${message.task_id || ""}_${message.created_at || ""}`,
      role: message.role || "assistant",
      content: message.content || "",
      status: message.status || "completed",
      taskId: message.task_id || null
    }));
    showTaskView();
    renderChatMessages();
  } catch (error) {
    showToast("读取会话失败", error.message);
  }
}

function renderEmptyConversationDetail() {
  els.historyTaskMeta.textContent = "会话历史";
  els.historyReport.className = "report empty";
  els.historyReport.textContent = "选择一条会话后会回到对话页";
  els.historyLogPanel.textContent = "";
  els.historyStateJson.textContent = JSON.stringify({ status: "conversation_history" }, null, 2);
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
      <div class="historyItem" data-doc-id="${escapeHtml(doc.doc_id)}">
        <span><strong>${escapeHtml(doc.title || doc.source)}</strong><small>${escapeHtml(doc.type || "?")} · ${doc.chunk_count} 片段</small></span>
        <small>${escapeHtml(doc.source)}</small>
        <button class="button ghost compact kbDelBtn" type="button" data-doc-id="${escapeHtml(doc.doc_id)}" title="删除此文档" style="margin-top:6px;">删除</button>
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
  els.kbAnswer.className = "report";
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
  els.kbAnswer.className = "report";
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
  try {
    const result = await callApi("get_memory_overview");
    if (!result.ok) {
      showToast("读取记忆失败", result.error || "未知错误");
      return;
    }
    renderMemoryOverview(result);
  } catch (error) {
    showToast("读取记忆失败", error.message);
  }
}

function renderMemoryOverview(memory) {
  els.memoryShortTerm.innerHTML = renderShortTermMemory();
  els.memoryTaskHistory.innerHTML = renderMemoryCards(memory.task_history, "task_id", "暂无任务历史");
  els.memoryLessons.innerHTML = renderMemoryCards(memory.lessons, "lesson_id", "暂无经验");
  els.memoryNegativeRules.innerHTML = renderMemoryCards(memory.negative_rules, "rule_id", "暂无负向规则");
  els.memorySkillCandidates.innerHTML = renderMemoryCards(memory.skill_candidates, "task_type", "暂无 Skill 候选");
}

function renderShortTermMemory() {
  if (!state.taskId) {
    return '<div class="emptyState">当前没有运行中的任务，可从运行记录查看历史 state。</div>';
  }
  return `
    <article class="memoryCard">
      <strong>${escapeHtml(state.taskId)}</strong>
      <small>当前任务 state 会保存在右侧 state.json，并进入运行记录。</small>
    </article>
  `;
}

function renderMemoryCards(items, titleKey, emptyText) {
  if (!items || !items.length) {
    return `<div class="emptyState">${escapeHtml(emptyText)}</div>`;
  }
  return items.slice(-20).reverse().map((item) => {
    const title = item[titleKey] || item.task_id || item.status || "memory";
    const body = item.content || item.reason || item.final_output_preview || item.intent || JSON.stringify(item);
    return `
      <article class="memoryCard">
        <strong>${escapeHtml(String(title))}</strong>
        <small>${escapeHtml(String(body))}</small>
      </article>
    `;
  }).join("");
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
  els.planList.innerHTML = "";
  els.logPanel.innerHTML = "";
  els.planMeta.textContent = "0 步";
  if (els.report) {
    els.report.className = "report empty hidden";
    els.report.textContent = "等待任务运行";
  }
  els.stateJson.textContent = JSON.stringify({ status: "idle", task_id: null }, null, 2);
  els.copyReport.disabled = true;
  state.reportText = "";
}

async function runTask() {
  if (state.running) {
    showToast("任务运行中", "当前版本一次只运行一个任务");
    return;
  }

  const text = els.taskInput.value.trim();
  if (!text) {
    showToast("请输入消息", "消息不能为空");
    return;
  }

  resetRunSurface();
  addChatMessage("user", text, "completed");
  const assistant = addChatMessage("assistant", "正在分析任务...", "running");
  state.pendingAssistantId = assistant.id;
  setStatus("running", "运行中");
  els.taskInput.readOnly = true;
  els.runTask.disabled = true;

  try {
    const result = await callApi("run_chat_message", state.conversationId || "", text);
    if (!result.ok) {
      setStatus("error", "未运行");
      updatePendingAssistant({ content: result.error || "未知错误", status: "failed" });
      showToast("无法运行", result.error || "未知错误");
      if ((result.error || "").includes("Key")) openSettings();
      return;
    }
    els.taskInput.value = "";
    if (result.direct) {
      state.conversationId = result.conversation_id;
      updatePendingAssistant({ content: result.message || "已回复。", status: "completed" });
      setStatus("done", "已回复");
      return;
    }
    state.running = true;
    state.conversationId = result.conversation_id;
    state.taskId = result.task_id;
    assistant.taskId = result.task_id;
    renderChatMessages();
    els.taskIdLabel.textContent = result.task_id;
  } catch (error) {
    setStatus("error", "失败");
    updatePendingAssistant({ content: error.message, status: "failed" });
    showToast("运行失败", error.message);
  } finally {
    if (!state.running) {
      els.taskInput.readOnly = false;
      els.runTask.disabled = false;
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
    step_started: "Loop",
    tool_selected: "Router",
    tool_executed: "Executor",
    verified: "Verifier",
    reflection: "Reflection",
    replanned: "Replan",
    step_done: "Loop",
    memory_saved: "Memory",
    task_completed: "Result",
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
  if (event.type === "step_started") return `开始步骤 ${data.step_id}：${data.goal}`;
  if (event.type === "tool_selected") return `步骤 ${data.step_id} 路由到 ${data.tool_name}`;
  if (event.type === "tool_executed") return `工具 ${data.tool_name} 执行 ${data.success ? "成功" : "失败"}`;
  if (event.type === "verified") return `步骤 ${data.step_id} 校验 ${data.passed ? "通过" : "未通过"}`;
  if (event.type === "reflection") return `${data.failure_type}，${data.repair_strategy}`;
  if (event.type === "replanned") return `从步骤 ${data.resume_step_id} 继续`;
  if (event.type === "step_done") return `步骤 ${data.step_id} ${data.status}`;
  if (event.type === "memory_saved") return `保存状态：${data.saved ? "true" : "false"}`;
  if (event.type === "task_completed") return `任务结束：${data.status}`;
  if (event.type === "error") return data.message || "未知错误";
  return JSON.stringify(data);
}

async function handleProgress(event) {
  addLog(sourceFor(event), messageFor(event));
  const data = event.data || {};

  if (event.task_id && !state.taskId) {
    state.taskId = event.task_id;
    const pending = state.messages.find((item) => item.id === state.pendingAssistantId);
    if (pending) pending.taskId = event.task_id;
  }

  if (event.type === "task_received") {
    appendAssistantProgress(state.taskId, "收到任务，正在解析...");
  }
  if (event.type === "parsed") {
    appendAssistantProgress(state.taskId, `识别任务：${data.task_type || "unknown"}`);
    updateAssistantMessage(state.taskId, { content: "已理解任务，正在制定执行步骤...", status: "running" });
  }
  if (event.type === "skill_matched" && data.skill_id) {
    appendAssistantProgress(state.taskId, `匹配 Skill：${data.skill_id}`);
  }
  if (event.type === "plan_created") {
    renderPlan(data.steps || []);
    appendAssistantProgress(state.taskId, `生成 ${(data.steps || []).length} 个步骤`);
    updateAssistantMessage(state.taskId, {
      content: `已拆解为 ${(data.steps || []).length} 个步骤，正在执行...`,
      status: "running"
    });
  }
  if (event.type === "step_started") {
    appendAssistantProgress(state.taskId, `开始步骤 ${data.step_id}：${data.goal}`);
    markStep(data.step_id, "active", "running");
  }
  if (event.type === "tool_selected") {
    appendAssistantProgress(state.taskId, `调用工具：${data.tool_name}`);
    markStep(data.step_id, "active", "tool", data.tool_name);
  }
  if (event.type === "replanned") markStep(data.failed_step_id, "active", "重新规划");
  if (event.type === "verified") {
    appendAssistantProgress(state.taskId, `校验${data.passed ? "通过" : "未通过"}：步骤 ${data.step_id}`);
  }
  if (event.type === "step_done") {
    appendAssistantProgress(state.taskId, `步骤 ${data.step_id}：${data.status}`);
    markStep(data.step_id, data.status === "completed" ? "done" : "failed", data.status);
  }

  if (event.type === "task_completed") {
    state.running = false;
    els.taskInput.readOnly = false;
    els.runTask.disabled = false;
    setStatus(data.status === "completed" ? "done" : "error", data.status === "completed" ? "已完成" : "失败");
    state.reportText = data.final_output || "";
    updateAssistantMessage(state.taskId, {
      content: state.reportText || "未生成输出",
      status: data.status === "completed" ? "completed" : "failed"
    });
    if (els.report) {
      els.report.className = "report hidden";
      els.report.innerHTML = renderMarkdown(state.reportText);
    }
    els.copyReport.disabled = !state.reportText;
    await callApi("sync_chat_result", state.conversationId || "", state.taskId || "");
    await refreshResult();
  }

  if (event.type === "error") {
    state.running = false;
    els.taskInput.readOnly = false;
    els.runTask.disabled = false;
    setStatus("error", "失败");
    updateAssistantMessage(state.taskId, { content: data.message || "任务失败", status: "failed" });
    await refreshResult();
  }
}

async function refreshResult() {
  if (!state.taskId) return;
  try {
    const result = await callApi("get_result", state.taskId);
    els.stateJson.textContent = JSON.stringify(result.state || result, null, 2);
  } catch (error) {
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
  els.openTaskView.addEventListener("click", showTaskView);
  els.openHistory.addEventListener("click", showHistoryView);
  els.openMemory.addEventListener("click", showMemoryView);
  els.openKnowledge.addEventListener("click", showKnowledgeView);
  els.openSkills.addEventListener("click", showSkillsView);
  els.refreshHistory.addEventListener("click", loadHistoryRuns);
  els.kbIngestBtn.addEventListener("click", ingestKnowledge);
  els.kbRefreshBtn.addEventListener("click", loadKnowledgeBase);
  els.kbAskBtn.addEventListener("click", askKnowledge);
  els.kbQueryBtn.addEventListener("click", queryKnowledge);
  els.refreshMemory.addEventListener("click", loadMemoryOverview);
  els.refreshSkills.addEventListener("click", loadSkillOverview);
  els.openSettings.addEventListener("click", openSettings);
  els.openSettingsSide.addEventListener("click", openSettings);
  els.closeSettings.addEventListener("click", closeSettings);
  els.settingsModal.addEventListener("click", (event) => {
    if (event.target === els.settingsModal) closeSettings();
  });
  els.settingsForm.addEventListener("submit", saveSettings);
  els.clearKey.addEventListener("click", clearKey);
  els.loadExample.addEventListener("click", loadExample);
  els.clearTask.addEventListener("click", () => {
    els.taskInput.value = "";
    els.taskInput.focus();
  });
  els.clearLogs.addEventListener("click", () => {
    els.logPanel.innerHTML = "";
  });
  els.runTask.addEventListener("click", runTask);
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

// 强制设置对话面板高度——不依赖 CSS 高度继承（pywebview 下不可靠）
function fixChatLayout() {
  const chatPanel = document.querySelector(".chatPanel");
  const chatMessages = document.getElementById("chatMessages");
  const chatComposer = document.querySelector(".chatComposer");
  if (!chatPanel || !chatMessages || !chatComposer) return;

  // 计算 chatPanel 应有的高度：窗口高度 - titlebar(42) - mainHead 高度 - padding(36)
  const titlebar = document.querySelector(".titlebar");
  const mainHead = document.querySelector(".mainHead");
  const winH = window.innerHeight;
  const titleH = titlebar ? titlebar.offsetHeight : 42;
  const headH = mainHead ? mainHead.offsetHeight : 76;
  const panelH = winH - titleH - headH - 36; // 36 = workspace padding (18*2)

  chatPanel.style.height = Math.max(panelH, 200) + "px";

  // messages 高度 = panel - panelHead - composer
  const panelHead = chatPanel.querySelector(".panelHead");
  const pH = panelHead ? panelHead.offsetHeight : 52;
  const cH = chatComposer.offsetHeight;
  const msgH = Math.max(panelH - pH - cH, 120);
  chatMessages.style.height = msgH + "px";
}

window.addEventListener("resize", fixChatLayout);
window.addEventListener("pywebviewready", () => { fixChatLayout(); loadSettings(); });
setTimeout(() => { fixChatLayout(); if (api()) loadSettings(); }, 500);
setTimeout(fixChatLayout, 1500); // 确保渲染完成后再次修正

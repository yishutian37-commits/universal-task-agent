const els = {
  bridgeState: document.getElementById("bridgeState"),
  keyState: document.getElementById("keyState"),
  openTaskView: document.getElementById("openTaskView"),
  openHistory: document.getElementById("openHistory"),
  openMemory: document.getElementById("openMemory"),
  taskView: document.getElementById("taskView"),
  historyView: document.getElementById("historyView"),
  memoryView: document.getElementById("memoryView"),
  refreshHistory: document.getElementById("refreshHistory"),
  refreshMemory: document.getElementById("refreshMemory"),
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
  toastBody: document.getElementById("toastBody")
};

const state = {
  activeExample: "summarize",
  running: false,
  taskId: null,
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
  setActiveNav(els.openTaskView);
}

async function showHistoryView() {
  els.taskView.classList.add("hidden");
  els.historyView.classList.remove("hidden");
  els.memoryView.classList.add("hidden");
  setActiveNav(els.openHistory);
  await loadHistoryRuns();
}

async function showMemoryView() {
  els.taskView.classList.add("hidden");
  els.historyView.classList.add("hidden");
  els.memoryView.classList.remove("hidden");
  setActiveNav(els.openMemory);
  await loadMemoryOverview();
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

function resetRunSurface() {
  els.planList.innerHTML = "";
  els.logPanel.innerHTML = "";
  els.planMeta.textContent = "0 步";
  els.report.className = "report empty";
  els.report.textContent = "等待任务运行";
  els.stateJson.textContent = JSON.stringify({ status: "idle", task_id: null }, null, 2);
  els.copyReport.disabled = true;
  state.reportText = "";
}

async function runTask() {
  if (state.running) {
    showToast("任务运行中", "当前版本一次只运行一个任务");
    return;
  }

  resetRunSurface();
  setStatus("running", "运行中");
  els.taskInput.readOnly = true;
  els.runTask.disabled = true;

  try {
    const result = await callApi("run_task", els.taskInput.value);
    if (!result.ok) {
      setStatus("error", "未运行");
      showToast("无法运行", result.error || "未知错误");
      if ((result.error || "").includes("Key")) openSettings();
      return;
    }
    state.running = true;
    state.taskId = result.task_id;
    els.taskIdLabel.textContent = result.task_id;
  } catch (error) {
    setStatus("error", "失败");
    showToast("运行失败", error.message);
  } finally {
    if (!state.running) {
      els.taskInput.readOnly = false;
      els.runTask.disabled = false;
    }
  }
}

function renderPlan(steps) {
  els.planMeta.textContent = `${steps.length} 步`;
  els.planList.innerHTML = steps.map((step) => `
    <div class="step" data-step-id="${step.step_id}">
      <span class="stepIcon">${step.step_id}</span>
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
  row.querySelector(".stepIcon").textContent = kind === "done" ? "✓" : kind === "failed" ? "!" : "…";
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

  if (event.type === "plan_created") renderPlan(data.steps || []);
  if (event.type === "step_started") markStep(data.step_id, "active", "running");
  if (event.type === "tool_selected") markStep(data.step_id, "active", "tool", data.tool_name);
  if (event.type === "replanned") markStep(data.failed_step_id, "active", "重新规划");
  if (event.type === "step_done") markStep(data.step_id, data.status === "completed" ? "done" : "failed", data.status);

  if (event.type === "task_completed") {
    state.running = false;
    els.taskInput.readOnly = false;
    els.runTask.disabled = false;
    setStatus(data.status === "completed" ? "done" : "error", data.status === "completed" ? "已完成" : "失败");
    state.reportText = data.final_output || "";
    els.report.className = "report";
    els.report.innerHTML = renderMarkdown(state.reportText);
    els.copyReport.disabled = !state.reportText;
    await refreshResult();
  }

  if (event.type === "error") {
    state.running = false;
    els.taskInput.readOnly = false;
    els.runTask.disabled = false;
    setStatus("error", "失败");
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
  let inList = false;
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    if (trimmed.startsWith("## ")) {
      if (inList) { html += "</ul>"; inList = false; }
      html += `<h2>${escapeHtml(trimmed.slice(3))}</h2>`;
    } else if (trimmed.startsWith("### ")) {
      if (inList) { html += "</ul>"; inList = false; }
      html += `<h3>${escapeHtml(trimmed.slice(4))}</h3>`;
    } else if (trimmed.startsWith("- ")) {
      if (!inList) { html += "<ul>"; inList = true; }
      html += `<li>${escapeHtml(trimmed.slice(2))}</li>`;
    } else {
      if (inList) { html += "</ul>"; inList = false; }
      html += `<p>${escapeHtml(trimmed)}</p>`;
    }
  }
  if (inList) html += "</ul>";
  return html;
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
  els.refreshHistory.addEventListener("click", loadHistoryRuns);
  els.refreshMemory.addEventListener("click", loadMemoryOverview);
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

window.addEventListener("pywebviewready", loadSettings);
setTimeout(() => {
  if (api()) loadSettings();
}, 500);

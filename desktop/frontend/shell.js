(function bootstrapShell(root) {
  const PAGE_NAMES = new Set(["conversation", "knowledge", "memory", "capabilities"]);
  const TASK_TABS = new Set(["progress", "files", "changes", "artifacts", "diagnostics"]);
  const MEMORY_TABS = new Set(["long-term", "session", "learning", "archive"]);
  const TERMINAL_PHASES = new Set(["completed", "cancelled", "failed"]);

  function startOfDay(value) {
    return new Date(value.getFullYear(), value.getMonth(), value.getDate()).getTime();
  }

  function groupConversations(conversations, now = new Date()) {
    const today = startOfDay(now);
    const day = 24 * 60 * 60 * 1000;
    const groups = { "今天": [], "昨天": [], "更早": [] };
    (Array.isArray(conversations) ? conversations : []).forEach((conversation) => {
      const updatedAt = new Date(conversation.updated_at || 0);
      const distance = today - startOfDay(updatedAt);
      const label = distance <= 0 ? "今天" : distance <= day ? "昨天" : "更早";
      groups[label].push(conversation);
    });
    return groups;
  }

  function activatePage(pageName) {
    const nextPage = PAGE_NAMES.has(pageName) ? pageName : "conversation";
    if (!root.document) return nextPage;
    root.document.querySelectorAll("[data-page]").forEach((page) => {
      page.classList.toggle("hidden", page.dataset.page !== nextPage);
    });
    root.document.querySelectorAll("[data-page-target]").forEach((button) => {
      button.classList.toggle("active", button.dataset.pageTarget === nextPage);
    });
    return nextPage;
  }

  function setTaskPanelOpen(isOpen) {
    if (!root.document) return false;
    const workspace = root.document.getElementById("taskView");
    const panel = root.document.getElementById("chatDetailPanel");
    const toggle = root.document.getElementById("toggleTaskPanel");
    if (!workspace || !panel) return false;
    const open = Boolean(isOpen);
    const shouldRestoreFocus = !open && panel.contains(root.document.activeElement);
    workspace.classList.toggle("task-panel-open", open);
    panel.classList.toggle("collapsed", !open);
    panel.setAttribute("aria-hidden", String(!open));
    if (toggle) toggle.setAttribute("aria-expanded", String(open));
    if (shouldRestoreFocus && toggle) toggle.focus();
    return open;
  }

  function activateTaskTab(tabName) {
    const nextTab = TASK_TABS.has(tabName) ? tabName : "progress";
    if (!root.document) return nextTab;
    root.document.querySelectorAll("[data-task-tab]").forEach((button) => {
      const active = button.dataset.taskTab === nextTab;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
      button.tabIndex = active ? 0 : -1;
    });
    root.document.querySelectorAll("[data-task-panel]").forEach((panel) => {
      const active = panel.dataset.taskPanel === nextTab;
      panel.classList.toggle("hidden", !active);
      panel.setAttribute("aria-hidden", String(!active));
    });
    return nextTab;
  }

  function handleTaskTabKeydown(event) {
    if (!root.document || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
      return null;
    }
    const tabs = Array.from(root.document.querySelectorAll("[data-task-tab]"));
    const currentIndex = tabs.indexOf(event.currentTarget);
    if (currentIndex < 0 || !tabs.length) return null;
    let nextIndex = currentIndex;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = tabs.length - 1;
    if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % tabs.length;
    event.preventDefault();
    const nextTab = tabs[nextIndex];
    activateTaskTab(nextTab.dataset.taskTab);
    nextTab.focus();
    return nextTab.dataset.taskTab;
  }

  function activateMemoryTab(tabName) {
    const nextTab = MEMORY_TABS.has(tabName) ? tabName : "long-term";
    if (!root.document) return nextTab;
    root.document.querySelectorAll("[data-memory-tab]").forEach((button) => {
      const active = button.dataset.memoryTab === nextTab;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
      button.tabIndex = active ? 0 : -1;
    });
    root.document.querySelectorAll("[data-memory-panel]").forEach((panel) => {
      const active = panel.dataset.memoryPanel === nextTab;
      panel.hidden = !active;
      panel.setAttribute("aria-hidden", String(!active));
    });
    return nextTab;
  }

  function handleMemoryTabKeydown(event) {
    if (!root.document || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
      return null;
    }
    const tabs = Array.from(root.document.querySelectorAll("[data-memory-tab]"));
    const currentIndex = tabs.indexOf(event.currentTarget);
    if (currentIndex < 0 || !tabs.length) return null;
    let nextIndex = currentIndex;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = tabs.length - 1;
    if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % tabs.length;
    event.preventDefault();
    const nextTab = tabs[nextIndex];
    activateMemoryTab(nextTab.dataset.memoryTab);
    nextTab.focus();
    return nextTab.dataset.memoryTab;
  }

  function groupMemoryFacts(facts) {
    const groups = {};
    (Array.isArray(facts) ? facts : []).forEach((fact) => {
      if (!fact || typeof fact !== "object") return;
      const kind = typeof fact.kind === "string" && fact.kind.trim() ? fact.kind.trim() : "unknown";
      if (!groups[kind]) groups[kind] = [];
      groups[kind].push(fact);
    });
    return groups;
  }

  function compactMemoryText(value, limit = 160) {
    const text = value === null || value === undefined ? "" : String(value);
    const compacted = text
      .replace(/```[^\n]*\n?/g, "")
      .replace(/^\s{0,3}#{1,6}\s*/gm, "")
      .replace(/^\s*(?:[-*+]|\d+[.)]|\d+\u3001)\s+/gm, "")
      .replace(/(?:\*\*|__)/g, "")
      .replace(/`/g, "")
      .replace(/\s+/g, " ")
      .trim();
    const maxLength = Math.max(0, Number.isFinite(Number(limit)) ? Math.floor(Number(limit)) : 160);
    if (compacted.length <= maxLength) return compacted;
    const ellipsis = "...".slice(0, maxLength);
    return `${compacted.slice(0, maxLength - ellipsis.length)}${ellipsis}`;
  }

  function memoryLessonTimestamp(item) {
    for (const field of ["updated_at", "created_at"]) {
      const value = item[field];
      const timestamp = typeof value === "number"
        ? value
        : typeof value === "string" || value instanceof Date
          ? new Date(value).getTime()
          : Number.NaN;
      if (Number.isFinite(timestamp)) return timestamp;
    }
    return null;
  }

  function dedupeMemoryLessons(items) {
    const lessons = new Map();
    (Array.isArray(items) ? items : []).forEach((item) => {
      if (!item || typeof item !== "object") return;
      const key = JSON.stringify([item.task_type || "", item.content || ""]);
      const existing = lessons.get(key);
      const occurrenceCount = (existing?.occurrence_count || 0) + 1;
      const itemTimestamp = memoryLessonTimestamp(item);
      const existingTimestamp = existing ? memoryLessonTimestamp(existing) : null;
      const shouldReplace = !existing
        || (itemTimestamp !== null && (existingTimestamp === null || itemTimestamp >= existingTimestamp))
        || (itemTimestamp === null && existingTimestamp === null);
      lessons.set(
        key,
        shouldReplace
          ? { ...item, occurrence_count: occurrenceCount }
          : { ...existing, occurrence_count: occurrenceCount }
      );
    });
    return Array.from(lessons.values());
  }

  function createMemoryOperationLifecycle() {
    let loadSequence = 0;
    let activeLoad = null;
    let compressionSequence = 0;
    let compressionOwner = null;

    function normalizeContext(input = {}, operationId) {
      return Object.freeze({
        operationId,
        conversationId: String(input.conversationId || ""),
        conversationRevision: Number(input.conversationRevision || 0)
      });
    }

    function sameConversation(context, input = {}) {
      return Boolean(
        context
        && context.conversationId === String(input.conversationId || "")
        && context.conversationRevision === Number(input.conversationRevision || 0)
      );
    }

    function beginLoad(input = {}) {
      activeLoad = normalizeContext(input, `memory-load-${++loadSequence}`);
      return activeLoad;
    }

    function isLoadCurrent(context, currentConversation = {}) {
      return Boolean(
        activeLoad
        && context
        && activeLoad.operationId === context.operationId
        && sameConversation(context, currentConversation)
      );
    }

    function finishLoad(context) {
      if (!activeLoad || !context || activeLoad.operationId !== context.operationId) return false;
      activeLoad = null;
      return true;
    }

    function beginCompression(input = {}) {
      if (compressionOwner) return null;
      compressionOwner = normalizeContext(input, `memory-compression-${++compressionSequence}`);
      return compressionOwner;
    }

    function isCompressionOwner(context) {
      return Boolean(
        compressionOwner
        && context
        && compressionOwner.operationId === context.operationId
      );
    }

    function finishCompression(context) {
      if (!isCompressionOwner(context)) return false;
      compressionOwner = null;
      return true;
    }

    return {
      beginLoad,
      isLoadCurrent,
      finishLoad,
      beginCompression,
      isCompressionOwner,
      finishCompression,
      isCompressionActive: () => Boolean(compressionOwner),
      getCompressionOwner: () => compressionOwner
    };
  }

  const MEMORY_TASK_TYPE_LABELS = Object.freeze({
    summarize: "文本总结",
    data_analysis: "表格分析",
    research: "联网调研",
    geo_analysis: "地理分析",
    history_query: "历史任务查询",
    complex_task: "复杂任务",
    code_reading: "代码阅读",
    langchain_tool: "工具调用",
    chat: "普通对话",
    task: "通用任务"
  });

  const MEMORY_TASK_STATUS_LABELS = Object.freeze({
    completed: "已完成",
    failed: "失败",
    cancelled: "已取消",
    stopped: "已停止",
    running: "运行中",
    pending: "待处理"
  });

  const MEMORY_SKILL_STATUS_LABELS = Object.freeze({
    tracking: "观察中",
    candidate: "待创建",
    pending: "待评估",
    active: "已启用",
    rejected: "已忽略"
  });

  function enumLabel(labels, value, fallback) {
    return labels[String(value || "").trim().toLowerCase()] || fallback;
  }

  function memoryTaskTypeLabel(value) {
    return enumLabel(MEMORY_TASK_TYPE_LABELS, value, "其他任务");
  }

  function memoryTaskStatusLabel(value) {
    return enumLabel(MEMORY_TASK_STATUS_LABELS, value, "未知状态");
  }

  function memorySkillStatusLabel(value) {
    return enumLabel(MEMORY_SKILL_STATUS_LABELS, value, "未知状态");
  }

  function localizeMemoryTaskText(value, taskType) {
    const text = String(value || "");
    const rawTaskType = String(taskType || "").trim();
    if (!rawTaskType) return text;
    return text.split(rawTaskType).join(memoryTaskTypeLabel(rawTaskType));
  }

  function createRunLifecycle() {
    let requestSequence = 0;
    let activeRequest = null;
    let currentTaskId = null;
    const tasks = new Map();
    const earlyEvents = new Map();

    function isTerminalPhase(phase) {
      return TERMINAL_PHASES.has(phase);
    }

    function currentRecord() {
      return currentTaskId ? tasks.get(currentTaskId) || null : null;
    }

    function isBusy() {
      const record = currentRecord();
      return Boolean(activeRequest || (record && !isTerminalPhase(record.phase)));
    }

    function beginRequest(input = {}) {
      if (isBusy()) return null;
      currentTaskId = null;
      earlyEvents.clear();
      const context = Object.freeze({
        requestId: `request-${++requestSequence}`,
        conversationId: String(input.conversationId || ""),
        conversationRevision: Number(input.conversationRevision || 0),
        assistantId: input.assistantId || null
      });
      activeRequest = { context, phase: "requesting" };
      return context;
    }

    function bindTask(requestId, input = {}) {
      const taskId = String(input.taskId || "");
      if (!activeRequest || activeRequest.context.requestId !== requestId || !taskId) {
        return { ok: false, context: null, events: [] };
      }
      const requestContext = activeRequest.context;
      const context = Object.freeze({
        requestId: requestContext.requestId,
        taskId,
        conversationId: String(input.conversationId || requestContext.conversationId || ""),
        conversationRevision: requestContext.conversationRevision,
        assistantId: requestContext.assistantId
      });
      const record = { context, phase: "running" };
      tasks.set(taskId, record);
      currentTaskId = taskId;
      activeRequest = null;
      const events = [...(earlyEvents.get(taskId) || [])];
      earlyEvents.clear();
      return { ok: true, context, events };
    }

    function finishRequest(requestId) {
      if (!activeRequest || activeRequest.context.requestId !== requestId) return false;
      activeRequest = null;
      earlyEvents.clear();
      return true;
    }

    function finishTask(taskId, phase = "failed") {
      const record = tasks.get(String(taskId || ""));
      if (!record || isTerminalPhase(record.phase) || !isTerminalPhase(phase)) return false;
      record.phase = phase;
      return true;
    }

    function terminalPhaseFor(event) {
      if (event.type === "cancelled") return "cancelled";
      if (event.type === "error") return "failed";
      if (event.type !== "task_completed") return null;
      const status = event.data && event.data.status;
      if (status === "completed") return "completed";
      if (status === "cancelled" || status === "stopped") return "cancelled";
      return "failed";
    }

    function routeEvent(event = {}) {
      const taskId = String(event.task_id || "");
      if (!taskId) return { disposition: "ignored", taskId: null, context: null, phase: null };
      const record = tasks.get(taskId);
      if (!record) {
        if (!activeRequest) {
          return { disposition: "ignored", taskId, context: null, phase: null };
        }
        if (!earlyEvents.has(taskId)) earlyEvents.set(taskId, []);
        earlyEvents.get(taskId).push(event);
        return { disposition: "buffered", taskId, context: null, phase: "requesting" };
      }
      if (isTerminalPhase(record.phase)) {
        return {
          disposition: "ignored",
          taskId,
          context: record.context,
          phase: record.phase,
          terminal: true
        };
      }
      const terminalPhase = terminalPhaseFor(event);
      if (terminalPhase) record.phase = terminalPhase;
      return {
        disposition: currentTaskId === taskId ? "visible" : "background",
        taskId,
        context: record.context,
        phase: record.phase,
        terminal: Boolean(terminalPhase)
      };
    }

    function beginCancel(taskId) {
      const normalizedTaskId = String(taskId || "");
      const record = tasks.get(normalizedTaskId);
      if (!record || currentTaskId !== normalizedTaskId || record.phase !== "running") return false;
      record.phase = "cancelling";
      return true;
    }

    function confirmCancel(taskId) {
      const normalizedTaskId = String(taskId || "");
      const record = tasks.get(normalizedTaskId);
      return Boolean(record && currentTaskId === normalizedTaskId && record.phase === "cancelling");
    }

    function failCancel(taskId) {
      const normalizedTaskId = String(taskId || "");
      const record = tasks.get(normalizedTaskId);
      if (!record || currentTaskId !== normalizedTaskId || record.phase !== "cancelling") return false;
      record.phase = "running";
      return true;
    }

    function getPhase() {
      if (activeRequest) return activeRequest.phase;
      const record = currentRecord();
      return record ? record.phase : "idle";
    }

    function getTaskContext(taskId) {
      const record = tasks.get(String(taskId || ""));
      return record ? record.context : null;
    }

    function getTaskPhase(taskId) {
      const record = tasks.get(String(taskId || ""));
      return record ? record.phase : null;
    }

    return {
      beginRequest,
      bindTask,
      finishRequest,
      finishTask,
      routeEvent,
      beginCancel,
      confirmCancel,
      failCancel,
      isBusy,
      isCurrentRequest: (requestId) => Boolean(activeRequest && activeRequest.context.requestId === requestId),
      isCurrentTask: (taskId) => currentTaskId === String(taskId || ""),
      isTerminalTask: (taskId) => isTerminalPhase(getTaskPhase(taskId)),
      getPhase,
      getCurrentTaskId: () => currentTaskId,
      getTaskContext,
      getTaskPhase
    };
  }

  const shell = {
    groupConversations,
    activatePage,
    setTaskPanelOpen,
    activateTaskTab,
    handleTaskTabKeydown,
    activateMemoryTab,
    handleMemoryTabKeydown,
    groupMemoryFacts,
    compactMemoryText,
    dedupeMemoryLessons,
    createMemoryOperationLifecycle,
    memoryTaskTypeLabel,
    memoryTaskStatusLabel,
    memorySkillStatusLabel,
    localizeMemoryTaskText,
    createRunLifecycle
  };
  root.UTAShell = shell;
  if (typeof module !== "undefined" && module.exports) module.exports = shell;
})(typeof window !== "undefined" ? window : globalThis);

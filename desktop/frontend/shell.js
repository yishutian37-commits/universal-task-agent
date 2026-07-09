(function bootstrapShell(window) {
  const PAGE_NAMES = new Set(["conversation", "knowledge", "memory", "capabilities"]);
  const TASK_TABS = new Set(["progress", "files", "changes", "artifacts", "diagnostics"]);

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
    document.querySelectorAll("[data-page]").forEach((page) => {
      page.classList.toggle("hidden", page.dataset.page !== nextPage);
    });
    document.querySelectorAll("[data-page-target]").forEach((button) => {
      button.classList.toggle("active", button.dataset.pageTarget === nextPage);
    });
    return nextPage;
  }

  function setTaskPanelOpen(isOpen) {
    const workspace = document.getElementById("taskView");
    const panel = document.getElementById("chatDetailPanel");
    if (!workspace || !panel) return false;
    workspace.classList.toggle("task-panel-open", Boolean(isOpen));
    panel.classList.toggle("collapsed", !isOpen);
    panel.setAttribute("aria-hidden", String(!isOpen));
    return Boolean(isOpen);
  }

  function activateTaskTab(tabName) {
    const nextTab = TASK_TABS.has(tabName) ? tabName : "progress";
    document.querySelectorAll("[data-task-tab]").forEach((button) => {
      const active = button.dataset.taskTab === nextTab;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
    });
    document.querySelectorAll("[data-task-panel]").forEach((panel) => {
      const active = panel.dataset.taskPanel === nextTab;
      panel.classList.toggle("hidden", !active);
      panel.setAttribute("aria-hidden", String(!active));
    });
    return nextTab;
  }

  window.UTAShell = {
    groupConversations,
    activatePage,
    setTaskPanelOpen,
    activateTaskTab
  };
})(window);

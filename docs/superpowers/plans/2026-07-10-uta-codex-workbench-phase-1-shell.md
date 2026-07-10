# UTA Codex 式工作台第一阶段实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不修改现有 Agent 后端行为的前提下，把 UTA 桌面端重构为“会话优先侧栏 + 中央对话 + 可折叠右侧任务面板”的 Codex 式工作台。

**Architecture:** 第一阶段继续使用现有 pywebview 桥和 `DesktopAPI`，前端仍通过 `run_chat_message`、`list_conversations`、`new_conversation`、`get_conversation`、`cancel_task` 和现有进度事件工作。新增一个无构建依赖的 `shell.js` 管理页面、会话分组和任务面板状态，`app.js` 继续负责业务调用；知识库、记忆和技能数据接口保持不变，只调整入口和页面容器。

**Tech Stack:** Python 3.11、pytest、原生 HTML/CSS/JavaScript、pywebview、macOS WKWebView。

## Global Constraints

- 所有用户可见文案使用中文。
- 普通聊天和任务执行继续共用同一个输入框。
- 会话历史不再使用独立页面，历史会话直接出现在左侧栏。
- 现有会话、记忆、知识库、技能、设置和授权 API 保持兼容。
- 当前工作区包含既有未提交改动；执行前记录基线，不回滚、不覆盖、不暂存本计划以外的文件。
- 本阶段不实现模型结构化路由、工作区读写、文件变更追踪或新事件协议。
- 输入框始终固定在对话区底部，任务开始和结束时不得改变位置。
- 原始日志和 state 只出现在右侧“诊断”标签中。
- 不加载远程字体、远程图标或新的前端依赖。
- 视觉采用中性浅色表面、深色文字、蓝色动作强调、绿色成功、红色危险，不使用渐变和发光装饰。
- 卡片圆角不超过 8px，按钮和固定面板使用稳定尺寸。
- 保留当前所有用户数据，不执行数据迁移。

---

## 文件结构

### 新增文件

- `desktop/frontend/shell.js`：页面切换、会话时间分组、任务面板展开和标签切换。
- `tests/test_desktop_workbench_shell.py`：新工作台 DOM、脚本接口和关键布局契约测试。

### 修改文件

- `desktop/frontend/index.html`：新侧栏、工作台、任务面板和二级页面入口。
- `desktop/frontend/app.js`：会话侧栏、新任务、页面路由、任务面板和停止操作接线。
- `desktop/frontend/style.css`：中性视觉系统、三栏布局、抽屉式窄屏任务面板。
- `tests/test_desktop_frontend_assets.py`：移除旧控制台和独立历史页断言，保留现有能力回归断言。

### 明确不修改

- `desktop/api.py`
- `desktop/conversation_store.py`
- `desktop/runner.py`
- `core/`
- `tools/`

---

### Task 1: 建立工作台 Shell 接口

**Files:**
- Create: `desktop/frontend/shell.js`
- Modify: `desktop/frontend/index.html:329`
- Create: `tests/test_desktop_workbench_shell.py`

**Interfaces:**
- Produces: `window.UTAShell.groupConversations(conversations, now)`
- Produces: `window.UTAShell.activatePage(pageName)`
- Produces: `window.UTAShell.setTaskPanelOpen(isOpen)`
- Produces: `window.UTAShell.activateTaskTab(tabName)`
- Consumes: DOM 元素上的 `data-page`、`data-page-target`、`data-task-tab`、`data-task-panel` 属性。

- [ ] **Step 1: 写 Shell 资源失败测试**

在 `tests/test_desktop_workbench_shell.py` 新建：

```python
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
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `.venv/bin/python -m pytest tests/test_desktop_workbench_shell.py -q`

Expected: FAIL，原因是 `desktop/frontend/shell.js` 不存在，且 `index.html` 未加载该脚本。

- [ ] **Step 3: 创建无构建依赖的 Shell**

创建 `desktop/frontend/shell.js`：

```javascript
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
      panel.classList.toggle("hidden", panel.dataset.taskPanel !== nextTab);
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
```

在 `desktop/frontend/index.html` 底部把单个脚本改为：

```html
<script src="shell.js"></script>
<script src="app.js"></script>
```

- [ ] **Step 4: 运行 Shell 测试**

Run: `.venv/bin/python -m pytest tests/test_desktop_workbench_shell.py -q`

Expected: 2 passed。

- [ ] **Step 5: 提交 Shell 基础**

```bash
git add desktop/frontend/shell.js desktop/frontend/index.html tests/test_desktop_workbench_shell.py
git commit -m "refactor: add desktop workbench shell helpers"
```

---

### Task 2: 改造成会话优先侧栏

**Files:**
- Modify: `desktop/frontend/index.html:10-47`
- Modify: `desktop/frontend/app.js:1-104, 316-503, 1197-1256`
- Modify: `tests/test_desktop_workbench_shell.py`
- Modify: `tests/test_desktop_frontend_assets.py:25-46, 303-318, 343-349`

**Interfaces:**
- Consumes: `DesktopAPI.list_conversations() -> {ok, conversations}`
- Consumes: `DesktopAPI.new_conversation() -> {ok, conversation}`
- Consumes: `DesktopAPI.get_conversation(conversation_id) -> {ok, conversation}`
- Consumes: `window.UTAShell.groupConversations(conversations, now)`
- Produces: `loadConversationSidebar()`
- Produces: `renderConversationSidebar(conversations)`
- Produces: `startNewConversation()`
- Produces: `openConversation(conversationId)`
- Produces: `showConversationView()`
- Produces: `showCapabilityPage(pageName)`

- [ ] **Step 1: 用新侧栏契约替换旧历史页测试**

在 `tests/test_desktop_workbench_shell.py` 追加：

```python
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


def test_app_loads_and_opens_conversations_from_sidebar():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'callApi("list_conversations")' in js
    assert 'callApi("new_conversation")' in js
    assert 'callApi("get_conversation", conversationId)' in js
    assert "function loadConversationSidebar" in js
    assert "function renderConversationSidebar" in js
    assert "function startNewConversation" in js
    assert "function openConversation" in js
```

在 `tests/test_desktop_frontend_assets.py`：

- 删除 `test_frontend_includes_run_history_view`。
- 删除 `test_frontend_calls_history_bridge_methods`。
- 将 `test_frontend_sidebar_nav_has_icons_without_breaking_ids` 的 ID 列表替换为 `newConversation`、`openKnowledge`、`openMemory`、`openSkills`、`openSettingsSide`。
- 将 `test_frontend_can_load_conversation_history` 改为检查 `loadConversationSidebar`、`renderConversationSidebar` 和 `openConversation`。

两个替换测试的完整内容为：

```python
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
```

- [ ] **Step 2: 运行新侧栏测试并确认失败**

Run: `.venv/bin/python -m pytest tests/test_desktop_workbench_shell.py tests/test_desktop_frontend_assets.py -q`

Expected: FAIL，旧 DOM 仍含独立会话历史页，且新函数尚不存在。

- [ ] **Step 3: 替换左侧栏 DOM**

将 `desktop/frontend/index.html` 中旧 `.titlebar` 和旧 `.sidebar` 替换为以下结构；原 `main` 内的工作区页面暂时保留：

```html
<div class="window">
  <div class="app">
    <aside class="sidebar" id="conversationSidebar">
      <div class="brandRow">
        <strong>UTA</strong>
        <span id="bridgeState">初始化</span>
      </div>
      <button class="newConversationButton" type="button" id="newConversation">
        <span aria-hidden="true">＋</span><span>新任务</span>
      </button>
      <label class="conversationSearch">
        <span class="srOnly">搜索会话</span>
        <input id="conversationSearch" type="search" placeholder="搜索会话" autocomplete="off" />
      </label>
      <div class="conversationList" id="conversationList">
        <div class="emptyState">暂无会话</div>
      </div>
      <nav class="capabilityNav" aria-label="能力页面">
        <button class="nav" type="button" id="openKnowledge" data-page-target="knowledge"><span class="navIcon" aria-hidden="true">▤</span><span>知识库</span></button>
        <button class="nav" type="button" id="openMemory" data-page-target="memory"><span class="navIcon" aria-hidden="true">◇</span><span>记忆中心</span></button>
        <button class="nav" type="button" id="openSkills" data-page-target="capabilities"><span class="navIcon" aria-hidden="true">⚡</span><span>技能与工具</span></button>
      </nav>
      <div class="sidebarFooter">
        <button class="nav" type="button" id="openSettingsSide"><span class="navIcon" aria-hidden="true">⚙</span><span>设置与授权</span></button>
        <button class="authStatus" type="button" id="dangerousToolsStatus">工具授权：关闭</button>
        <span id="keyState">Key：未配置</span>
      </div>
    </aside>
```

从 `index.html` 删除整个 `historyView`。保留 `taskView`、`memoryView`、`knowledgeView`、`skillsView` 及所有数据节点，并完成以下属性调整：

```html
<h2 id="conversationTitle">新任务</h2>
<section class="workspace chatWorkspace" id="taskView" data-page="conversation">
<section class="workspace memoryWorkspace hidden" id="memoryView" data-page="memory">
<section class="workspace memoryWorkspace hidden" id="knowledgeView" data-page="knowledge">
<section class="workspace memoryWorkspace hidden" id="skillsView" data-page="capabilities">
```

- [ ] **Step 4: 接入侧栏会话逻辑**

在 `desktop/frontend/app.js` 的 `els` 中删除旧历史节点，增加：

```javascript
newConversation: document.getElementById("newConversation"),
conversationSearch: document.getElementById("conversationSearch"),
conversationList: document.getElementById("conversationList"),
conversationTitle: document.getElementById("conversationTitle"),
```

在 `state` 中增加：

```javascript
conversations: [],
activePage: "conversation",
taskPanelOpen: false,
taskPanelTab: "progress",
```

删除 `openTaskView`、`openHistory`、`refreshHistory` 和所有 `history*` DOM 引用；删除 `loadHistoryRuns`、`renderHistoryList`、`selectHistoryRun`、`renderEmptyHistoryDetail`、`showHistoryView` 和 `renderEmptyConversationDetail`。用以下函数替换旧页面切换、`renderConversationList` 和 `selectConversation`：

```javascript
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
    const rows = items.map((conversation) => `
      <button class="conversationItem" type="button" data-conversation-id="${escapeHtml(conversation.conversation_id)}">
        <strong>${escapeHtml(conversation.title || "新对话")}</strong>
        <small>${escapeHtml(conversation.preview || "暂无消息")}</small>
      </button>
    `).join("");
    return `<section class="conversationGroup"><h2>${label}</h2>${rows}</section>`;
  }).join("");
  els.conversationList.innerHTML = html || '<div class="emptyState">暂无匹配会话</div>';
  els.conversationList.querySelectorAll("[data-conversation-id]").forEach((button) => {
    button.addEventListener("click", () => openConversation(button.dataset.conversationId));
  });
}

async function startNewConversation() {
  if (state.running) {
    showToast("任务运行中", "请先停止当前任务");
    return;
  }
  const result = await callApi("new_conversation");
  if (!result.ok) {
    showToast("新建失败", result.error || "未知错误");
    return;
  }
  state.conversationId = result.conversation.conversation_id;
  state.messages = [];
  state.pendingAssistantId = null;
  els.conversationTitle.textContent = "新任务";
  resetRunSurface();
  showConversationView();
  renderChatMessages();
  await loadConversationSidebar();
  els.taskInput.focus();
}

async function openConversation(conversationId) {
  if (state.running) {
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
```

绑定事件：

```javascript
els.newConversation.addEventListener("click", startNewConversation);
els.conversationSearch.addEventListener("input", () => renderConversationSidebar(state.conversations));
els.openKnowledge.addEventListener("click", () => showCapabilityPage("knowledge"));
els.openMemory.addEventListener("click", () => showCapabilityPage("memory"));
els.openSkills.addEventListener("click", () => showCapabilityPage("capabilities"));
```

删除旧 `openTaskView`、`openHistory` 和 `refreshHistory` 的事件绑定。设置弹窗仍由 `openSettingsSide` 和 `dangerousToolsStatus` 打开。

将启动过程改为：

```javascript
async function initializeDesktop() {
  await loadSettings();
  await loadConversationSidebar();
}

window.addEventListener("pywebviewready", initializeDesktop);
setTimeout(() => { if (api()) initializeDesktop(); }, 500);
```

- [ ] **Step 5: 运行侧栏和现有会话测试**

Run: `.venv/bin/python -m pytest tests/test_desktop_workbench_shell.py tests/test_desktop_frontend_assets.py tests/test_desktop_api.py tests/test_desktop_conversation_store.py -q`

Expected: PASS。

- [ ] **Step 6: 提交会话优先侧栏**

```bash
git add desktop/frontend/index.html desktop/frontend/app.js tests/test_desktop_workbench_shell.py tests/test_desktop_frontend_assets.py
git commit -m "feat: move desktop conversations into sidebar"
```

---

### Task 3: 建立中央对话与右侧任务面板

**Files:**
- Modify: `desktop/frontend/index.html:34-100`
- Modify: `desktop/frontend/app.js:1-104, 845-1135, 1197-1248`
- Modify: `tests/test_desktop_workbench_shell.py`
- Modify: `tests/test_desktop_frontend_assets.py:15-23, 185-249, 262-286`

**Interfaces:**
- Consumes: `window.UTAShell.setTaskPanelOpen(isOpen)`
- Consumes: `window.UTAShell.activateTaskTab(tabName)`
- Consumes: 现有 `window.onProgress(event)` 事件。
- Produces: `setTaskPanelOpen(isOpen)`
- Produces: `setTaskPanelTab(tabName)`
- Produces: `renderTaskPanelEmptyStates()`

- [ ] **Step 1: 写任务面板失败测试**

在 `tests/test_desktop_workbench_shell.py` 追加：

```python
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
```

替换 `tests/test_desktop_frontend_assets.py` 中依赖旧双卡片布局的测试：

- `test_frontend_keeps_plan_and_logs_in_separate_scroll_regions` 改为检查任务面板五个标签。
- `test_frontend_shows_progress_inside_assistant_message` 改为检查 `messageProgress` 不再存在、步骤仍渲染到 `planList`。
- 删除旧 `test_frontend_chat_layout_keeps_messages_above_bottom_composer`；新的稳定布局断言在 Task 5 与 CSS 一起加入。

两个替换测试的完整内容为：

```python
def test_frontend_keeps_task_details_in_tabbed_panel():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    for name in ["progress", "files", "changes", "artifacts", "diagnostics"]:
        assert f'data-task-tab="{name}"' in html
        assert f'data-task-panel="{name}"' in html


def test_frontend_keeps_execution_progress_out_of_assistant_messages():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert "function renderMessageProgress" not in js
    assert "function renderPlan" in js
    assert "function markStep" in js
    assert "els.taskActivity.textContent = line" in js
```

- [ ] **Step 2: 运行任务面板测试并确认失败**

Run: `.venv/bin/python -m pytest tests/test_desktop_workbench_shell.py tests/test_desktop_frontend_assets.py -q`

Expected: FAIL，右侧仍是“执行详情 + 实时日志 + state.json”三块堆叠结构。

- [ ] **Step 3: 替换工作台 DOM**

将 `taskView` 改为：

```html
<section class="workspace chatWorkspace" id="taskView" data-page="conversation">
  <section class="conversationSurface">
    <header class="conversationHeader">
      <div>
        <h1 id="conversationTitle">新任务</h1>
        <button class="workspaceSelector" type="button" id="workspaceSelector" disabled title="无工作区">无工作区</button>
      </div>
      <div class="headActions">
        <span class="status ready" id="statusPill"><i></i><span id="statusText">就绪</span></span>
        <button class="iconButton" type="button" id="toggleTaskPanel" title="任务详情" aria-label="任务详情">▥</button>
      </div>
    </header>
    <div class="chatMessages" id="chatMessages"></div>
    <article class="report empty hidden" id="report">等待任务运行</article>
    <div class="chatComposer">
      <textarea id="taskInput" spellcheck="false" rows="3" placeholder="继续提问或安排下一项任务"></textarea>
      <div class="composerToolbar">
        <div>
          <button class="iconButton" type="button" id="loadExample" title="载入示例" aria-label="载入示例">＋</button>
          <button class="iconButton" type="button" id="clearTask" title="清空输入" aria-label="清空输入">×</button>
        </div>
        <div>
          <button class="button secondary hidden" type="button" id="stopTask">停止</button>
          <button class="button primary" type="button" id="runTask">发送</button>
        </div>
      </div>
    </div>
  </section>

  <aside class="taskPanel collapsed" id="chatDetailPanel" aria-hidden="true">
    <header class="taskPanelHeader">
      <div><h2>本轮任务</h2><span id="taskIdLabel">未运行</span></div>
      <div>
        <button class="button ghost compact" type="button" id="resumeTask">继续</button>
        <button class="iconButton" type="button" id="closeTaskPanel" title="收起任务详情" aria-label="收起任务详情">×</button>
      </div>
    </header>
    <div class="taskTabs" role="tablist" aria-label="任务详情">
      <button class="active" type="button" data-task-tab="progress" role="tab">进度</button>
      <button type="button" data-task-tab="files" role="tab">文件</button>
      <button type="button" data-task-tab="changes" role="tab">变更</button>
      <button type="button" data-task-tab="artifacts" role="tab">产物</button>
      <button type="button" data-task-tab="diagnostics" role="tab">诊断</button>
    </div>
    <section class="taskPanelBody" data-task-panel="progress">
      <div class="taskPanelMeta"><strong>执行进度</strong><span id="planMeta">0 步</span></div>
      <p class="taskActivity" id="taskActivity">尚未开始</p>
      <div class="steps" id="planList"></div>
    </section>
    <section class="taskPanelBody hidden" data-task-panel="files"><div class="emptyState">本轮暂无文件记录</div></section>
    <section class="taskPanelBody hidden" data-task-panel="changes"><div class="emptyState">本轮暂无文件变更</div></section>
    <section class="taskPanelBody hidden" data-task-panel="artifacts"><div class="emptyState">本轮暂无独立产物</div></section>
    <section class="taskPanelBody diagnosticsPanel hidden" data-task-panel="diagnostics">
      <div class="diagnosticBlock"><div class="taskPanelMeta"><strong>实时日志</strong><button class="button ghost compact" type="button" id="clearLogs">清空</button></div><div class="logs" id="logPanel"></div></div>
      <details class="stateBox"><summary>运行状态 <button class="button secondary compact" type="button" id="copyReport" disabled>复制结果</button></summary><pre id="stateJson">{"status":"idle","task_id":null}</pre></details>
    </section>
  </aside>
</section>
```

- [ ] **Step 4: 接入任务面板状态和标签**

在 `els` 增加 `toggleTaskPanel`、`closeTaskPanel`、`stopTask`、`taskActivity`，删除已从 DOM 移除的 `openSettings`。增加：

```javascript
function setTaskPanelOpen(isOpen) {
  state.taskPanelOpen = window.UTAShell.setTaskPanelOpen(isOpen);
}

function setTaskPanelTab(tabName) {
  state.taskPanelTab = window.UTAShell.activateTaskTab(tabName);
}

function renderTaskPanelEmptyStates() {
  els.chatDetailPanel.classList.toggle("has-task", Boolean(state.taskId));
}
```

绑定：

```javascript
els.toggleTaskPanel.addEventListener("click", () => setTaskPanelOpen(!state.taskPanelOpen));
els.closeTaskPanel.addEventListener("click", () => setTaskPanelOpen(false));
document.querySelectorAll("[data-task-tab]").forEach((button) => {
  button.addEventListener("click", () => setTaskPanelTab(button.dataset.taskTab));
});
```

在任务返回 `task_id` 后调用：

```javascript
setTaskPanelTab("progress");
setTaskPanelOpen(true);
renderTaskPanelEmptyStates();
```

普通 `result.direct` 分支不得自动展开任务面板。

- [ ] **Step 5: 把进度从聊天气泡移到任务面板**

删除 `renderMessageProgress` 以及 `renderChatMessages` 中对应调用。保留 `appendAssistantProgress` 函数名作为兼容入口，把最新活动写入右侧进度面板；原始事件日志仍由 `handleProgress` 开头的 `addLog` 负责，避免重复日志：

```javascript
function appendAssistantProgress(taskId, line) {
  if (!taskId || !line) return;
  els.taskActivity.textContent = line;
}
```

`handleProgress` 继续使用 `renderPlan`、`markStep` 和 `addLog`。`task_completed` 只把最终结果写入助手消息，步骤与日志继续留在右侧面板。

将旧 `els.openSettings.addEventListener("click", openSettings)` 删除，仅保留侧栏设置入口和工具授权入口，避免已删除节点触发空引用。

- [ ] **Step 6: 运行工作台测试**

Run: `.venv/bin/python -m pytest tests/test_desktop_workbench_shell.py tests/test_desktop_frontend_assets.py -q`

Expected: PASS。

- [ ] **Step 7: 提交工作台结构**

```bash
git add desktop/frontend/index.html desktop/frontend/app.js tests/test_desktop_workbench_shell.py tests/test_desktop_frontend_assets.py
git commit -m "feat: add contextual desktop task panel"
```

---

### Task 4: 接入停止任务并整理二级能力页面

**Files:**
- Modify: `desktop/frontend/index.html:139-264`
- Modify: `desktop/frontend/app.js:316-381, 649-843, 858-955, 1197-1256`
- Modify: `tests/test_desktop_workbench_shell.py`
- Modify: `tests/test_desktop_frontend_assets.py`

**Interfaces:**
- Consumes: `DesktopAPI.cancel_task(task_id) -> {ok, status}`
- Consumes: Task 2 产生的 `showCapabilityPage(pageName)`
- Produces: `stopTask()`

- [ ] **Step 1: 写停止按钮和二级页面标题失败测试**

在 `tests/test_desktop_workbench_shell.py` 追加：

```python
def test_secondary_pages_have_clear_titles():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    assert '<h1>知识库</h1>' in html
    assert '<h1>记忆中心</h1>' in html
    assert '<h1>技能与工具</h1>' in html


def test_running_task_can_be_stopped_from_composer():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'id="stopTask"' in html
    assert "function stopTask" in js
    assert 'callApi("cancel_task", state.taskId)' in js
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `.venv/bin/python -m pytest tests/test_desktop_workbench_shell.py -q`

Expected: FAIL，二级页面没有统一标题，且没有停止按钮逻辑。

- [ ] **Step 3: 整理二级页面标题**

在三个二级页面容器的首部增加稳定页面标题，并保留其内部现有功能节点：

```html
<header class="pageHeader"><h1>知识库</h1></header>
<header class="pageHeader"><h1>记忆中心</h1></header>
<header class="pageHeader"><h1>技能与工具</h1></header>
```

- [ ] **Step 4: 接入停止任务**

新增：

```javascript
async function stopTask() {
  if (!state.running || !state.taskId) return;
  els.stopTask.disabled = true;
  try {
    const result = await callApi("cancel_task", state.taskId);
    if (!result.ok) {
      showToast("停止失败", result.error || "未知错误");
      return;
    }
    setStatus("running", "正在停止");
    addLog("Task", "已请求停止，等待当前步骤结束");
  } catch (error) {
    showToast("停止失败", error.message);
  } finally {
    els.stopTask.disabled = false;
  }
}
```

在 `runTask` 开始执行任务后显示停止按钮，在 `task_completed` 和 `error` 时隐藏：

```javascript
els.stopTask.classList.toggle("hidden", !state.running);
```

绑定：

```javascript
els.stopTask.addEventListener("click", stopTask);
```

- [ ] **Step 5: 运行前端与取消任务回归测试**

Run: `.venv/bin/python -m pytest tests/test_desktop_workbench_shell.py tests/test_desktop_frontend_assets.py tests/test_desktop_api.py tests/test_runner.py -q`

Expected: PASS。

- [ ] **Step 6: 提交页面和停止操作**

```bash
git add desktop/frontend/index.html desktop/frontend/app.js tests/test_desktop_workbench_shell.py tests/test_desktop_frontend_assets.py
git commit -m "feat: wire workbench navigation and task stop"
```

---

### Task 5: 应用中性视觉系统和响应式布局

**Files:**
- Modify: `desktop/frontend/style.css:1-1256`
- Modify: `tests/test_desktop_workbench_shell.py`
- Modify: `tests/test_desktop_frontend_assets.py:289-300, 332-340`

**Interfaces:**
- Consumes: Task 2-4 产生的 DOM 类名。
- Produces: 1280px 以上固定三栏布局。
- Produces: 761px-1179px 右侧任务抽屉。
- Produces: 760px 及以下可折叠会话侧栏和全宽对话区。

- [ ] **Step 1: 写视觉和布局失败测试**

在 `tests/test_desktop_workbench_shell.py` 追加：

```python
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
```

将 `tests/test_desktop_frontend_assets.py::test_frontend_uses_dark_command_deck_theme_without_remote_fonts` 替换为：

```python
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
```

保留所有记忆卡片不裁切的回归断言，只更新已经不存在的旧布局类名。

- [ ] **Step 2: 运行视觉契约测试并确认失败**

Run: `.venv/bin/python -m pytest tests/test_desktop_workbench_shell.py tests/test_desktop_frontend_assets.py -q`

Expected: FAIL，当前仍是深色渐变“命令甲板”主题和旧两栏布局。

- [ ] **Step 3: 重写视觉 token 和应用外壳**

用以下 token 替换旧 `:root`：

```css
:root {
  --app-bg: #f5f5f3;
  --sidebar-bg: #ecece8;
  --panel-bg: #ffffff;
  --panel-subtle: #f8f8f6;
  --text: #1d1d1b;
  --muted: #6f6f69;
  --faint: #969690;
  --border: #d9d9d4;
  --border-strong: #bdbdb6;
  --action: #2f64d6;
  --action-soft: #e8efff;
  --success: #238052;
  --danger: #b42318;
  --warning: #9a5b13;
  --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --bg: var(--app-bg);
  --surface: var(--panel-bg);
  --surface-0: var(--sidebar-bg);
  --surface-1: var(--panel-bg);
  --surface-2: var(--panel-subtle);
  --surface-3: #eeeeea;
  --text-3: var(--faint);
  --border-2: var(--border-strong);
  --accent: var(--action);
  --accent-dark: #2556bd;
  --accent-glow: var(--action-soft);
  --accent-glow-2: #cfdbf7;
  --cyan: #157a7a;
  --warn: var(--warning);
  --r-sm: var(--radius-sm);
  --r-md: var(--radius-md);
  --r-lg: var(--radius-lg);
  --r-pill: 999px;
}
```

建立稳定外壳：

```css
.window { height: 100%; }
.app { height: 100%; min-height: 0; display: grid; grid-template-columns: 260px minmax(0, 1fr); }
.sidebar { min-height: 0; display: flex; flex-direction: column; background: var(--sidebar-bg); border-right: 1px solid var(--border); }
.main { min-width: 0; min-height: 0; height: 100%; background: var(--panel-bg); }
.chatWorkspace { position: relative; height: 100%; min-height: 0; padding: 0; display: grid; grid-template-columns: minmax(0, 1fr); overflow: hidden; }
.chatWorkspace.task-panel-open { grid-template-columns: minmax(0, 1fr) 340px; }
.conversationSurface { min-width: 0; min-height: 0; display: grid; grid-template-rows: auto minmax(0, 1fr) auto; background: var(--panel-bg); }
.chatMessages { min-height: 0; overflow-y: auto; padding: 24px max(24px, calc((100% - 820px) / 2)); }
.chatComposer { width: min(820px, calc(100% - 48px)); margin: 0 auto 20px; border: 1px solid var(--border-strong); border-radius: var(--radius-lg); background: var(--panel-bg); }
.taskPanel { min-width: 0; min-height: 0; border-left: 1px solid var(--border); background: var(--panel-subtle); }
.taskPanel.collapsed { display: none; }
.brandRow,
.conversationHeader,
.taskPanelHeader,
.taskPanelMeta,
.composerToolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.brandRow { min-height: 52px; padding: 0 14px; }
.brandRow strong { font-size: 18px; }
.brandRow span,
.sidebarFooter > span { color: var(--muted); font-size: 11px; }
.newConversationButton { min-height: 38px; margin: 0 12px 10px; padding: 0 11px; display: flex; align-items: center; gap: 8px; border-radius: var(--radius-md); background: #242422; color: #ffffff; }
.conversationSearch { padding: 0 12px 10px; }
.conversationSearch input { width: 100%; height: 34px; padding: 0 10px; border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--panel-subtle); color: var(--text); }
.conversationList { min-height: 0; flex: 1; overflow-y: auto; padding: 0 8px; }
.conversationGroup h2 { margin: 13px 8px 5px; color: var(--faint); font-size: 11px; font-weight: 600; }
.conversationItem { width: 100%; min-width: 0; padding: 8px; display: grid; gap: 2px; border-radius: var(--radius-md); text-align: left; }
.conversationItem:hover,
.conversationItem.active { background: #deded9; }
.conversationItem strong,
.conversationItem small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.conversationItem strong { font-size: 12px; }
.conversationItem small { color: var(--muted); font-size: 11px; }
.capabilityNav { padding: 8px; border-top: 1px solid var(--border); display: grid; gap: 2px; }
.nav { width: 100%; min-height: 34px; padding: 6px 8px; display: flex; align-items: center; gap: 8px; border-radius: var(--radius-md); color: var(--muted); text-align: left; }
.nav:hover,
.nav.active { background: #deded9; color: var(--text); }
.navIcon { width: 18px; flex: 0 0 18px; text-align: center; }
.sidebarFooter { margin-top: 0; padding: 8px; border-top: 1px solid var(--border); display: grid; gap: 4px; }
.conversationHeader { min-height: 64px; padding: 10px 18px; border-bottom: 1px solid var(--border); }
.conversationHeader h1,
.pageHeader h1,
.taskPanelHeader h2 { margin: 0; font-size: 16px; letter-spacing: 0; }
.workspaceSelector { margin-top: 3px; padding: 0; color: var(--muted); font-size: 11px; }
.messageBubble { max-width: min(760px, 88%); padding: 10px 12px; border: 0; border-radius: var(--radius-lg); background: transparent; overflow-wrap: anywhere; }
.chatMessage.user .messageBubble { color: var(--text); background: #eeeeea; box-shadow: none; }
.chatMessage.assistant .messageBubble,
.chatMessage.system .messageBubble { border-left: 0; background: transparent; }
.chatComposer textarea { width: 100%; min-height: 64px; max-height: 160px; margin: 0; padding: 12px; border: 0; resize: vertical; background: transparent; color: var(--text); }
.composerToolbar { padding: 0 8px 8px; }
.composerToolbar > div { display: flex; align-items: center; gap: 6px; }
.iconButton { width: 32px; height: 32px; display: inline-grid; place-items: center; border-radius: var(--radius-md); color: var(--muted); }
.iconButton:hover { background: var(--panel-subtle); color: var(--text); }
.taskPanel { display: grid; grid-template-rows: auto auto minmax(0, 1fr); overflow: hidden; }
.taskPanelHeader { min-height: 58px; padding: 10px 12px; border-bottom: 1px solid var(--border); }
.taskPanelHeader > div { display: flex; align-items: center; gap: 6px; }
.taskPanelHeader span { color: var(--muted); font-family: var(--mono); font-size: 10px; }
.taskTabs { padding: 0 8px; display: flex; gap: 2px; overflow-x: auto; border-bottom: 1px solid var(--border); }
.taskTabs button { min-height: 38px; padding: 0 7px; color: var(--muted); font-size: 11px; border-bottom: 2px solid transparent; }
.taskTabs button.active { color: var(--text); border-bottom-color: var(--text); }
.taskPanelBody { min-height: 0; overflow-y: auto; padding: 12px; }
.taskActivity { margin: 8px 0 12px; color: var(--muted); font-size: 12px; }
.diagnosticsPanel { display: grid; align-content: start; gap: 12px; }
.pageHeader { min-height: 64px; padding: 18px 20px; border-bottom: 1px solid var(--border); }
.srOnly { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
```

删除旧 `.titlebar::after`、`.brand h1` 和 `.chatMessage.user .messageBubble` 中的全部渐变声明，确保 CSS 中不再出现 `linear-gradient`。未在上方覆盖的记忆、知识库、技能、设置、授权和 Markdown 渲染规则继续保留，并通过兼容 token 自动切换到新配色。

- [ ] **Step 4: 增加窄窗口任务抽屉**

追加：

```css
@media (max-width: 1179px) {
  .chatWorkspace,
  .chatWorkspace.task-panel-open { grid-template-columns: minmax(0, 1fr); }
  .taskPanel {
    position: absolute;
    z-index: 20;
    top: 0;
    right: 0;
    bottom: 0;
    width: min(380px, calc(100% - 48px));
    box-shadow: -12px 0 28px rgba(30, 30, 28, 0.12);
  }
}

@media (max-width: 760px) {
  .app { grid-template-columns: 72px minmax(0, 1fr); }
  .sidebar .conversationSearch,
  .sidebar .conversationList,
  .sidebar .nav span:not(.navIcon),
  .newConversationButton span:last-child,
  .sidebarFooter > span { display: none; }
  .newConversationButton { width: 40px; min-width: 40px; margin-inline: auto; }
  .chatMessages { padding-inline: 16px; }
  .chatComposer { width: calc(100% - 24px); margin-bottom: 12px; }
}
```

- [ ] **Step 5: 运行前端测试**

Run: `.venv/bin/python -m pytest tests/test_desktop_workbench_shell.py tests/test_desktop_frontend_assets.py tests/test_desktop_frontend.py -q`

Expected: PASS。

- [ ] **Step 6: 提交视觉系统**

```bash
git add desktop/frontend/style.css tests/test_desktop_workbench_shell.py tests/test_desktop_frontend_assets.py
git commit -m "style: apply neutral Codex workbench layout"
```

---

### Task 6: 全量回归、浏览器视觉检查和阶段验收

**Files:**
- Modify only if verification finds a defect: `desktop/frontend/index.html`
- Modify only if verification finds a defect: `desktop/frontend/app.js`
- Modify only if verification finds a defect: `desktop/frontend/style.css`
- Modify only if verification finds a defect: `tests/test_desktop_workbench_shell.py`

**Interfaces:**
- Consumes: 第一阶段全部前端成果。
- Produces: 可进入第二阶段的稳定工作台骨架。

- [ ] **Step 1: 运行前端和桌面桥定向测试**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_desktop_workbench_shell.py \
  tests/test_desktop_frontend_assets.py \
  tests/test_desktop_frontend.py \
  tests/test_desktop_api.py \
  tests/test_desktop_conversation_store.py \
  tests/test_runner.py -q
```

Expected: 全部通过。

- [ ] **Step 2: 运行全量测试**

Run: `.venv/bin/python -m pytest -q`

Expected: 全部通过；现有环境标记为 deselected 的测试数量不增加。

- [ ] **Step 3: 启动静态预览并检查桌面宽度**

Run: `.venv/bin/python -m http.server 8765 --directory desktop/frontend`

使用应用内浏览器打开 `http://localhost:8765/`，分别检查：

- 1440 × 900：侧栏、对话、展开任务面板均完整可见。
- 1024 × 768：任务面板为右侧抽屉，不压缩输入框。
- 760 × 900：侧栏收窄，对话正文和按钮无重叠。

Expected: 页面非空；输入框固定底部；任务面板关闭时中央对话占满；所有文字没有被裁切。

完成三种宽度检查后向该终端会话发送 `Ctrl-C`，确认静态服务器已经退出。

- [ ] **Step 4: 检查关键交互**

在开发版桌面应用中验证：

1. 新建任务后左侧立即出现新会话。
2. 点击历史会话回到中央对话，不进入独立历史页。
3. 普通直接回复不自动展开任务面板。
4. 执行任务后任务面板自动展开到“进度”。
5. “停止”调用现有取消接口并进入正在停止状态。
6. “诊断”中可以查看日志和 state，主消息中没有步骤日志。
7. 知识库、记忆中心、技能与工具、设置与授权仍可打开。
8. 授权弹窗仍可批准或拒绝高风险操作。

Expected: 8 项全部通过。

- [ ] **Step 5: 检查改动范围**

Run: `git status --short`

Expected: 与执行前记录的基线相比，只新增本计划列出的前端和测试文件改动；既有未提交改动保持原样，没有被回滚或误暂存。

- [ ] **Step 6: 提交验证中发现的修复**

仅当 Step 1-5 产生修复时执行：

```bash
git add desktop/frontend/index.html desktop/frontend/app.js desktop/frontend/style.css desktop/frontend/shell.js tests/test_desktop_workbench_shell.py tests/test_desktop_frontend_assets.py tests/test_desktop_frontend.py
git commit -m "fix: finish Codex workbench shell verification"
```

如果没有产生修复，不创建空提交。

---

## 阶段完成定义

第一阶段只有同时满足以下条件才算完成：

- 首页是会话优先侧栏、中央对话和可折叠右侧任务面板。
- 独立会话历史页已移除，历史会话可直接恢复到对话工作台。
- 普通聊天不会显示任务执行细节。
- 任务步骤、日志和 state 只在右侧任务面板中出现。
- 停止按钮可调用现有取消能力。
- 知识库、记忆、技能、设置和授权功能没有回归。
- 定向测试和全量测试通过。
- 1440、1024 和 760 三种宽度的视觉检查通过。

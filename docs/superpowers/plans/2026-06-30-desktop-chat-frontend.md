# Desktop Chat Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 UTA Desktop 的主任务页升级为“聊天主界面 + 执行详情侧栏”，并保留现有 Agent 后端能力。

**Architecture:** 保持 pywebview 单进程架构，前端仍通过 `window.pywebview.api` 调 Python 后端。后端新增轻量 `ConversationStore` 保存本地会话消息，`DesktopAPI` 新增对话方法，但任务执行仍复用 `TaskRunner.start()` 和 `main.run_task()`。前端在现有 `desktop/frontend/app.js` 上增量改造，先不引入打包器和新框架。

**Tech Stack:** Python 3.12, pytest, pywebview bridge, vanilla HTML/CSS/JavaScript, JSON file storage under `~/.uta/conversations/`.

---

## File Structure

- Create: `desktop/conversation_store.py`
  - 负责本地会话 JSON 的创建、读取、追加消息、更新 assistant 消息和列表摘要。
- Create: `tests/test_desktop_conversation_store.py`
  - 覆盖会话存储的核心行为和坏文件容错。
- Modify: `desktop/api.py`
  - 注入 `ConversationStore`，新增 `new_conversation()`、`list_conversations()`、`get_conversation()`、`run_chat_message()`、`sync_chat_result()`。
- Modify: `tests/test_desktop_api.py`
  - 覆盖对话 API、无 Key 拒绝、同步任务结果写回 assistant 消息。
- Modify: `desktop/frontend/index.html`
  - 把任务页改成聊天区和详情区；保留运行记录、记忆、知识库、技能包页面。
- Modify: `desktop/frontend/app.js`
  - 新增聊天消息状态、发送消息、根据进度事件更新 assistant 消息和详情侧栏。
- Modify: `desktop/frontend/style.css`
  - 新增聊天布局、消息气泡、底部输入区、详情侧栏样式。
- Modify: `tests/test_desktop_frontend_assets.py`
  - 覆盖聊天 DOM、桥接方法、进度更新、Markdown 渲染仍存在。
- Modify: `desktop/README.md`, `README.md`, `CHANGELOG.md`, `docs/project-overview.md`
  - 记录桌面端对话前端能力。

## Task 1: Conversation Store

**Files:**
- Create: `tests/test_desktop_conversation_store.py`
- Create: `desktop/conversation_store.py`

- [ ] **Step 1: Write failing store tests**

Create `tests/test_desktop_conversation_store.py`:

```python
import json
import re

from desktop.conversation_store import ConversationStore


def test_conversation_store_creates_and_reads_conversation(tmp_path):
    store = ConversationStore(tmp_path)

    created = store.new_conversation(title="第一次对话")
    conversation_id = created["conversation"]["conversation_id"]
    loaded = store.get_conversation(conversation_id)

    assert created["ok"] is True
    assert re.match(r"conv_\d{8}_\d{6}_\d{6}", conversation_id)
    assert loaded["ok"] is True
    assert loaded["conversation"]["title"] == "第一次对话"
    assert loaded["conversation"]["messages"] == []


def test_conversation_store_appends_user_and_assistant_messages(tmp_path):
    store = ConversationStore(tmp_path)
    conversation_id = store.new_conversation()["conversation"]["conversation_id"]

    user = store.append_message(
        conversation_id,
        role="user",
        content="帮我总结这篇文章",
        task_id="task_1",
        status="completed",
    )
    assistant = store.append_message(
        conversation_id,
        role="assistant",
        content="正在处理...",
        task_id="task_1",
        status="running",
    )
    loaded = store.get_conversation(conversation_id)

    assert user["ok"] is True
    assert assistant["ok"] is True
    assert [m["role"] for m in loaded["conversation"]["messages"]] == ["user", "assistant"]
    assert loaded["conversation"]["messages"][0]["content"] == "帮我总结这篇文章"
    assert loaded["conversation"]["messages"][1]["status"] == "running"


def test_conversation_store_updates_assistant_message_by_task_id(tmp_path):
    store = ConversationStore(tmp_path)
    conversation_id = store.new_conversation()["conversation"]["conversation_id"]
    store.append_message(conversation_id, role="user", content="任务", task_id="task_1")
    store.append_message(conversation_id, role="assistant", content="正在处理...", task_id="task_1", status="running")

    updated = store.update_assistant_message(
        conversation_id,
        task_id="task_1",
        content="## 摘要\n完成",
        status="completed",
    )
    loaded = store.get_conversation(conversation_id)

    assert updated["ok"] is True
    assistant = loaded["conversation"]["messages"][1]
    assert assistant["content"] == "## 摘要\n完成"
    assert assistant["status"] == "completed"


def test_conversation_store_lists_newest_first_and_skips_bad_json(tmp_path):
    store = ConversationStore(tmp_path)
    first = store.new_conversation(title="旧会话")["conversation"]["conversation_id"]
    second = store.new_conversation(title="新会话")["conversation"]["conversation_id"]
    (tmp_path / "conv_bad.json").write_text("{bad json", encoding="utf-8")

    listed = store.list_conversations()

    assert listed["ok"] is True
    ids = [item["conversation_id"] for item in listed["conversations"]]
    assert ids[0] == second
    assert first in ids
    assert "conv_bad" not in ids


def test_conversation_store_rejects_unsafe_ids(tmp_path):
    store = ConversationStore(tmp_path)

    result = store.get_conversation("../secret")

    assert result == {"ok": False, "error": "会话不存在"}
```

- [ ] **Step 2: Run store tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_desktop_conversation_store.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'desktop.conversation_store'`.

- [ ] **Step 3: Implement ConversationStore**

Create `desktop/conversation_store.py`:

```python
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


class ConversationStore:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def new_conversation(self, title: str | None = None) -> dict[str, Any]:
        now = _now()
        conversation = {
            "conversation_id": _conversation_id(),
            "title": title or "新对话",
            "created_at": now,
            "updated_at": now,
            "messages": [],
        }
        self._write(conversation)
        return {"ok": True, "conversation": conversation}

    def list_conversations(self) -> dict[str, Any]:
        items = []
        for path in self.root.glob("conv_*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(data, dict):
                continue
            conversation_id = str(data.get("conversation_id") or "")
            if not _is_safe_id(conversation_id):
                continue
            messages = data.get("messages") if isinstance(data.get("messages"), list) else []
            preview = ""
            if messages:
                preview = str(messages[-1].get("content") or "")[:120]
            items.append(
                {
                    "conversation_id": conversation_id,
                    "title": str(data.get("title") or "新对话"),
                    "updated_at": str(data.get("updated_at") or ""),
                    "message_count": len(messages),
                    "preview": preview,
                }
            )
        items.sort(key=lambda item: item["updated_at"], reverse=True)
        return {"ok": True, "conversations": items}

    def get_conversation(self, conversation_id: str) -> dict[str, Any]:
        path = self._path_for(conversation_id)
        if path is None or not path.exists() or path.is_symlink():
            return {"ok": False, "error": "会话不存在"}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {"ok": False, "error": "会话 JSON 无效"}
        if not isinstance(data, dict):
            return {"ok": False, "error": "会话 JSON 无效"}
        return {"ok": True, "conversation": data}

    def append_message(
        self,
        conversation_id: str,
        *,
        role: str,
        content: str,
        task_id: str | None = None,
        status: str = "completed",
    ) -> dict[str, Any]:
        loaded = self.get_conversation(conversation_id)
        if not loaded.get("ok"):
            return loaded
        conversation = loaded["conversation"]
        message = {
            "role": role,
            "content": content,
            "task_id": task_id,
            "status": status,
            "created_at": _now(),
        }
        conversation.setdefault("messages", []).append(message)
        conversation["updated_at"] = message["created_at"]
        if role == "user" and len(conversation["messages"]) == 1:
            conversation["title"] = content[:30] or conversation.get("title") or "新对话"
        self._write(conversation)
        return {"ok": True, "message": message, "conversation": conversation}

    def update_assistant_message(
        self,
        conversation_id: str,
        *,
        task_id: str,
        content: str,
        status: str,
    ) -> dict[str, Any]:
        loaded = self.get_conversation(conversation_id)
        if not loaded.get("ok"):
            return loaded
        conversation = loaded["conversation"]
        messages = conversation.get("messages") if isinstance(conversation.get("messages"), list) else []
        for message in reversed(messages):
            if message.get("role") == "assistant" and message.get("task_id") == task_id:
                message["content"] = content
                message["status"] = status
                message["updated_at"] = _now()
                conversation["updated_at"] = message["updated_at"]
                self._write(conversation)
                return {"ok": True, "message": message, "conversation": conversation}
        return {"ok": False, "error": "助手消息不存在"}

    def _path_for(self, conversation_id: str) -> Path | None:
        if not _is_safe_id(str(conversation_id or "")):
            return None
        return self.root / f"{conversation_id}.json"

    def _write(self, conversation: dict[str, Any]) -> None:
        path = self._path_for(str(conversation.get("conversation_id") or ""))
        if path is None:
            raise ValueError("会话 ID 无效")
        path.write_text(json.dumps(conversation, ensure_ascii=False, indent=2), encoding="utf-8")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _conversation_id() -> str:
    return "conv_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _is_safe_id(value: str) -> bool:
    return bool(re.fullmatch(r"conv_[0-9]{8}_[0-9]{6}_[0-9]{6}", value))
```

- [ ] **Step 4: Run store tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/test_desktop_conversation_store.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit store**

Run:

```bash
git add desktop/conversation_store.py tests/test_desktop_conversation_store.py
git commit -m "feat: add desktop conversation store"
```

## Task 2: Desktop API Chat Methods

**Files:**
- Modify: `desktop/api.py`
- Modify: `tests/test_desktop_api.py`

- [ ] **Step 1: Add API tests**

Append to `tests/test_desktop_api.py`:

```python
from desktop.conversation_store import ConversationStore


def test_desktop_api_creates_and_lists_conversations(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=FakeRunner(),
        conversation_store=ConversationStore(tmp_path / "conversations"),
    )

    created = api.new_conversation()
    listed = api.list_conversations()

    assert created["ok"] is True
    assert listed["ok"] is True
    assert listed["conversations"][0]["conversation_id"] == created["conversation"]["conversation_id"]


def test_desktop_api_run_chat_message_refuses_without_key(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=runner,
        conversation_store=ConversationStore(tmp_path / "conversations"),
    )

    result = api.run_chat_message("", "帮我总结")

    assert result["ok"] is False
    assert "Key" in result["error"]
    assert runner.started_inputs == []


def test_desktop_api_run_chat_message_starts_runner_and_records_messages(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    conversation_store = ConversationStore(tmp_path / "conversations")
    api = DesktopAPI(settings_store=SettingsStore(), runner=runner, conversation_store=conversation_store)
    api.save_settings({"llm_api_key": "secret-key"})

    result = api.run_chat_message("", "帮我总结")
    conversation = conversation_store.get_conversation(result["conversation_id"])["conversation"]

    assert result["ok"] is True
    assert result["task_id"] == "task_fake"
    assert runner.started_inputs == ["帮我总结"]
    assert [message["role"] for message in conversation["messages"]] == ["user", "assistant"]
    assert conversation["messages"][1]["status"] == "running"


def test_desktop_api_sync_chat_result_updates_assistant_message(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    conversation_store = ConversationStore(tmp_path / "conversations")
    api = DesktopAPI(settings_store=SettingsStore(), runner=runner, conversation_store=conversation_store)
    api.save_settings({"llm_api_key": "secret-key"})
    started = api.run_chat_message("", "帮我总结")

    synced = api.sync_chat_result(started["conversation_id"], started["task_id"])
    conversation = conversation_store.get_conversation(started["conversation_id"])["conversation"]

    assert synced["ok"] is True
    assistant = conversation["messages"][1]
    assert assistant["content"] == "done"
    assert assistant["status"] == "completed"
```

- [ ] **Step 2: Run API tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_desktop_api.py::test_desktop_api_creates_and_lists_conversations tests/test_desktop_api.py::test_desktop_api_run_chat_message_refuses_without_key tests/test_desktop_api.py::test_desktop_api_run_chat_message_starts_runner_and_records_messages tests/test_desktop_api.py::test_desktop_api_sync_chat_result_updates_assistant_message -q
```

Expected: FAIL because `DesktopAPI` does not accept `conversation_store` and chat methods do not exist.

- [ ] **Step 3: Implement API methods**

In `desktop/api.py`, add import:

```python
from desktop.conversation_store import ConversationStore
```

Extend `DesktopAPI.__init__` parameters:

```python
        conversation_store: ConversationStore | None = None,
```

Set default store:

```python
        self.conversation_store = (
            conversation_store if conversation_store is not None else ConversationStore(uta_home() / "conversations")
        )
```

Add methods:

```python
    def list_conversations(self) -> dict[str, Any]:
        try:
            return self.conversation_store.list_conversations()
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def new_conversation(self) -> dict[str, Any]:
        try:
            return self.conversation_store.new_conversation()
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def get_conversation(self, conversation_id: str) -> dict[str, Any]:
        try:
            return self.conversation_store.get_conversation(str(conversation_id or ""))
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def run_chat_message(self, conversation_id: str, user_input: str) -> dict[str, Any]:
        text = str(user_input or "").strip()
        if not text:
            return {"ok": False, "error": "请输入消息内容"}
        if not self.settings_store.public_settings()["has_api_key"]:
            return {"ok": False, "error": "请先配置 API Key"}

        try:
            if conversation_id:
                loaded = self.conversation_store.get_conversation(str(conversation_id))
                if not loaded.get("ok"):
                    created = self.conversation_store.new_conversation()
                    conversation_id = created["conversation"]["conversation_id"]
            else:
                created = self.conversation_store.new_conversation()
                conversation_id = created["conversation"]["conversation_id"]

            task_id = self.runner.start(text)
            self.conversation_store.append_message(conversation_id, role="user", content=text, task_id=task_id)
            self.conversation_store.append_message(
                conversation_id,
                role="assistant",
                content="正在处理...",
                task_id=task_id,
                status="running",
            )
            return {"ok": True, "conversation_id": conversation_id, "task_id": task_id}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def sync_chat_result(self, conversation_id: str, task_id: str) -> dict[str, Any]:
        try:
            result = self.runner.get_result(str(task_id or ""))
            status = str(result.get("status") or "unknown")
            content = str(result.get("final_output") or result.get("error") or "未生成输出")
            if status == "running":
                return {"ok": True, "status": status}
            updated = self.conversation_store.update_assistant_message(
                str(conversation_id or ""),
                task_id=str(task_id or ""),
                content=content,
                status=status,
            )
            if not updated.get("ok"):
                return updated
            return {"ok": True, "status": status, "conversation": updated["conversation"]}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
```

- [ ] **Step 4: Run API tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_desktop_api.py tests/test_desktop_conversation_store.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit API**

Run:

```bash
git add desktop/api.py tests/test_desktop_api.py
git commit -m "feat: add desktop chat api"
```

## Task 3: Chat Layout HTML and CSS

**Files:**
- Modify: `desktop/frontend/index.html`
- Modify: `desktop/frontend/style.css`
- Modify: `tests/test_desktop_frontend_assets.py`

- [ ] **Step 1: Add frontend asset tests**

Append to `tests/test_desktop_frontend_assets.py`:

```python
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
```

- [ ] **Step 2: Run frontend asset tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_desktop_frontend_assets.py::test_frontend_includes_chat_surface_and_detail_panel tests/test_desktop_frontend_assets.py::test_frontend_chat_styles_exist -q
```

Expected: FAIL because chat DOM and CSS classes do not exist.

- [ ] **Step 3: Replace task view markup**

In `desktop/frontend/index.html`, replace the current `<section class="workspace" id="taskView">...</section>` with:

```html
        <section class="workspace chatWorkspace" id="taskView">
          <div class="chatColumn">
            <section class="panel chatPanel">
              <div class="panelHead">
                <h3>对话</h3>
                <div class="segments">
                  <button class="segment active" type="button" data-example="summarize">文本</button>
                  <button class="segment" type="button" data-example="data">表格</button>
                </div>
              </div>
              <div class="chatMessages" id="chatMessages">
                <article class="chatMessage assistant">
                  <div class="messageBubble">你好，我是 UTA。把任务发给我，我会在右侧展示拆解步骤和执行状态。</div>
                </article>
              </div>
              <div class="chatComposer">
                <textarea id="taskInput" spellcheck="false" rows="3">帮我总结一段文本：面对庞杂的Agent学习资料，其知识内容并非无序堆砌，而是一种高度结构化、模块化但分布在不同载体中的体系。</textarea>
                <div class="toolbar">
                  <button class="button secondary" type="button" id="loadExample">载入示例</button>
                  <button class="button secondary" type="button" id="clearTask">清空</button>
                  <button class="button primary" type="button" id="runTask">发送</button>
                </div>
              </div>
            </section>
          </div>

          <div class="detailColumn" id="chatDetailPanel">
            <section class="panel grow">
              <div class="panelHead">
                <h3>执行详情</h3>
                <span id="planMeta">0 步</span>
              </div>
              <div class="steps" id="planList"></div>
            </section>

            <section class="panel logsPanel">
              <div class="panelHead">
                <h3>实时日志</h3>
                <button class="button ghost compact" type="button" id="clearLogs">清空</button>
              </div>
              <div class="logs" id="logPanel"></div>
            </section>

            <details class="stateBox">
              <summary>state.json</summary>
              <pre id="stateJson">{
  "status": "idle",
  "task_id": null
}</pre>
            </details>
          </div>
        </section>
```

- [ ] **Step 4: Add chat CSS**

Append to `desktop/frontend/style.css` before media queries:

```css
.chatWorkspace {
  grid-template-columns: minmax(420px, 1fr) minmax(360px, 0.82fr);
  align-items: stretch;
}

.chatColumn,
.detailColumn {
  min-height: 0;
  display: grid;
  gap: 16px;
}

.chatPanel {
  min-height: 0;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  overflow: hidden;
}

.chatMessages {
  min-height: 0;
  overflow: auto;
  padding: 18px;
  display: grid;
  align-content: start;
  gap: 14px;
}

.chatMessage {
  min-width: 0;
  display: flex;
}

.chatMessage.user {
  justify-content: flex-end;
}

.chatMessage.assistant,
.chatMessage.system {
  justify-content: flex-start;
}

.messageBubble {
  max-width: min(720px, 88%);
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #f8fafc;
  overflow-wrap: anywhere;
}

.chatMessage.user .messageBubble {
  color: #fff;
  background: var(--accent);
  border-color: var(--accent);
}

.chatMessage.failed .messageBubble {
  border-color: var(--danger);
}

.chatMessage.running .messageBubble::after {
  content: " 正在执行";
  color: var(--muted);
  font-family: var(--mono);
  font-size: 12px;
}

.chatComposer {
  border-top: 1px solid var(--border);
  background: var(--surface);
}

.chatComposer textarea {
  min-height: 92px;
}

.detailColumn {
  grid-template-rows: auto minmax(220px, 0.9fr) auto;
  align-content: stretch;
}
```

- [ ] **Step 5: Run frontend asset tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_desktop_frontend_assets.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit layout**

Run:

```bash
git add desktop/frontend/index.html desktop/frontend/style.css tests/test_desktop_frontend_assets.py
git commit -m "feat: add desktop chat layout"
```

## Task 4: Frontend Chat Behavior

**Files:**
- Modify: `desktop/frontend/app.js`
- Modify: `tests/test_desktop_frontend_assets.py`

- [ ] **Step 1: Add JS behavior tests**

Append to `tests/test_desktop_frontend_assets.py`:

```python
def test_frontend_calls_chat_bridge_methods_and_updates_messages():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'callApi("run_chat_message"' in js
    assert 'callApi("sync_chat_result"' in js
    assert "function addChatMessage" in js
    assert "function updateAssistantMessage" in js
    assert "function renderChatMessages" in js
    assert "pendingAssistantId" in js


def test_frontend_task_completed_updates_assistant_message_not_report_panel_only():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'event.type === "task_completed"' in js
    assert "updateAssistantMessage" in js
    assert "renderMarkdown(state.reportText)" in js
```

- [ ] **Step 2: Run JS behavior tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_desktop_frontend_assets.py::test_frontend_calls_chat_bridge_methods_and_updates_messages tests/test_desktop_frontend_assets.py::test_frontend_task_completed_updates_assistant_message_not_report_panel_only -q
```

Expected: FAIL because chat functions and chat bridge calls do not exist.

- [ ] **Step 3: Extend element and state maps**

In `desktop/frontend/app.js`, add element references:

```javascript
  chatMessages: document.getElementById("chatMessages"),
  chatDetailPanel: document.getElementById("chatDetailPanel"),
```

Extend `state`:

```javascript
  conversationId: null,
  messages: [],
  pendingAssistantId: null,
```

- [ ] **Step 4: Add chat render helpers**

Add after `showToast()`:

```javascript
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

function updateAssistantMessage(taskId, patch) {
  const message = [...state.messages].reverse().find((item) => item.role === "assistant" && item.taskId === taskId);
  if (!message) return;
  Object.assign(message, patch);
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
      <div class="messageBubble">${message.role === "assistant" ? renderMarkdown(message.content || "") : escapeHtml(message.content || "")}</div>
    </article>
  `).join("");
  els.chatMessages.scrollTop = els.chatMessages.scrollHeight;
}
```

- [ ] **Step 5: Update reset and run flow**

Change `resetRunSurface()` to clear details but keep chat messages:

```javascript
function resetRunSurface() {
  els.planList.innerHTML = "";
  els.logPanel.innerHTML = "";
  els.planMeta.textContent = "0 步";
  els.stateJson.textContent = JSON.stringify({ status: "idle", task_id: null }, null, 2);
  state.reportText = "";
}
```

Change `runTask()` bridge call:

```javascript
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
      updateAssistantMessage(null, { content: result.error || "未知错误", status: "failed" });
      showToast("无法运行", result.error || "未知错误");
      if ((result.error || "").includes("Key")) openSettings();
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
    updateAssistantMessage(null, { content: error.message, status: "failed" });
    showToast("运行失败", error.message);
  } finally {
    if (!state.running) {
      els.taskInput.readOnly = false;
      els.runTask.disabled = false;
    }
  }
}
```

If `updateAssistantMessage(null, ...)` cannot find the pending message, update it by `state.pendingAssistantId`:

```javascript
function updatePendingAssistant(patch) {
  const message = state.messages.find((item) => item.id === state.pendingAssistantId);
  if (!message) return;
  Object.assign(message, patch);
  renderChatMessages();
}
```

Use `updatePendingAssistant(...)` for pre-task errors.

- [ ] **Step 6: Update progress handling**

Inside `handleProgress(event)` update assistant content:

```javascript
  if (event.type === "parsed") {
    updateAssistantMessage(state.taskId, { content: "已理解任务，正在制定执行步骤...", status: "running" });
  }

  if (event.type === "plan_created") {
    renderPlan(data.steps || []);
    updateAssistantMessage(state.taskId, { content: `已拆解为 ${(data.steps || []).length} 个步骤，正在执行...`, status: "running" });
  }
```

Replace the `task_completed` block with:

```javascript
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
    await callApi("sync_chat_result", state.conversationId || "", state.taskId || "");
    await refreshResult();
  }
```

In the `error` block:

```javascript
    updateAssistantMessage(state.taskId, { content: data.message || "任务失败", status: "failed" });
```

- [ ] **Step 7: Add keyboard send behavior**

In `bindEvents()` add:

```javascript
  els.taskInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      runTask();
    }
  });
```

- [ ] **Step 8: Run JS tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_desktop_frontend_assets.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit chat behavior**

Run:

```bash
git add desktop/frontend/app.js tests/test_desktop_frontend_assets.py
git commit -m "feat: wire desktop chat interactions"
```

## Task 5: History and Documentation

**Files:**
- Modify: `desktop/frontend/index.html`
- Modify: `desktop/frontend/app.js`
- Modify: `tests/test_desktop_frontend_assets.py`
- Modify: `README.md`
- Modify: `desktop/README.md`
- Modify: `docs/project-overview.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add tests for conversation history bridge**

Append to `tests/test_desktop_frontend_assets.py`:

```python
def test_frontend_can_load_conversation_history():
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'callApi("list_conversations")' in js
    assert 'callApi("get_conversation", conversationId)' in js
    assert "function loadConversationHistory" in js
    assert "function selectConversation" in js
```

- [ ] **Step 2: Run history frontend test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_desktop_frontend_assets.py::test_frontend_can_load_conversation_history -q
```

Expected: FAIL because conversation history functions do not exist.

- [ ] **Step 3: Add conversation history functions**

In `desktop/frontend/app.js`, keep existing run history methods and add:

```javascript
async function loadConversationHistory() {
  try {
    const result = await callApi("list_conversations");
    if (!result.ok) {
      showToast("读取会话失败", result.error || "未知错误");
      return;
    }
    renderConversationList(result.conversations || []);
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
      id: `${message.role}_${message.task_id || ""}_${message.created_at || ""}`,
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
```

Change `showHistoryView()` to call `loadConversationHistory()` first:

```javascript
async function showHistoryView() {
  els.taskView.classList.add("hidden");
  els.historyView.classList.remove("hidden");
  els.memoryView.classList.add("hidden");
  els.knowledgeView.classList.add("hidden");
  els.skillsView.classList.add("hidden");
  setActiveNav(els.openHistory);
  await loadConversationHistory();
}
```

- [ ] **Step 4: Update history labels**

In `desktop/frontend/index.html`, change history headings:

```html
<button class="nav" type="button" id="openHistory">会话历史</button>
...
<h3>会话历史</h3>
...
<h3>历史消息</h3>
```

- [ ] **Step 5: Update docs**

Add to `README.md` feature list:

```markdown
- 桌面端对话式前端：主界面支持聊天输入，右侧保留步骤、日志、state 等执行详情。
```

Add to `desktop/README.md`:

```markdown
## 对话式前端

桌面端主任务页现在采用“聊天主界面 + 执行详情侧栏”。发送消息后，任务仍走 `main.run_task()`，右侧同步显示 Planner 步骤、实时日志和 state.json。
```

Add to `CHANGELOG.md` under Unreleased or latest section:

```markdown
- 新增桌面端对话式前端，支持聊天消息流和执行详情侧栏。
```

Add to `docs/project-overview.md`:

```markdown
- `desktop/frontend/`：桌面端前端，主任务页为聊天消息流，执行详情仍显示步骤、日志和 state。
```

- [ ] **Step 6: Run docs/frontend tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_desktop_frontend_assets.py tests/test_desktop_api.py tests/test_desktop_conversation_store.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit history/docs**

Run:

```bash
git add desktop/frontend/index.html desktop/frontend/app.js tests/test_desktop_frontend_assets.py README.md desktop/README.md docs/project-overview.md CHANGELOG.md
git commit -m "docs: document desktop chat frontend"
```

## Task 6: Full Verification and Packaging

**Files:**
- No source edits unless verification exposes a bug.

- [ ] **Step 1: Run full test suite**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected: PASS with no failures.

- [ ] **Step 2: Build desktop app**

Run:

```bash
bash desktop/build/build_macos.sh
```

Expected:

```text
构建完成：dist/UTA Desktop.app
压缩包：dist/UTA Desktop-macos.zip
```

- [ ] **Step 3: Verify packaged resources**

Run:

```bash
rg -n "chatMessages|run_chat_message|sync_chat_result|ConversationStore|chatWorkspace" "dist/UTA Desktop.app/Contents/Resources/source" "dist/UTA Desktop.app/Contents/Resources/frontend"
```

Expected: matches in packaged source/frontend resources.

- [ ] **Step 4: Verify signature and zip hash**

Run:

```bash
codesign --verify --deep --strict --verbose=1 "dist/UTA Desktop.app"
shasum -a 256 "dist/UTA Desktop-macos.zip"
```

Expected: codesign exits 0 and SHA256 is printed.

- [ ] **Step 5: Final commit if packaging changed tracked files**

Run:

```bash
git status --short --branch
```

Expected: no uncommitted source changes. If source fixes were required during verification, commit them with a focused message.

## Self-Review

- Spec coverage: plan covers chat surface, detail sidebar, conversation persistence, DesktopAPI methods, progress updates, history access, tests, packaging, and documentation.
- Completeness scan: no unfinished markers and no unspecified “add tests” step. Each task has exact file paths and commands.
- Type consistency: `conversation_id`, `task_id`, `messages`, `role`, `content`, `status` are used consistently across store, API, and frontend. Frontend keeps existing `taskInput`, `runTask`, `planList`, `logPanel`, and `stateJson` IDs to reduce breakage.

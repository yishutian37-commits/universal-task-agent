# 桌面端对话式前端设计

日期：2026-06-30

## 背景

当前 UTA Desktop 已经是一个本地可视化 Agent 应用：前端在 `desktop/frontend/`，后端是 `desktop.api.DesktopAPI`，两者通过 pywebview 的 `window.pywebview.api` 桥通信，任务最终仍走 `main.run_task()`。

现有界面偏“任务控制台”：用户输入一段任务，应用显示计划、日志、最终结果、state。这个形态适合调试 Agent，但不像一个自然可用的对话助手。下一步要在不推翻现有后端的前提下，把主体验升级为“对话式前端 + 可展开执行详情”。

## 目标

- 主界面默认像聊天工具：用户输入消息，Agent 回复结果。
- 每轮对话仍走现有 `run_task()`、Planner、Router、Executor、Verifier、Memory、Skill、RAG 能力。
- 执行步骤、实时日志、state、记忆命中不消失，而是作为详情区展示。
- 运行记录从“任务历史”升级为“会话历史”：能看到一轮轮用户消息和 Agent 回复。
- 首版只支持本地单机使用，不引入 HTTP 服务、不改为 Electron/Tauri。
- 尽量复用当前桌面端文件和事件流，避免重写核心后端。

## 非目标

- 不做多人协作。
- 不做云同步。
- 不做移动端。
- 不做语音输入。
- 不做多任务并行执行。
- 不把 pywebview 架构改成 HTTP API 架构。
- 不让前端直接接触明文 API Key。

## 推荐方案

采用“聊天主界面 + 详情侧栏”的组合形态。

默认状态下，用户看到的是对话流：

```text
用户：帮我分析这篇文章，并改写成小白版
Agent：正在拆解任务...
Agent：已完成，总结如下...
```

当任务运行时或用户点开详情时，右侧显示：

- 当前计划步骤
- `[ ] / [...] / [x] / [!]` 状态
- 实时日志
- state.json
- 本轮命中的 Skill
- 本轮使用的记忆或知识库结果

这样保留“看懂 Agent 怎么运行”的学习价值，同时让日常使用更像一个真正的 Agent。

## 界面结构

桌面端仍保持单页应用，左侧导航继续存在。

主任务页改为三块：

```text
┌────────────────────────────────────────────────────────────┐
│ UTA Desktop                                  状态 / 设置    │
├──────────────┬──────────────────────────────┬──────────────┤
│ 左侧导航      │ 对话区                         │ 详情区         │
│              │                              │              │
│ 任务          │ 消息列表                       │ 步骤           │
│ 运行记录      │ 用户消息 / Agent 回复           │ 日志           │
│ 记忆          │                              │ state.json     │
│ 知识库        │ 底部输入框                     │ 记忆 / Skill    │
│ 技能包        │                              │              │
└──────────────┴──────────────────────────────┴──────────────┘
```

桌面宽度足够时显示右侧详情区；窗口较窄时，详情区收起为“详情”按钮，点击后覆盖或折叠展开。

## 交互流程

### 新建一轮对话

1. 用户在底部输入框输入任务。
2. 前端创建一条用户消息。
3. 前端创建一条 Agent 占位消息，状态为“思考中”。
4. 前端调用 `DesktopAPI.run_task(user_input)`。
5. 后端返回 `task_id`。
6. 执行过程通过现有 `window.onProgress(event)` 推送。
7. 前端根据事件更新详情区。
8. 任务完成后，Agent 消息替换为最终结果。

### 查看执行详情

用户不需要在最终答案里看到完整过程清单。过程清单留在详情区：

- `plan_created`：渲染全部步骤为 `[ ]`
- `step_started`：当前步骤变为 `[...]`
- `step_done`：完成变为 `[x]`，失败变为 `[!]`
- `error`：Agent 消息显示失败原因，详情区保留日志

### 历史会话

首版会话历史基于现有运行记录实现：

- 每次 `task_id` 对应一轮消息。
- 会话列表按时间倒序。
- 点击历史记录时，重建一轮用户消息和 Agent 回复。
- 后续再升级为真正的多轮 `conversation_id`。

## 后端设计

### 保持现有核心路径

不改 `main.run_task()` 的核心职责。对话前端只是新的展示层。

```text
Chat UI
  -> DesktopAPI.run_task(user_input)
  -> TaskRunner.start(user_input)
  -> main.run_task(...)
  -> on_progress(event)
  -> window.onProgress(event)
  -> Chat UI 更新消息和详情
```

### 新增轻量会话层

首版新增一个小模块，例如 `desktop/conversation_store.py`，用于把“任务运行结果”转成“对话消息”：

```json
{
  "conversation_id": "local_default",
  "messages": [
    {
      "role": "user",
      "task_id": "task_...",
      "content": "用户输入",
      "created_at": "..."
    },
    {
      "role": "assistant",
      "task_id": "task_...",
      "content": "最终输出",
      "status": "completed",
      "created_at": "..."
    }
  ]
}
```

数据存放在：

```text
~/.uta/conversations/
```

### DesktopAPI 增量方法

新增方法：

```text
list_conversations()
get_conversation(conversation_id)
new_conversation()
run_chat_message(conversation_id, user_input)
```

首版可以让 `run_chat_message()` 内部复用 `runner.start()`，不复制任务执行逻辑。

为了降低风险，也可以第一步只用现有 `run_task()`，前端先维护当前会话内存；完成后再补持久化会话。

## 前端设计

### 文件边界

当前 `desktop/frontend/app.js` 已经较大。为了避免继续膨胀，聊天前端拆成小文件更清楚：

```text
desktop/frontend/
├─ app.js              # 启动、导航、事件绑定
├─ chat.js             # 消息流、输入框、发送消息
├─ task_details.js     # 步骤、日志、state、详情区
├─ markdown.js         # Markdown 渲染和转义
├─ style.css           # 全局样式
└─ index.html
```

如果暂时不想拆文件，也可以先在 `app.js` 内分区实现，但本设计推荐拆分，方便后续维护。

### 消息类型

前端消息至少包含：

```text
role: user | assistant | system
status: pending | running | completed | failed
content: string
taskId: string
```

### 输入区

底部输入区支持：

- 回车发送
- Shift + 回车换行
- 运行中禁用发送
- 无 API Key 时提示去设置
- 保留“载入示例”按钮，但放到输入区旁边

## 错误处理

- 未配置 API Key：不创建运行任务，直接在聊天区显示提示。
- 已有任务运行中：发送按钮禁用，避免并行冲突。
- LLM 网络失败：Agent 消息显示失败原因，详情区显示错误事件。
- 任务失败：消息状态为失败，不丢失用户输入。
- Markdown 渲染异常：降级为纯文本显示。
- 会话文件损坏：忽略损坏文件，并在日志里显示提示。

## 测试

必须覆盖：

- `ConversationStore` 能创建、读取、追加消息。
- `DesktopAPI.run_chat_message()` 能启动任务并返回 `task_id`。
- 前端资源包含聊天区、消息列表、输入区、详情区。
- `onProgress(event)` 能同时更新聊天消息和详情步骤。
- 任务完成后最终结果进入 assistant 消息。
- 运行中不能重复发送。
- 全量测试通过。
- 桌面端重新打包后，包内资源包含新增前端文件。

## 验收标准

用桌面端测试：

```text
帮我执行复杂任务：[1]总结全文核心观点 [2]提炼5个关键结论 [3]改写成小白版
```

预期：

- 用户输入显示为一条用户消息。
- Agent 先显示运行中状态。
- 右侧详情区显示步骤，从 `[ ]` 到 `[x]`。
- 最终结果显示为 Agent 回复。
- 最终回复不显示执行清单，执行过程留在详情区。
- Markdown 能正确渲染，不显示裸 ` ```markdown `。
- 运行记录或会话历史能看到这轮任务。

## 实施顺序

1. 新增会话数据结构和 `ConversationStore`。
2. 扩展 `DesktopAPI`，提供对话方法。
3. 调整前端 HTML，加入聊天区和详情区。
4. 拆分或整理前端 JS，接入消息流。
5. 复用现有 `onProgress(event)` 更新详情区。
6. 调整 CSS，让聊天区成为默认主体验。
7. 补测试。
8. 重新构建 macOS `.app` 和 zip。
9. 本地 git 提交。

## 风险和取舍

- 当前 `TaskRunner` 一次只能跑一个任务。首版聊天也保持这个限制，避免并行状态混乱。
- 当前 Agent 不是严格多轮上下文模型。首版“对话”是 UI 层多轮，执行层仍是一轮一任务。真正把历史消息注入下一轮推理，放到后续版本。
- 拆分前端 JS 会增加文件数，但能让聊天、详情、Markdown 渲染边界更清楚。
- 不引入 HTTP 服务，意味着外部网页暂时不能直接调用这个后端；这是为了保持打包和本地安全简单。

## 后续版本

首版完成后，可以继续做：

- 真正的 `conversation_id` 多轮上下文注入。
- 让 Agent 在回答时自动引用长期记忆。
- 对话里直接上传文件或拖入文件。
- 对话中选择是否使用 RAG 知识库。
- 外部 HTTP API 模式，供浏览器前端或其他应用连接。

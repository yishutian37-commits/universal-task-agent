# UTA Codex 工作台第一阶段最终修复报告

日期：2026-07-10

修复基线：`ce85105c13be6a32de2b8d62d59bf611d9e6938b`

实现提交：`5033778fc48563a79429d40b63cc9a68e38726ff`

## 处置结果

### Important 1：终态/进度事件跨会话或跨任务污染

已修复。`shell.js` 新增无依赖 `createRunLifecycle()`，将请求阶段、任务身份和终态转移从 DOM 状态中分离：

- `beginRequest()` 在 `run_chat_message` 返回前立即进入 `requesting`，第二次提交、新建会话和切换会话都使用同一 `isBusy()` 锁。
- 请求与任务上下文通过 `Object.freeze()` 固定 `requestId/taskId/conversationId/conversationRevision/assistantId`。
- API 映射未建立时，事件按 `event.task_id` 缓冲；`bindTask()` 只取回 API 返回 task ID 对应的事件并回放。
- `handleProgress()` 在写日志、聊天、任务面板、授权弹窗或 state DOM 前先执行任务路由和会话修订校验。
- 终态分支只使用路由出的 `taskId`；`syncTerminalTask(taskId)` 从任务上下文取会话，`refreshResult(taskId)` 在 API 返回后再次校验当前上下文。
- 非当前终态仍可按自身 task ID 做后台会话同步，但不能写入当前聊天、面板、日志、弹窗或诊断 state。

### Important 2：`stopTask` 晚返回覆盖终态

已修复。`stopTask()` 在调用 API 前捕获原 `taskId`，并通过 `beginCancel()` 立即进入 `cancelling`。“正在停止”在 await 前写入；取消 Promise 返回后只调用 `confirmCancel(taskId)`，不再重写可见状态。`cancelled/completed/error` 是吸收终态，晚到的成功、失败或异常 continuation 均不能逆转终态。

### Important 3：窄屏抽屉压住设置/授权弹窗

已修复。`.modalBackdrop` 改为 `inset: 0` 和 `z-index: 100`，高于抽屉的 `z-index: 20`。`.modal` 使用 `max-height: calc(100dvh - 48px)` 的三行网格，header/footer 保持可见；新增 `.settingsBody`，它与 `.authorizationBody` 都使用独立纵向滚动。760px 及以下收窄遮罩边距，授权详情改为单列，footer 的拒绝/授权按钮不进入滚动区。

### Minor

- 任务面板开关已增加 `aria-controls`/`aria-expanded`；通过面板内控件关闭时恢复到开关焦点。
- 任务 tab 已实现 roving `tabindex`、左右方向键、Home 和 End，未延期。
- 会话侧栏依据 `state.conversationId` 设置 `active` 和 `aria-current`。
- 旧的 `state.taskId/state.running` 交错字符串断言已更新；资源、DOM、配色和布局契约测试保留。
- handoff 文档 EOF 多余空行已删除。
- 计划和 handoff 统一为 761px-1179px 任务抽屉、760px 及以下窄侧栏；计划中的媒体查询示例也改为 `max-width: 760px`。

## TDD 记录

### RED

1. 新增无依赖 Node 行为测试后，`tests/test_desktop_workbench_runtime.py` 为 `6 failed`：旧 `shell.js` 不能在 Node 中加载，也没有请求/任务生命周期 API。
2. 替换过时 app.js 交错断言后，聚焦套件为 `10 failed, 33 passed`：失败点对应旧全局 task ID、API 返回后置锁、旧取消 continuation 和无参 refresh。
3. 增加模态/ARIA/边界契约后，套件为 `5 failed, 56 passed`：确认旧遮罩 inset/层级、缺少滚动主体、缺少 toggle 属性与计划边界不一致。其中一项为 UMD 导出后的过时资源字符串断言，已按新导出契约修正。

### GREEN

- `.venv/bin/python -m pytest tests/test_desktop_workbench_runtime.py -q`：`6 passed`。
- `.venv/bin/python -m pytest tests/test_desktop_workbench_shell.py tests/test_desktop_frontend_assets.py -q`：`61 passed`。
- 指定回归套件：`119 passed`。
- `node --check desktop/frontend/app.js`：通过。
- `node --check desktop/frontend/shell.js`：通过。
- `git diff --check fe81fae..5033778`：通过。

Node 行为测试真实执行 `shell.js`，覆盖：API 未返回时拒绝第二请求、早到事件按 task ID 缓冲/映射、旧任务不能成为当前任务、终态使用事件 task ID、cancel 返回晚于 cancelled，以及 completed/cancel Promise 竞态。

## 自审

- 数据流：从 `runTask -> beginRequest -> routeEvent/buffer -> bindTask -> replay -> terminal sync/refresh` 逐段回溯，未发现仍依赖后写 `state.taskId` 的终态路径。
- 竞态：终态进入后生命周期不接受进度、取消确认或取消失败回退；所有 await 后的诊断写入都重新校验上下文。
- 可见性：`handleProgress` 的首个可见操作位于 route/context guard 之后；后台同步失败日志和 toast 也只能写入当前上下文。
- 布局：modal 遮罩和抽屉有明确层级差，两种 modal DOM 都是 header/body/footer 顺序，只有 body 可滚动。
- 范围：实现提交只包含用户允许的 9 个前端、测试和文档文件，没有暂存或修改范围外 `core/`、`tools/` 或 desktop 后端脏文件。
- 独立复核：Orca 调度运行时未启动；替代的只读 Codex review 因外部代码传输安全策略被拒绝，没有发送任何代码。本报告的结论基于当前代理自审和本地自动化证据。

## 剩余风险

- 按任务分工，1024/760 宽度下的浏览器 `elementFromPoint` 和截图复验由主代理执行；本次已增加精确 CSS/DOM 契约，但未在本任务中代替该浏览器检查。
- macOS 解锁后的真实“拒绝/授权执行”双路径仍需主代理实机验收。
- 按用户要求未运行全量套件；全量回归由主代理最终执行。
- 本次要求内的代码 finding 无未解决项。

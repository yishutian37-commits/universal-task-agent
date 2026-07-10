# 记忆中心工作区改造实施计划

> **给执行代理：** 必须使用 `superpowers:subagent-driven-development` 按任务执行；每个任务先测试失败，再实现、提交并独立审查。

**目标：** 将当前无限向下展开的记忆中心改造成四标签、稳定高度、列表与详情分离的管理工作区，并重新打包桌面应用。

**架构：** `shell.js` 提供可独立测试的标签切换、文本压缩、长期记忆分组和经验去重函数；`app.js` 负责保存记忆页面状态并渲染四个标签；`index.html` 和 `style.css` 提供专用结构和受控滚动，不修改任何记忆后端接口或数据文件。

**技术栈：** 原生 HTML/CSS/JavaScript、Node.js 运行测试、pytest 静态资产测试、pywebview、PyInstaller。

## 全局约束

- 不修改 `get_memory_overview`、`get_conversation`、`compress_conversation` 的接口和返回结构。
- 不迁移、不删除、不自动改写已有记忆记录。
- 不回滚工作区内现有后端、工具、授权、checkpoint 和其他未提交改动。
- 所有界面文字使用中文，内部 ID 只能作为次级信息。
- `memoryView` 不得继续使用无限展开的 `overflow: visible` 修复方式。
- 最小窗口 `960×640` 不得出现横向滚动。

---

### Task 1：可测试的记忆视图状态与内容整理函数

**文件：**
- 修改：`desktop/frontend/shell.js`
- 修改：`tests/test_desktop_workbench_runtime.py`

**产出接口：**
- `activateMemoryTab(tabName: string): string`
- `handleMemoryTabKeydown(event): string | null`
- `groupMemoryFacts(facts: Array<object>): Record<string, Array<object>>`
- `compactMemoryText(value: unknown, limit?: number): string`
- `dedupeMemoryLessons(items: Array<object>): Array<object>`，每项增加 `occurrence_count`

- [ ] **步骤 1：先写失败的 Node 运行测试**

增加测试覆盖：非法标签回退 `long-term`；四个合法标签可切换；键盘左右/Home/End 切换；Markdown 文本压成单行且限制长度；长期事实按 `kind` 分组；相同 `task_type + content` 的经验合并并累计次数。

```javascript
const {
  activateMemoryTab,
  groupMemoryFacts,
  compactMemoryText,
  dedupeMemoryLessons
} = require("./desktop/frontend/shell.js");

assert.equal(activateMemoryTab("invalid"), "long-term");
assert.deepEqual(groupMemoryFacts([{kind: "preference", content: "中文"}]).preference.length, 1);
assert.equal(compactMemoryText("## 标题\n- 内容", 20), "标题 内容");
assert.equal(dedupeMemoryLessons([
  {task_type: "summarize", content: "复用流程"},
  {task_type: "summarize", content: "复用流程"}
])[0].occurrence_count, 2);
```

- [ ] **步骤 2：运行新测试并确认失败**

运行：

```bash
.venv/bin/python -m pytest tests/test_desktop_workbench_runtime.py -q
```

预期：因上述导出函数不存在而失败。

- [ ] **步骤 3：实现最小纯函数和标签 DOM 契约**

在 `shell.js` 增加合法标签集合 `long-term`、`session`、`learning`、`archive`。`activateMemoryTab()` 同步 `[data-memory-tab]` 的 `active`、`aria-selected`、`tabIndex`，同步 `[data-memory-panel]` 的 `hidden` 和 `aria-hidden`。键盘处理沿用任务标签的循环切换方式。

`compactMemoryText()` 去除代码围栏、标题符号、列表符号、粗体和反引号，合并空白，超过限制时以省略号结尾。`dedupeMemoryLessons()` 保留最新条目的字段并按稳定键累计 `occurrence_count`。

- [ ] **步骤 4：运行测试与语法检查**

```bash
.venv/bin/python -m pytest tests/test_desktop_workbench_runtime.py -q
node --check desktop/frontend/shell.js
git diff --check -- desktop/frontend/shell.js tests/test_desktop_workbench_runtime.py
```

预期：全部通过。

- [ ] **步骤 5：提交任务 1**

```bash
git add desktop/frontend/shell.js tests/test_desktop_workbench_runtime.py
git commit -m "feat: add memory workspace view helpers"
```

---

### Task 2：四标签记忆中心结构、渲染与稳定布局

**文件：**
- 修改：`desktop/frontend/index.html`
- 修改：`desktop/frontend/app.js`
- 修改：`desktop/frontend/style.css`
- 修改：`tests/test_desktop_frontend_assets.py`
- 修改：`tests/test_desktop_workbench_shell.py`

**依赖接口：** Task 1 导出的五个 `UTAShell` 函数。

**产出结构：**
- 标签：`data-memory-tab="long-term|session|learning|archive"`
- 面板：`data-memory-panel="long-term|session|learning|archive"`
- 长期记忆：`memoryLongTermKinds`、`memoryLongTermFacts`
- 当前会话：`memoryConversationShortTerm`、`compressCurrentConversation`、`refreshMemory`
- 经验规则：`memoryLessons`、`memoryNegativeRules`、`memorySkillCandidates`
- 任务归档：`memoryArchiveList`、`memoryArchiveDetail`

- [ ] **步骤 1：写失败的静态布局测试**

测试必须断言四个标签的 ARIA 对应关系、四个面板、专用工作区和数据节点存在；旧的无限展开规则不存在；CSS 包含受控高度、内部滚动、双栏/三列以及 `1179px` 单列规则。

```python
assert 'class="workspace memoryCenterWorkspace hidden" id="memoryView"' in html
for name in ["long-term", "session", "learning", "archive"]:
    assert f'data-memory-tab="{name}"' in html
    assert f'data-memory-panel="{name}"' in html
assert "#memoryView .memoryBlock {\n  max-height: none;\n  overflow: visible;" not in css
assert ".memoryArchiveLayout" in css
assert ".memoryLearningLayout" in css
```

- [ ] **步骤 2：运行新测试并确认失败**

```bash
.venv/bin/python -m pytest tests/test_desktop_frontend_assets.py tests/test_desktop_workbench_shell.py -q
```

预期：因四标签结构和专用 CSS 尚不存在而失败。

- [ ] **步骤 3：改造 HTML 与 CSS**

将 `memoryView` 改为 `memoryCenterWorkspace`，按设计增加页面标题、标签栏和四个 `tabpanel`。删除原有长期总览大卡片和两列无限面板结构。

CSS 使用：

```css
.memoryCenterWorkspace {
  grid-template-columns: minmax(0, 1fr);
  grid-template-rows: auto auto minmax(0, 1fr);
  overflow: hidden;
}

.memoryLongTermLayout,
.memoryArchiveLayout {
  min-height: 0;
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 16px;
}

.memoryLearningLayout {
  min-height: 0;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}
```

所有列表和详情使用 `min-height: 0; overflow: auto;`。`1179px` 以下将上述布局改为单列，并给列表设置稳定的最大高度。

- [ ] **步骤 4：实现四类专用渲染**

在 `state` 增加 `memoryOverview`、`memoryTab`、`memoryLongTermKind` 和 `memoryArchiveTaskId`。`renderMemoryOverview()` 保存数据并调用：

- `renderMemoryLongTerm(facts)`：分类按钮与当前分类事实。
- `renderConversationShortTermMemory(conversation)`：同步禁用压缩按钮。
- `renderMemoryLearning(memory)`：调用 `dedupeMemoryLessons()`，显示累计次数。
- `renderMemoryArchive(tasks)`：最新任务默认选中，列表使用 `compactMemoryText()`，详情使用 `renderMarkdown()`。

新增 `setMemoryTab()` 并绑定四个标签点击和键盘事件。`compressCurrentConversation()` 的 `finally` 必须按 `state.conversationId` 恢复禁用状态，不能无条件启用。

- [ ] **步骤 5：运行聚焦测试与语法检查**

```bash
.venv/bin/python -m pytest tests/test_desktop_frontend_assets.py tests/test_desktop_workbench_shell.py tests/test_desktop_workbench_runtime.py -q
node --check desktop/frontend/app.js
node --check desktop/frontend/shell.js
git diff --check -- desktop/frontend/index.html desktop/frontend/app.js desktop/frontend/style.css tests/test_desktop_frontend_assets.py tests/test_desktop_workbench_shell.py
```

预期：全部通过。

- [ ] **步骤 6：提交任务 2**

```bash
git add desktop/frontend/index.html desktop/frontend/app.js desktop/frontend/style.css tests/test_desktop_frontend_assets.py tests/test_desktop_workbench_shell.py
git commit -m "feat: redesign memory center workspace"
```

---

### Task 3：真实窗口验收、全量测试与重新打包

**产物：**
- `dist/UTA Desktop.app`
- `dist/UTA Desktop-macos.zip`

- [ ] **步骤 1：真实数据窗口检查**

在 `1280×820`、`1179×800`、`960×640` 检查四个标签：外层页面不无限增长；长期分类和任务归档列表/详情独立滚动；经验规则无重叠；无会话时压缩按钮禁用；无横向溢出。

- [ ] **步骤 2：运行全量测试并打包**

```bash
bash desktop/build/build_macos.sh
```

预期：全量 pytest 通过并重新生成两个产物。

- [ ] **步骤 3：验证产物**

```bash
codesign --verify --deep --strict "dist/UTA Desktop.app"
unzip -t "dist/UTA Desktop-macos.zip"
rg -n "memoryCenterWorkspace|memoryArchiveLayout|data-memory-tab" "dist/UTA Desktop.app/Contents/Resources/frontend"
```

预期：全部退出码为 0。

- [ ] **步骤 4：重新启动打包版并最终检查**

关闭旧进程，重新启动新 `.app`，打开记忆中心，确认 URL 来自 `dist/UTA Desktop.app/Contents/Resources/frontend/index.html`，四个标签均可切换并显示真实数据。

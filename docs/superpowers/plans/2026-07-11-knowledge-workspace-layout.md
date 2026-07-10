# 知识库工作区布局修复实施计划

> **给执行代理：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务执行，每一步使用复选框跟踪。

**目标：** 将知识库从记忆页和历史页通用样式中拆出，形成稳定的文档浏览与知识问答双栏工作区，并重新打包桌面应用。

**架构：** 保留全部 RAG API 和数据节点，只为 `knowledgeView` 增加专用结构类与 CSS。文档渲染改用知识库专用条目类；宽窗口使用受约束双栏，窄窗口降为单栏，面板内部只保留必要滚动区。

**技术栈：** 原生 HTML/CSS/JavaScript、pytest 静态资产测试、PyInstaller、pywebview、macOS codesign。

## 全局约束

- 不修改 RAG 后端接口、数据结构和已有文档数据。
- 不回滚工作区内现有的后端、授权工具、记忆和 checkpoint 改动。
- 所有新增界面文字使用中文。
- 先写失败测试并确认失败，再修改生产代码。
- 打包前必须通过全量测试，打包后必须验证签名、zip 和真实窗口。

---

### 任务 1：知识库专用布局与条目样式

**文件：**
- 修改：`tests/test_desktop_frontend_assets.py`
- 修改：`desktop/frontend/index.html`
- 修改：`desktop/frontend/app.js`
- 修改：`desktop/frontend/style.css`

**接口：**
- 使用：现有 `loadKnowledgeBase()`、`loadKnowledgeDocs()` 和 `renderKnowledgeResult()`。
- 产出：`knowledgeWorkspace`、`knowledgeLibraryColumn`、`knowledgeQueryColumn`、`knowledgeDocList`、`knowledgeDocItem`、`knowledgeQueryPanel`、`knowledgeAnswer`、`knowledgeSources` 样式契约。

- [ ] **步骤 1：写失败的布局契约测试**

在 `tests/test_desktop_frontend_assets.py` 增加测试，要求知识库使用专用类，渲染结果不再使用 `historyItem`，路径带 `title`，CSS 有路径省略和专用问答面板规则：

```python
def test_knowledge_workspace_uses_dedicated_layout_without_history_card_leakage():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert 'class="workspace knowledgeWorkspace hidden"' in html
    assert 'class="knowledgeDocList" id="kbDocList"' in html
    assert 'class="panel knowledgeQueryPanel"' in html
    assert 'class="report empty knowledgeAnswer"' in html
    assert 'class="logs knowledgeSources"' in html
    assert 'class="knowledgeDocItem"' in js
    assert 'class="historyItem" data-doc-id' not in js
    assert 'class="knowledgeDocPath" title=' in js
    assert ".knowledgeDocPath" in css
    assert "text-overflow: ellipsis" in css
    assert ".knowledgeAnswer" in css
```

- [ ] **步骤 2：运行测试并确认按预期失败**

运行：

```bash
.venv/bin/python -m pytest tests/test_desktop_frontend_assets.py::test_knowledge_workspace_uses_dedicated_layout_without_history_card_leakage -q
```

预期：失败，提示 `knowledgeWorkspace` 或 `knowledgeDocItem` 尚不存在。

- [ ] **步骤 3：实现最小专用结构和样式**

在 `index.html` 中替换知识库容器类，移除输入区内联样式并加入专用类；在 `app.js` 中将条目改为：

```javascript
<div class="knowledgeDocItem" data-doc-id="${escapeHtml(doc.doc_id)}">
  <div class="knowledgeDocMain">
    <strong>${escapeHtml(doc.title || doc.source)}</strong>
    <small>${escapeHtml(doc.type || "?")} · ${doc.chunk_count} 片段</small>
    <small class="knowledgeDocPath" title="${escapeHtml(doc.source)}">${escapeHtml(doc.source)}</small>
  </div>
  <button class="button ghost compact kbDelBtn" type="button" data-doc-id="${escapeHtml(doc.doc_id)}" title="删除此文档">删除</button>
</div>
```

在 `style.css` 中加入知识库专用双栏、列行高、文档列表滚动、路径省略、回答区和来源区规则，并在 `max-width: 1179px` 下解除固定行高、改为单栏内容流。

- [ ] **步骤 4：运行聚焦测试**

运行：

```bash
.venv/bin/python -m pytest tests/test_desktop_frontend_assets.py tests/test_desktop_workbench_shell.py -q
node --check desktop/frontend/app.js
node --check desktop/frontend/shell.js
```

预期：全部通过，JavaScript 语法检查退出码为 0。

- [ ] **步骤 5：检查差异**

运行：

```bash
git diff --check -- desktop/frontend/index.html desktop/frontend/app.js desktop/frontend/style.css tests/test_desktop_frontend_assets.py
```

预期：退出码为 0，没有空白错误。

---

### 任务 2：真实窗口验收与重新打包

**文件：**
- 验证：`desktop/frontend/index.html`
- 构建：`dist/UTA Desktop.app`
- 构建：`dist/UTA Desktop-macos.zip`

**接口：**
- 使用：`desktop/build/build_macos.sh`。
- 产出：包含新版知识库布局的 macOS 应用和压缩包。

- [ ] **步骤 1：在开发版窗口验收知识库页面**

启动开发版，打开知识库，在桌面窗口尺寸下检查文档条目无重叠、路径省略、问答区和来源区可见；再检查窄窗口单栏布局没有横向溢出。

- [ ] **步骤 2：运行全量测试并重新打包**

运行：

```bash
bash desktop/build/build_macos.sh
```

预期：全量 pytest 通过，重新生成 `dist/UTA Desktop.app` 和 `dist/UTA Desktop-macos.zip`。

- [ ] **步骤 3：验证产物**

运行：

```bash
codesign --verify --deep --strict "dist/UTA Desktop.app"
unzip -t "dist/UTA Desktop-macos.zip"
rg -n "knowledgeWorkspace|knowledgeDocItem|knowledgeAnswer" "dist/UTA Desktop.app/Contents/Resources/frontend"
```

预期：三个命令全部退出码为 0，压缩包无错误，新类名存在于打包资源。

- [ ] **步骤 4：启动打包版冒烟验证**

打开 `dist/UTA Desktop.app`，进入知识库，确认当前窗口来自打包资源路径，且显示新版知识库布局。

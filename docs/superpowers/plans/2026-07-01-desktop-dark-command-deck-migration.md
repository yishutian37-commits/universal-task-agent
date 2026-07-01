# Desktop Dark Command Deck Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把早上新设计的深色 Command Deck 视觉系统迁入当前真实 UTA Desktop 前端，同时保留现有后端接口、记忆分组、知识库、技能包和会话历史功能。

**Architecture:** 以主项目 `desktop/frontend/` 为唯一实现基底，只从 `/Users/tianjiashu/uta-redesign-20260701/desktop/frontend/` 提取视觉样式和侧栏图标。`index.html` 只做无行为风险的结构增强，`app.js` 保持接口和渲染逻辑不变，`style.css` 承担深色主题和布局稳定性。

**Tech Stack:** pywebview 桌面前端、原生 HTML/CSS/JS、pytest 前端资产测试、Node.js `--check`、PyInstaller macOS 打包。

---

## File Structure

- Modify: `tests/test_desktop_frontend_assets.py`
  - 增加资产测试，锁住深色主题、离线字体、侧栏图标、底部输入区、记忆页自然展开。
- Modify: `desktop/frontend/index.html`
  - 为左侧导航按钮加入内联 SVG 图标。
  - 保留所有现有 `id`，尤其是 `memoryLongTermGroups`、`memoryConversationShortTerm`、`compressCurrentConversation`。
  - 不加入 Google Fonts。
- Modify: `desktop/frontend/style.css`
  - 迁移深色 Command Deck 变量、侧栏、面板、按钮、输入框、日志、记忆卡片、弹窗样式。
  - 保留现有测试依赖的布局片段，必要时同步更新测试。
- No planned changes: `desktop/frontend/app.js`
  - 除非 CSS 类名兼容必须调整，否则不改 JS。
- Verify/build:
  - `tests/test_desktop_frontend_assets.py`
  - `node --check desktop/frontend/app.js`
  - `.venv/bin/python -m pytest -q`
  - `bash desktop/build/build_macos.sh`
  - `codesign --verify --deep --strict --verbose=1 "dist/UTA Desktop.app"`
  - `shasum -a 256 "dist/UTA Desktop-macos.zip"`

## Task 1: Frontend Asset Tests

**Files:**
- Modify: `tests/test_desktop_frontend_assets.py`

- [ ] **Step 1: Add failing tests for visual migration**

Add these tests to the end of `tests/test_desktop_frontend_assets.py`:

```python
def test_frontend_uses_dark_command_deck_theme_without_remote_fonts():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert "fonts.googleapis.com" not in html
    assert "fonts.gstatic.com" not in html
    assert "--surface-0: #0e0e18;" in css
    assert "--surface-1: #14141f;" in css
    assert "--surface-2: #1a1a28;" in css
    assert "--accent-glow: rgba(116, 123, 255, 0.12);" in css
    assert "background: var(--bg);" in css
    assert "--sans: -apple-system, BlinkMacSystemFont" in css


def test_frontend_sidebar_nav_has_icons_without_breaking_ids():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    for nav_id in [
        "openTaskView",
        "openHistory",
        "openMemory",
        "openKnowledge",
        "openSkills",
        "openSettingsSide",
    ]:
        assert f'id="{nav_id}"' in html
    assert html.count("<svg") >= 6
    assert ".nav svg" in css
    assert ".nav.active::before" in css


def test_frontend_preserves_current_memory_nodes_during_redesign():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    assert 'id="memoryLongTermGroups"' in html
    assert 'id="memoryConversationShortTerm"' in html
    assert 'id="compressCurrentConversation"' in html
    assert "长期记忆总览" in html
    assert "短期会话记忆" in html
    assert "压缩当前会话" in html


def test_frontend_dark_memory_cards_do_not_clip_titles():
    css = (FRONTEND_ROOT / "style.css").read_text(encoding="utf-8")

    assert ".memoryCard {" in css
    assert "overflow-wrap: anywhere;" in css
    assert "#memoryView .memoryPanel {\n  grid-template-rows: auto auto;\n  overflow: visible;" in css
    assert "#memoryView .memoryBlock {\n  max-height: none;\n  overflow: visible;" in css
    assert ".memoryGroupHead" in css
    assert "min-width: 0;" in css
```

- [ ] **Step 2: Run frontend asset tests and confirm they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_desktop_frontend_assets.py -q
```

Expected before implementation: at least one failure from missing dark theme variables or missing nav SVG icons.

## Task 2: Sidebar Icon Structure

**Files:**
- Modify: `desktop/frontend/index.html`
- Test: `tests/test_desktop_frontend_assets.py`

- [ ] **Step 1: Add inline icons while preserving nav button ids**

Replace the six sidebar navigation buttons with this structure:

```html
<button class="nav active" type="button" id="openTaskView"><svg aria-hidden="true" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg><span>任务</span></button>
<button class="nav" type="button" id="openHistory"><svg aria-hidden="true" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg><span>会话历史</span></button>
<button class="nav" type="button" id="openMemory"><svg aria-hidden="true" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a7 7 0 0 1 7 7c0 2.38-1.19 4.47-3 5.74V17a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 0 1 7-7z"/><line x1="9" y1="21" x2="15" y2="21"/></svg><span>记忆</span></button>
<button class="nav" type="button" id="openKnowledge"><svg aria-hidden="true" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg><span>知识库</span></button>
<button class="nav" type="button" id="openSkills"><svg aria-hidden="true" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg><span>技能包</span></button>
<button class="nav" type="button" id="openSettingsSide"><svg aria-hidden="true" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg><span>设置</span></button>
```

- [ ] **Step 2: Run sidebar asset test**

Run:

```bash
.venv/bin/python -m pytest tests/test_desktop_frontend_assets.py::test_frontend_sidebar_nav_has_icons_without_breaking_ids -q
```

Expected: PASS.

## Task 3: Dark Command Deck CSS Migration

**Files:**
- Modify: `desktop/frontend/style.css`
- Test: `tests/test_desktop_frontend_assets.py`

- [ ] **Step 1: Replace theme variables and base shell styles**

Update `:root`, `body`, `.window`, `.titlebar`, `.app`, `.sidebar`, `.brand`, `.nav`, `.main`, `.mainHead`, `.status`, `.button`, `.workspace`, `.panel`, `.stateBox`, `.panelHead`, text inputs, scrollbars and focus styles to use the deep Command Deck variables from the design.

Required CSS fragments:

```css
:root {
  --bg: #08080f;
  --surface: #14141f;
  --surface-0: #0e0e18;
  --surface-1: #14141f;
  --surface-2: #1a1a28;
  --surface-3: #212132;
  --text: #e2e2ec;
  --muted: #8888a2;
  --text-3: #55556a;
  --border: #202030;
  --border-2: #2a2a3d;
  --accent: #747bff;
  --accent-dark: #5c63ff;
  --accent-glow: rgba(116, 123, 255, 0.12);
  --accent-glow-2: rgba(116, 123, 255, 0.25);
  --cyan: #3ddbd9;
  --success: #4ade80;
  --danger: #f87171;
  --warn: #fbbf24;
  --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
}
```

- [ ] **Step 2: Keep existing layout contracts**

Preserve these exact or equivalent contracts because tests and real behavior depend on them:

```css
.chatPanel {
  height: 100%;
  min-height: 0;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  overflow: hidden;
}

#memoryView .memoryPanel {
  grid-template-rows: auto auto;
  overflow: visible;
}

#memoryView .memoryBlock {
  max-height: none;
  overflow: visible;
}
```

- [ ] **Step 3: Run frontend asset tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_desktop_frontend_assets.py -q
```

Expected: all frontend asset tests pass.

## Task 4: Layout and Syntax Verification

**Files:**
- Verify only: `desktop/frontend/index.html`, `desktop/frontend/style.css`, `desktop/frontend/app.js`

- [ ] **Step 1: Check JavaScript syntax**

Run:

```bash
node --check desktop/frontend/app.js
```

Expected: exit code 0 and no output.

- [ ] **Step 2: Run full test suite**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected: all tests pass, with the existing deselected count unchanged or only changed by intentional test selection behavior.

## Task 5: Build and Package

**Files:**
- Build outputs: `dist/UTA Desktop.app`, `dist/UTA Desktop-macos.zip`

- [ ] **Step 1: Build macOS desktop app**

Run:

```bash
bash desktop/build/build_macos.sh
```

Expected:

```text
构建完成：dist/UTA Desktop.app
压缩包：dist/UTA Desktop-macos.zip
```

- [ ] **Step 2: Verify app signature**

Run:

```bash
codesign --verify --deep --strict --verbose=1 "dist/UTA Desktop.app"
```

Expected:

```text
dist/UTA Desktop.app: valid on disk
dist/UTA Desktop.app: satisfies its Designated Requirement
```

- [ ] **Step 3: Record zip SHA256**

Run:

```bash
shasum -a 256 "dist/UTA Desktop-macos.zip"
```

Expected: one SHA256 line for `dist/UTA Desktop-macos.zip`.

## Task 6: Commit Implementation

**Files:**
- Modify: `tests/test_desktop_frontend_assets.py`
- Modify: `desktop/frontend/index.html`
- Modify: `desktop/frontend/style.css`
- Modify if required: `desktop/frontend/app.js`

- [ ] **Step 1: Review diff**

Run:

```bash
git diff -- desktop/frontend/index.html desktop/frontend/style.css desktop/frontend/app.js tests/test_desktop_frontend_assets.py
```

Expected: only dark visual migration, nav icon structure, tests, and necessary compatibility edits are present.

- [ ] **Step 2: Commit implementation**

Run:

```bash
git add desktop/frontend/index.html desktop/frontend/style.css desktop/frontend/app.js tests/test_desktop_frontend_assets.py
git commit -m "feat: migrate desktop to dark command deck"
```

Expected: commit succeeds.

## Self Review

- Spec coverage: covers visual migration, no direct overwrite, real memory nodes, no remote fonts, memory page layout, task page composer, tests and package verification.
- Placeholder scan: no unresolved placeholder markers.
- Type and selector consistency: all IDs match current `index.html`; CSS selectors match existing class names; bridge methods remain untouched.

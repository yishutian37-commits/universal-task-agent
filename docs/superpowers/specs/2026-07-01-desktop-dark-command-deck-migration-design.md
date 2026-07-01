# 桌面端深色 Command Deck 视觉迁移设计

日期：2026-07-01

## 背景

当前主项目的桌面端前端位于 `desktop/frontend/`，已经接入真实 pywebview 后端，包含任务对话、执行详情、会话历史、记忆、知识库、技能包和设置等功能。早上新设计目录 `/Users/tianjiashu/uta-redesign-20260701` 中存在一个独立分支式原型，最新提交为 `feat: redesign desktop UI with dark command deck theme`，主要价值是深色 Command Deck 视觉系统、侧栏图标、按钮状态、面板层级和整体质感。

两个版本不能直接覆盖合并。新设计目录中的 `desktop/frontend/` 相比主项目少了近期新增的长期记忆分组、短期会话记忆压缩入口等真实能力。如果直接替换三文件，会让已实现功能回退。因此本设计采用“迁移视觉，不回退功能”的方案。

## 目标

- 把早上新版的深色 Command Deck 视觉迁入当前真实桌面端。
- 保留当前主项目的真实 DOM 结构和后端接口，不回退记忆、知识库、技能包、会话历史和任务执行。
- 修复并统一记忆页布局，长期记忆总览、经验、负向规则、Skill 候选都不能再出现压扁、遮挡、文字半截显示。
- 让输入框稳定固定在对话面板底部，消息区独立滚动，运行中和完成后位置一致。
- 桌面端离线可用，不依赖 Google Fonts 或任何外部字体资源。
- 变更后重新跑前端资产测试、JS 语法检查、全量测试，并重新打包 `.app`。

## 非目标

- 不重写后端、不改变 pywebview 通信方式。
- 不把桌面端改成 HTTP 服务或 Electron/Tauri。
- 不重新设计 Agent 执行逻辑、RAG 逻辑、记忆压缩策略。
- 不增加新业务功能。
- 不直接引入新设计目录里的静态假数据交互。
- 不把明文 API Key 暴露到前端。

## 推荐方案

采用方案 C：以当前主项目为基底，迁移新版视觉系统。

实施时只从 `/Users/tianjiashu/uta-redesign-20260701/desktop/frontend/` 提取视觉层和少量无行为风险的结构增强：

- 迁入深色 CSS 变量、面板、按钮、状态标签、滚动条、输入框、日志区、记忆卡片等样式。
- 为侧栏导航加入内联图标，但保留原有按钮 `id`，避免破坏 `app.js` 事件绑定。
- 保留当前 `index.html` 中 `memoryLongTermGroups`、`memoryConversationShortTerm`、`compressCurrentConversation` 等新记忆节点。
- 保留当前 `app.js` 的接口调用、渲染函数和 Markdown 渲染逻辑，只做与视觉类名兼容相关的必要小修。
- 不迁入新版的 Google Fonts 链接，字体栈改为系统字体 + `ui-monospace`。

## 页面结构

整体仍是单页桌面控制台：

```text
window
  titlebar
  app
    sidebar
      brand
      nav buttons
      footer
    main
      mainHead
      taskView
      historyView
      memoryView
      knowledgeView
      skillsView
      settings modal
```

本次不改变主要节点，只增强视觉和稳定布局。

## 视觉系统

深色主题使用新版 Command Deck 的方向，但做桌面端约束调整：

- 背景：接近黑色的 `--bg`，区分 `--surface-0` 到 `--surface-3`。
- 文本：主文本、次文本、弱文本分层，避免一片灰。
- 强调色：蓝紫色用于主按钮、活动导航和运行状态；青色只作为辅助高亮，避免页面变成单一紫色。
- 状态色：成功、警告、失败分别使用绿色、黄色、红色，并提供透明底色。
- 圆角：控制在 6 到 12px，保持工具型界面，不做大圆卡片。
- 阴影：尽量少用，主要靠边框、背景层级和状态色区分。

字体使用：

```css
--sans: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
--mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
```

这样打包后的桌面端不需要联网加载字体。

## 任务页布局

任务页保留“对话主区 + 右侧执行详情”：

- 左侧对话面板使用三行 grid：标题、消息区、输入区。
- 消息区 `overflow-y: auto`，负责滚动。
- 输入区固定在面板底部，不随消息运行过程跳到中间或顶部。
- 用户消息靠右，Agent 消息靠左。
- Agent 运行过程只在消息气泡内展示轻量进度，完整步骤保留在右侧执行详情。
- 右侧执行详情包含步骤、日志和 state.json，面板高度由可用空间分配，不挤压对话输入区。

## 记忆页布局

记忆页是本次重点验收页面。

当前记忆页需要保留三组真实内容：

- 长期记忆总览：用户画像、工作习惯、明确偏好、待确认问题、决策记录等分组。
- 短期会话记忆：当前会话摘要、已压缩位置、近期保留消息数量、手动压缩按钮。
- 运行沉淀：任务历史、经验、负向规则、Skill 候选。

布局规则：

- `#memoryView` 使用自然撑开布局，不复用固定高度裁切策略。
- `#memoryView .memoryPanel` 使用 `grid-template-rows: auto auto`。
- `#memoryView .memoryBlock` 不设置 `max-height: 300px`，普通记忆页内容自然展开。
- 长期记忆总览跨两列或全宽展示，内部使用 `auto-fit` 网格，每个分组卡片最小宽度不低于 260px。
- 经验、负向规则、Skill 候选的卡片标题必须允许换行，不能被面板头部或边框遮住。
- 知识库和技能包页面可以继续使用可滚动面板，避免大列表撑爆页面。

## 知识库和技能包

知识库和技能包不改数据逻辑，只统一视觉：

- 输入框、按钮、空状态、来源列表使用深色变量。
- 文档列表和技能卡片使用同一套 `.memoryCard` 视觉。
- 错误列表和加载问题使用失败色边框或标签，但不改变原始错误文案。

## 设置弹窗

设置弹窗保留当前字段：

- Base URL
- 模型
- API Key
- SSL Verify
- 清除 Key
- 保存

视觉上迁移深色遮罩、面板、输入框和按钮。`get_settings()` 仍只返回 `has_api_key`，不回传明文 Key。

## 风险和处理

| 风险 | 处理 |
|---|---|
| 直接覆盖导致记忆功能回退 | 以主项目为基底，只迁移视觉 |
| 深色主题影响可读性 | 主文本、弱文本、边框、背景层级分别定义，跑截图检查 |
| 内联 SVG 影响按钮事件 | 保留按钮 `id`，只在按钮内部增加图标 |
| 外部字体导致离线不可用 | 不引入 Google Fonts |
| 记忆页再次被裁切 | 为 `#memoryView` 写资产测试，断言自然撑开规则 |
| Markdown 渲染回退 | 不改 `renderMarkdown()` 主逻辑，只检查样式 |

## 验收标准

功能验收：

- 任务页能发送普通对话和执行任务。
- 右侧能显示执行步骤、实时日志、state.json。
- 会话历史能打开并回填消息。
- 记忆页能显示长期记忆分组、短期会话记忆、任务历史、经验、负向规则、Skill 候选。
- 知识库页和技能包页仍可打开，不报 JS 错误。

视觉验收：

- 任务页、记忆页、知识库页、技能包页都使用深色 Command Deck 风格。
- 输入框固定在对话面板底部。
- 记忆页卡片不压扁、不遮挡、不出现半截文字。
- 所有按钮文字完整显示。
- 小窗口下侧栏和内容区可正常折叠为单列。

测试验收：

- `tests/test_desktop_frontend_assets.py` 通过。
- `node --check desktop/frontend/app.js` 通过。
- `.venv/bin/python -m pytest -q` 通过。
- `bash desktop/build/build_macos.sh` 打包成功。
- `codesign --verify --deep --strict --verbose=1 "dist/UTA Desktop.app"` 通过。
- 生成 `dist/UTA Desktop-macos.zip` 并记录 SHA256。

## 实施顺序

1. 增加或更新前端资产测试，先覆盖深色主题、侧栏图标、输入区底部固定、记忆页自然展开、禁止 Google Fonts。
2. 更新 `desktop/frontend/index.html`，只做结构增强：侧栏图标、必要容器类名；保留所有真实节点和 `id`。
3. 更新 `desktop/frontend/style.css`，迁移深色视觉系统并修正所有页面布局。
4. 运行前端资产测试和 JS 语法检查。
5. 跑全量测试。
6. 打包 `.app`。
7. 做签名校验和压缩包哈希。
8. 提交实现改动。

## 自检结论

本设计范围集中在桌面端前端视觉迁移，不改变后端功能和数据模型。所有关键真实功能均以主项目现状为准，新设计目录只作为视觉参考。记忆页排版问题被列为明确验收项，避免再次出现“越改越乱”的情况。

# UTA 整体架构可视化设计

## 背景

UTA（Universal Task Agent）是一个学习型本地 Agent 框架，已经积累了多个相对独立的子系统：核心 Agent Loop、工具层、记忆系统、RAG 知识库、搜索/天气 Provider、桌面端和 FastAPI 接口。随着功能增加，项目整体结构对新成员或回顾者不够直观。需要一份可交互的整体架构图，帮助快速理解模块划分、主执行链路和数据/记忆流转。

## 目标

为 UTA 项目生成一个**本地可打开的 HTML 交互式架构图**，具备以下能力：

1. 以网络图形式展示项目主要模块及其关系。
2. 支持 4 个视图切换：整体模块全景、核心 Agent Loop 执行链路、桌面端与后端交互、数据/记忆流转。
3. 点击节点可在侧边栏查看模块职责、关键文件和依赖说明。
4. 无需安装依赖，单个 HTML 文件本地双击即可打开。

## 方案选择

考虑过三种方案：

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| 轻量单文件：Mermaid + 标签页 | 实现简单，易维护 | 交互有限，无法拖拽缩放节点 | 未选 |
| **富交互图谱：Cytoscape.js + 侧边详情面板** | 可拖拽、缩放、点击查看详情，体验好 | 文件稍大，节点数据需手动维护 | **选用** |
| 架构文档页：HTML 文档 + 多图 + 文字 | 适合作为长期文档 | 不够直观，缺少交互 | 未选 |

最终选择 **Cytoscape.js 富交互图谱**，因为用户明确希望“看一下它长什么样”，交互式网络图最符合直觉。

## 详细设计

### 输出产物

- 文件路径：`docs/uta-architecture.html`（或项目根目录 `architecture.html`，最终由实现阶段确定）。
- 技术栈：纯 HTML + CSS + JavaScript，Cytoscape.js 通过 CDN 引入。
- 数据：节点和边直接内嵌在 HTML 的 `<script>` 中，便于后续手工更新。

### 页面布局

```text
┌─────────────────────────────────────────────────────────────┐
│  [整体模块] [Agent Loop] [桌面端交互] [数据流转]  [适应屏幕]   │  ← 顶部工具栏
├───────────────────────────────┬─────────────────────────────┤
│                               │                             │
│                               │  节点详情                    │
│      Cytoscape 网络图          │  ────────────               │
│      （可缩放 / 拖拽）          │  名称                        │
│                               │  类型                        │
│                               │  职责                        │
│                               │  关键文件                    │
│                               │  输入 / 输出                 │
│                               │  依赖                        │
│                               │                             │
└───────────────────────────────┴─────────────────────────────┘
```

### 视觉编码

- **颜色**：按子系统区分。
  - `core`：蓝色
  - `tools`：绿色
  - `memory_providers` / `memory`：紫色
  - `rag`：橙色
  - `desktop`：青色
  - `api`：灰色
  - `llm`：红色
  - `search_providers` / `weather_providers`：黄色
  - `skills`：粉色
  - 用户 / 外部系统：深色/黑色
- **形状**：
  - 核心组件：圆角矩形
  - 数据存储/持久化：圆柱
  - 外部服务/用户：菱形
  - 执行步骤：六边形
- **边**：
  - 实线箭头：直接调用
  - 虚线箭头：数据/事件流
  - 双向箭头：前后端交互

### 四个视图

#### 视图 1：整体模块全景

展示顶层模块及其调用关系：

- 用户输入
- `main.py` / `api/server.py` / `desktop/api.py`
- `core/`（TaskParser、Planner、Loop、Router、Executor、Verifier、Reflection、SkillLoader）
- `tools/`（file_tool、text_tool、table_tool、search_tool、code_tool、geo_tool、history_tool、report_tool 等）
- `memory_providers/`（JsonMemoryProvider）
- `rag/`（KB、store、retrieval、generation）
- `llm/`（LLMClient）
- `search_providers/`、 `weather_providers/`
- `skills/`（Markdown Skill + vendor 包）
- `desktop/`（前端、api、runner、chat_router、conversation_store 等）
- `outputs/`（states、logs）

#### 视图 2：核心 Agent Loop 执行链路

线性展示一次任务从输入到输出的完整链路：

```text
User Input
  → TaskParser
  → SkillLoader
  → Planner
  → Agent Loop
  → Router
  → Executor
  → Verifier
  → Reflection / Replan
  → Memory
  → Final Output
```

同时标注：
- `AgentState` 在各步骤间的传递
- 失败时的单步重试和 Replan 路径
- 复杂任务的 `[ ]/[x]` 步骤清单执行

#### 视图 3：桌面端与后端交互

展示桌面端各层如何调用 Agent 核心：

- 桌面前端（HTML/JS，聊天消息流 + 右侧详情区）
- `desktop/api.py`（FastAPI 桥接）
- `desktop/runner.py`（后台任务执行）
- `desktop/chat_router.py`（对话路由）
- `core/` 主链路
- `rag/` 知识库接口
- `memory/` 长期记忆
- 打包产物 `dist/UTA Desktop.app`

#### 视图 4：数据/记忆流转

聚焦数据存储和读写关系：

- 短期记忆：`AgentState` → `outputs/states/<task_id>_state.json`
- 日志：`outputs/logs/<task_id>.log`
- 长期 JSON Memory：`memory/task_history.json`、`lessons.json`、`negative_rules.json`、`skill_candidates.json`、`user_profile.json`
- RAG 知识库：文档 → chunker → embedder → `SQLite` 向量存储 → retrieval → generation
- 桌面端运行数据：`~/.uta/`

### 交互行为

- 点击节点：右侧详情面板展示该节点的元数据。
- 点击边：右侧面板展示关系说明。
- 视图切换按钮：切换不同的节点/边数据集，默认重置布局。
- 适应屏幕按钮：将图缩放至完整可见。
- 鼠标滚轮：缩放画布。
- 拖拽空白处：平移画布。
- 拖拽节点：手动调整布局。

### 节点详情字段

每个节点至少包含：

- `id`：唯一标识
- `label`：显示名称
- `type`：模块类型（core / tool / memory / rag / desktop / api / llm / provider / skill / storage / user）
- `description`：一句话职责
- `files`：关键文件路径数组
- `inputs`：输入说明
- `outputs`：输出说明
- `dependencies`：依赖的模块/服务

## 验收标准

1. 生成的 HTML 文件可以在 macOS 上通过双击直接打开。
2. 页面顶部有 4 个视图切换按钮，切换后网络图正确渲染。
3. Cytoscape 图支持缩放、拖拽画布、拖拽节点。
4. 点击任意节点，右侧详情面板显示该节点的 `description`、`files`、`inputs`、`outputs`、`dependencies`。
5. 节点颜色、形状与“视觉编码”一节一致。
6. 四个视图分别覆盖：整体模块全景、核心 Agent Loop 执行链路、桌面端与后端交互、数据/记忆流转。
7. 不引入额外构建步骤或 npm 依赖，所有资源通过 CDN 加载。

## 后续维护

由于节点数据内嵌在 HTML 中，当项目新增或调整模块时，需要手动更新 HTML 里的节点/边数组。如果后续架构变化频繁，可以考虑：

- 用 Python 脚本从 `core/`、`tools/`、`desktop/` 等目录自动生成节点元数据；
- 或将节点数据拆出为独立的 `architecture-data.json`。

本次实现保持简单，先交付单个 HTML 文件。

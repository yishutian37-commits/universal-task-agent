# UTA 桌面端应用 · 架构基线

> 文档版本：**Baseline v1.0**（原 v1.0 前瞻设计改写）
> 对应 PRD：UTA PRD v6.1（Final Start Version）
> 对应实现：`desktop/`（tag `v1.2-rag-desktop-integrated` 起）
> 记录日期：2026-07-08
> 状态：现状记录 + 演进 backlog

---

## 0. 文档定位

本文档原为"v2.0 桌面版前瞻设计"，起草时（2026-06-20）桌面版尚未实现。实际项目演进远超预期：截至 2026-07，桌面版已完整实现并通过 PyInstaller 打包分发（`dist/UTA Desktop-macos.zip`）。

因此本文档改写为**现状基线**：记录已实现的架构、打包链路、能力边界，并标注尚未覆盖的项为演进 backlog。不再作为"待实现的设计"。

---

## 1. 已实现的整体架构

### 1.1 进程模型

pywebview 单进程方案，与原设计一致：

```
双击 UTA Desktop.app
  ↓
启动器（desktop/build/uta_app.py）
  ├─ multiprocessing.freeze_support()  ← 防止 torch/numba spawn 子进程无限弹窗
  └─ desktop/app.py:main()
       ├─ 创建 DesktopAPI 实例（持有所有后端能力）
       ├─ webview.create_window("UTA Desktop", frontend/index.html, js_api=api)
       └─ webview.start()
            ├─ 原生 macOS 窗口（WKWebView 渲染前端）
            └─ 前端 JS 通过 window.pywebview.api.<method> 调后端
```

任务执行走后台线程（`desktop/runner.py` 的 `TaskRunner`），通过 `window.evaluate_js("window.onProgress(...)")` 把 Loop 每步进度推给前端。

### 1.2 实际能力范围（远超原设计）

原设计假设 6 个 API 方法 + 单页控制台。实际实现：

| 维度 | 原设计 | 实际 |
|---|---|---|
| DesktopAPI 方法数 | 6 | **23** |
| 前端规模 | ~200 行单页 | **2600 行**完整应用 |
| 任务类型 | 仅 summarize | summarize / data_analysis / research / complex_task / history_query |
| 对话能力 | 无 | 完整多轮对话 + 自动压缩 |
| RAG 知识库 | 无 | 摄入/检索/问答/删除 |
| 记忆面板 | 无 | 长期记忆/技能/历史三面板 |
| 打包分发 | 设计中 | 已产出 `.app` + `.zip` |

### 1.3 DesktopAPI 全部方法（23 个）

```
配置:      get_settings, save_settings
示例:      load_example
任务:      run_task, get_result, cancel_task
历史:      list_runs, get_run          ← 2026-07-08 改为读 memory/task_history.json
对话:      run_chat_message, sync_chat_result, list_conversations,
           new_conversation, get_conversation, compress_conversation
记忆:      get_memory_overview
技能:      get_skill_overview
RAG:       rag_stats, rag_list_docs, rag_ingest, rag_query, rag_ask, rag_delete
```

---

## 2. 后端（desktop/）模块清单

| 模块 | 职责 |
|---|---|
| `app.py` | pywebview 窗口入口；`freeze_support` 防子进程重启 |
| `api.py` | DesktopAPI 类，23 个方法的实现，对话上下文组装、压缩编排 |
| `runner.py` | TaskRunner 后台线程，调 `main.run_task`，事件推送 |
| `chat_router.py` | 区分"直接回答 / 普通聊天 / 任务执行"三种路由 |
| `conversation_store.py` | 对话持久化（`~/.uta/conversations/`） |
| `memory_compression.py` | 会话压缩策略（token 估算、触发阈值） |
| `memory_store.py` | 长期记忆读写（`~/.uta/memory/`） |
| `skill_store.py` | 技能目录扫描与概览 |
| `history_store.py` | re-export `core.history_store.HistoryStore`（读 task_history.json） |
| `settings_store.py` | LLM 配置读写（`~/.uta/config.json`），apply_to_environment 注入 os.environ |
| `rag_client.py` | 调用 RAG 子系统的 HTTP/进程客户端 |
| `paths.py` | `resource_path`（打包后定位 Resources）+ `uta_home`（`~/.uta`） |

### 2.1 任务进度事件流

`main.run_task(on_progress=...)` 在 Loop 关键节点回调，经 `TaskRunner._emit_progress` → `window.evaluate_js`。事件 type：

`task_received` → `parsed` → `skill_matched` → `plan_created` → (`step_started` → `tool_selected` → `tool_executed` → `verified` → `step_done` | `reflection`)× → `memory_saved` → `task_completed`

---

## 3. 前端（desktop/frontend/）

| 文件 | 行数 | 说明 |
|---|---|---|
| `index.html` | 303 | 应用骨架，多视图容器 |
| `app.js` | 1114 | 全部交互逻辑，原生 JS 无框架 |
| `style.css` | 1183 | 样式（含暗色"命令甲板"主题） |

前端通过 `callApi("<method>", ...args)` 统一调后端（封装 pywebview 桥），不写 fetch/HTTP。视图包括：任务运行、运行历史、长期记忆、技能、对话、RAG 知识库、设置。

---

## 4. 打包链路（已实现）

### 4.1 入口与配置文件

- 入口：`desktop/build/uta_app.py`（先 `freeze_support`，再调 `desktop.app.main`）
- 配置：`desktop/build/uta_app.spec`（PyInstaller）
- 脚本：`desktop/build/build_macos.sh`（一键构建）

### 4.2 .spec 关键配置

`datas` 打进 Resources 的资源：

| 源 | 目标 | 作用 |
|---|---|---|
| `desktop/frontend` | `frontend` | 前端静态资源 |
| `examples` | `examples` | 示例数据（load_example 读） |
| `skills` | `skills` | Skill 定义（SkillLoader 读） |
| `docs` | `docs` | 文档 |
| `memory` | `memory` | 初始 memory 模板 |
| `README.md`, `CHANGELOG.md` | `.` | 根目录文档 |
| 源码目录（main.py/api/core/desktop/llm/...） | `source/<name>` | **源码也冻进包，供学习者查看** |

`hiddenimports`：显式声明所有模块（pywebview Cocoa 后端 + 全部 core/tools/rag/search/weather 模块），避免运行时动态 import 找不到。

`BUNDLE` info_plist：`CFBundleShortVersionString=2.0.0`、`LSMinimumSystemVersion=11.0`、`NSHighResolutionCapable=True`、`bundle_identifier=com.uta.desktop`。

### 4.3 构建脚本流程（build_macos.sh）

```
1. 定位 venv python
2. pytest -q               ← 带伤不许打包
3. 检查 pywebview/pyinstaller 依赖存在
4. PyInstaller --clean 打包到 dist/UTA Desktop.app
5. ditto 打 zip → dist/UTA Desktop-macos.zip
```

### 4.4 运行产物落地（脱离代码仓）

打包后无代码仓，运行时文件全部落 `~/.uta/`（`.app` 内部只读）：

| 文件 | 位置 |
|---|---|
| LLM 配置 | `~/.uta/config.json` |
| 对话记录 | `~/.uta/conversations/` |
| 长期记忆 | `~/.uta/memory/` |
| 任务历史 | `~/.uta/memory/task_history.json` |

> **2026-07-08 变更**：移除了 `~/.uta/outputs/states/*.json` 与 `~/.uta/outputs/logs/*.log` 落盘。任务历史统一由 JsonMemoryProvider 写入 `task_history.json`（含完整 final_output），history 功能改读此处。左侧执行过程的实时事件流已覆盖"看懂 Agent Loop"的学习价值。

---

## 5. 开发与运行

### 5.1 开发模式（不打包）

```bash
.venv/bin/python desktop/app.py    # debug=True，窗口直接加载 desktop/frontend/
```

改完前端刷新窗口即可，无需重新打包。

### 5.2 完整打包

```bash
.venv/bin/python -m pip install -r requirements-desktop.txt
bash desktop/build/build_macos.sh
# 产物：dist/UTA Desktop.app + dist/UTA Desktop-macos.zip
```

### 5.3 依赖分离

- `requirements.txt`：CLI 学习者（仅 pytest）
- `requirements-desktop.txt`：桌面版（含 pywebview/pyinstaller，引用 `.[desktop]`）

---

## 6. 演进 Backlog

尚未覆盖、可后续增强的项：

| 项 | 说明 | 优先级 |
|---|---|---|
| api_key 加密存储 | 当前 `~/.uta/config.json` 明文存 key；可升级 macOS Keychain | 低 |
| 任务取消 | `cancel_task` 当前返回"不支持"；TaskRunner 线程不可中断 | 中 |
| 多任务并发 | 当前单任务（运行中再点运行被禁用） | 低 |
| 应用图标 | `uta_app.spec` 中 `icon=None`，用系统默认 | 低 |
| 分发包签名 | 当前未做 codesign（`codesign_identity=None`），用户首次打开需手动允许 | 中 |
| 包体积优化 | 当前 214MB（含 RAG/torch 等重库），可考虑拆分或懒加载 | 中 |

---

## 7. 与 PRD 主线的关系

- PRD 第 7 节"复杂前端 / 先 CLI"：CLI 优先在 v0.x-v1.0 维持不变；桌面化是独立演进线，已实现。
- PRD 第 23 节 Backlog"简单 Web UI（v1.2）"：已被桌面版吸收并远超其范围。
- `core/` 的唯一为桌面版而设的改动是 Loop 的可选 `on_progress` 回调；其余桌面能力都在 `desktop/` 层内，CLI 不受影响。

# UTA 桌面端应用设计

> 文档版本：**Design v1.0**
> 对应 PRD：UTA PRD v6.1（Final Start Version）
> 桌面版里程碑：**v2.0**（V1.0 CLI 学习版之后的独立里程碑）
> 设计日期：2026-06-20
> 状态：待审阅

---

## 0. 决策汇总

本设计基于五项已确认决策：

| # | 决策项 | 结论 |
|---|---|---|
| 1 | 定位 | 独立 v2.0 桌面版，CLI 保留，前后端打包成可直接双击运行的 `.app` |
| 2 | 技术栈 | Python 后端 + Web 前端，pywebview 提供原生窗口（无 FastAPI、无 HTTP） |
| 3 | LLM 接入 | 云端 API + 应用内设置页填 Key，脱离本地代理依赖 |
| 4 | 前端形态 | 单页控制台，SSE 式实时进度（通过 pywebview 事件推送） |
| 5 | 与主线衔接 | 架构按完整 v1.0 预留（Memory/Skill/Verifier 重试接口），首版只打通当前 v0.4 总结任务 |

> 关于第 2 项的澄清：桌面版最终选定 **pywebview 单进程方案**，不使用 FastAPI/HTTP。后端就是窗口所在的 Python 进程本身，前后端通过 pywebview 的 JS-Python 桥通信。详见第 1 节。决策汇总表与澄清无冲突。

---

## 1. 整体架构（进程模型 + 目录）

### 1.1 进程模型

桌面版是一个**自包含 `.app`**。用 pywebview 作为窗口层：启动一个原生 macOS 窗口，窗口内是系统 WKWebView 渲染前端，同时窗口所在的 Python 进程**直接就是后端**——前端通过 pywebview 的 JS-Python 桥（`window.pywebview.api.xxx`）调后端，不需要单独起 HTTP 服务，也不需要选端口。

```
双击 UTA Desktop.app
  ↓
启动器进程（PyInstaller 冻结的 Python）
  ├─ 创建一个 pywebview 窗口，加载打包进来的 desktop/frontend/index.html
  ├─ 窗口进程内直接持有：core/ llm/ tools/ 的运行时
  └─ 前端 JS 调 window.pywebview.api.run_task(...)
       → 后端在 Python 侧执行 run_task
       → 通过回调把每步进度 push 回前端
       → 前端实时刷新计划/步骤/日志
```

### 1.2 为什么是 pywebview 单进程方案

技术栈选型阶段对比了三种方案，最终选定 pywebview：

| 维度 | pywebview（选定） | HTTP 后端 + 浏览器 | Tauri/Electron + Python sidecar | 纯 Python GUI（PyQt/Tkinter） |
|---|---|---|---|---|
| 用户体验 | 原生窗口，像真正的 .app | 开浏览器标签页，较松散 | 最接近原生 | 原生但 UI 表现力弱 |
| 端口/网络 | 无需端口，无占用冲突 | 要选端口，可能被占用 | sidecar 进程 + 端口 | 无 |
| 进程数 | 单进程 | 后端进程 + 浏览器 | 多进程 | 单进程 |
| 前后端通信 | JS-Python 桥（直调） | HTTP/SSE | IPC | Python 回调 |
| 工具链复杂度 | 低（纯 Python） | 低 | 高（Rust/Node） | 低 |
| 打包复杂度 | PyInstaller + pywebview | PyInstaller | 高 | PyInstaller |

pywebview 在"原生体验 + 低复杂度 + 与现有 Python 代码无缝衔接"上平衡最好，且符合 PRD"每文件能看懂、避免被前端分散精力"的学习导向。

### 1.3 流式进度的处理

JS 直接调 `api.run_task()` 会阻塞等返回。要实现"逐步看到进度"，用一个后台线程跑 `run_task`，每步通过 pywebview 的 `window.evaluate_js()` 主动把进度推给前端；前端有全局 `onProgress(event)` 回调更新界面。这样既保持"单进程、无端口"的简洁，又能实时看 Loop 过程（正是"看懂 Agent Loop"的学习价值所在）。

### 1.4 目录结构

桌面版作为新增层，不侵入现有结构：

```
desktop/
├─ app.py              ← pywebview 窗口入口：建窗口、注册 API 类
├─ api.py              ← 暴露给前端 JS 的 Python API 类（run_task/get_settings/save_settings...）
├─ runner.py           ← 后台线程跑 run_task，通过回调推进度
├─ settings_store.py   ← 读写 ~/.uta/config.json
├─ frontend/
│  ├─ index.html
│  ├─ app.js           ← 单页控制台（调 window.pywebview.api）
│  ├─ style.css
│  └─ vendor/marked.min.js   ← Markdown 渲染库（单文件）
├─ build/
│  ├─ uta_app.py       ← PyInstaller 入口（调 app.py 启动窗口）
│  ├─ uta_app.spec     ← 把 frontend/ 冻进 .app 的资源配置
│  ├─ icon.icns        ← 应用图标
│  └─ build_macos.sh   ← 一键构建脚本
└─ README.md           ← 桌面版说明
```

### 1.5 对 core/ 的改动（最小化原则）

`core/` 唯一改动：给 `run_minimal_loop` 加一个可选 `on_progress` 回调。不传时（CLI、测试）行为完全不变。这是"架构预留"的落点：主线 v0.5→v1.0 继续推进，回调是纯增量。

```python
# core/loop.py —— 现有签名加一个可选参数
def run_minimal_loop(state, tool_registry=None, on_progress=None) -> AgentState:
    # 每个关键节点：
    if on_progress:
        on_progress({"type": "step_started", "step_id": step.step_id, "goal": step.goal})
    ...
```

---

## 2. 后端 API 设计

`api.py` 不碰业务逻辑，只把前端请求转给现有的 `run_task` / `config`，把结果转成前端好用的 dict。

### 2.1 对前端暴露的 API 方法

通过 `window.pywebview.api.xxx` 调用：

| 方法 | 入参 | 返回 | 作用 |
|---|---|---|---|
| `get_settings()` | 无 | `{llm_base_url, llm_model, has_api_key, ssl_verify}` | 读 `~/.uta/config.json`。`has_api_key` 是布尔，**不把明文 key 回传前端** |
| `save_settings(base_url, model, api_key, ssl_verify)` | 见左 | `{ok: bool, error?}` | 写配置到 `~/.uta/config.json`；明文 key 只落本地配置文件，不进代码仓 |
| `load_example(category)` | `"summarize"` | `{title, input}` | 从打包进来的 `examples/summarize_example.txt` 取示例文本 |
| `run_task(user_input)` | 任务字符串 | `{task_id}` | 在后台线程启动一次任务，立即返回 task_id；进度走事件推送，不靠返回值 |
| `cancel_task(task_id)` | task_id | `{ok}` | 首版返回"不支持取消"，接口先留 |
| `get_result(task_id)` | task_id | `{status, final_output, state}` | 拿某次任务的最终状态 |

**明文 key 的边界**：`get_settings` 永远只回 `has_api_key` 布尔值，前端设置页只在"用户主动修改"时才把新 key 传回 `save_settings`。这避免 key 在 JS 层随意流转。

### 2.2 进度事件（后端 → 前端）

后台线程跑 `run_task`，每到一个关键节点就 push 一个事件，通过 `window.evaluate_js` 调用前端全局 `onProgress(event)`。统一信封：

```json
{ "type": "...", "task_id": "...", "data": {...} }
```

事件类型与现有 `build_log_lines` 的日志节点一一对应，把人类可读日志升级成机器可消费的事件流：

| type | data | 触发时机 |
|---|---|---|
| `task_received` | `{task_id, user_input}` | 任务开始 |
| `parsed` | `{task_type, intent}` | TaskParser 完成 |
| `plan_created` | `{steps: [{step_id, goal}]}` | Planner 出计划 |
| `step_started` | `{step_id, goal}` | 某步开始 |
| `tool_selected` | `{step_id, tool_name, reason}` | Router 选了工具 |
| `tool_executed` | `{step_id, success, tool_name}` | Executor 执行完 |
| `verified` | `{step_id, passed, failed_reasons}` | Verifier 判完 |
| `step_done` | `{step_id, status}` | 某步结束 |
| `task_completed` | `{status, final_output}` | 整个任务结束 |
| `error` | `{message}` | 任何意外（如 LLM 连不上） |

同一个 Loop 走完，CLI 打日志、桌面端推事件，**数据源是同一个 `on_progress` 回调**。

### 2.3 配置注入到 LLMClient

当前 `config.py` 在 import 时就 `load_env_file()` 读 `.env`。桌面版不能依赖代码仓里的 `.env`（打包后根本没有仓），所以 `settings_store` 启动时把 `~/.uta/config.json` 的值写进 `os.environ`（`LLM_API_KEY` 等），再 import `llm_client`。这样 `llm_client` 一行不改，依然从 `os.getenv` 取值。

---

## 3. 前端单页控制台布局

### 3.1 布局总览

单页面，三块区域，一条任务从输入到结果的全过程都在这页内呈现：

```
┌─ UTA Desktop ───────────────────────────────────────────────┐
│ [设置 ⚙]                                          [状态: 就绪]│
├──────────────────────────────────────────────────────────────┤
│  ┌─ 任务输入 ───────────────────────────────────────────┐    │
│  │ [文本框：粘贴/输入任务]                              │    │
│  │ [载入示例 ▾]                              [▶ 运行]   │    │
│  └─────────────────────────────────────────────────────┘    │
├───────────────────────┬──────────────────────────────────────┤
│  执行过程（左）        │  最终结果（右）                        │
│ ┌──────────────────┐ │ ┌──────────────────────────────────┐ │
│ │ 计划              │ │ │ 最终报告                          │ │
│ │ 1 读取文本   ✓    │ │ │ (Markdown 渲染)                   │ │
│ │ 2 生成摘要   ⏳   │ │ │                                  │ │
│ │ 3 输出报告   …    │ │ │                                  │ │
│ ├──────────────────┤ │ ├──────────────────────────────────┤ │
│ │ 实时日志          │ │ │ state.json (可折叠)              │ │
│ │ [Main] received   │ │ │ { task_id, status, results... }  │ │
│ │ [Planner] 3 steps │ │ │                                  │ │
│ │ [Verifier] passed │ │ │                                  │ │
│ └──────────────────┘ │ └──────────────────────────────────┘ │
└───────────────────────┴──────────────────────────────────────┘
```

### 3.2 三块区域各自的行为

**① 顶部输入区**
- 文本框输入任务；`载入示例` 按钮调 `load_example("summarize")` 把示例文本灌进框
- 点 `运行` → 调 `run_task(user_input)`，拿回 task_id，随即把界面切成"运行中"状态：输入区只读，运行键变 `停止`
- 顶部右上角小状态灯：就绪 / 运行中 / 已完成 / 失败

**② 左侧执行过程（"看懂 Agent Loop"的核心）**

分上下两栏：

- **计划栏**：收到 `plan_created` 事件后画出步骤列表，每步一个图标 + goal 文本。图标随事件流转：`…`(pending) → `⏳`(step_started) → `✓`(step_done, status=completed) / `✗`(failed)。点某步可展开看它对应的 tool_selected / tool_executed / verified 事件详情。
- **日志栏**：一条滚动文本流，每收一个事件追加一行（格式沿用现有 `build_log_lines` 的人类可读风格，逐行实时出现而不是最后一次性打印）。

**③ 右侧结果区**
- **最终报告**：收到 `task_completed` 后，用 Markdown 渲染 `final_output`（v0.4 的 `report_tool` 输出本来就是 Markdown，天然适配）。
- **state.json**：可折叠的原始状态展示，调 `get_result(task_id)` 拿完整 state，`JSON.stringify(..., null, 2)` 展示。折叠默认收起，给想看细节的学习者展开。

### 3.3 关键交互细节

| 场景 | 行为 |
|---|---|
| 运行中再次点运行 | 禁用，避免并发任务把进度流搅乱（首版单任务） |
| 进度事件到来 | `onProgress` 更新计划栏图标 + 追加日志行，日志栏自动滚到底 |
| 任务完成 | 右侧填报告，状态灯转绿/红，输入区恢复可编辑，`运行`键恢复 |
| 没配 Key 就运行 | `run_task` 立即返回，前端弹"请先到设置填 API Key" |
| 设置页 | 点齿轮 → 浮层：base_url / model / api_key(password 框) / ssl_verify 开关 → 保存调 `save_settings` |

### 3.4 技术选型（刻意保持薄）

- **原生 HTML/CSS/JS，无框架**。单页逻辑用几十行 JS 就够，不引入构建链。Markdown 渲染用 marked.js（单文件）。
- 前端调后端统一走 `window.pywebview.api.xxx`（pywebview 桥），不写 fetch、不碰 HTTP。
- 整个 `frontend/` 三个源文件（index.html / app.js / style.css），和 PRD"每文件 ≤200 行、能看懂"的学习目标一致。

---

## 4. 打包成 `.app` 的完整链路

### 4.1 `.app` 内部结构（构建产物）

```
UTA Desktop.app/Contents/
├─ Info.plist              ← 应用名、图标、最低 macOS 版本
├─ MacOS/
│  └─ uta_app              ← PyInstaller 生成的可执行入口
└─ Resources/
   ├─ icon.icns            ← 应用图标
   ├─ frontend/            ← 静态前端资源（spec 里用 datas 打进来）
   │  ├─ index.html
   │  ├─ app.js
   │  ├─ style.css
   │  └─ vendor/marked.min.js
   └─ examples/
      └─ summarize_example.txt   ← 载入示例要用
```

> core/ llm/ tools/ 不进 Resources——它们是 Python 模块，由 PyInstaller 编译进可执行文件本身（`uta_app`），`import core.loop` 在打包后照样能用。

### 4.2 PyInstaller spec 关键配置（`desktop/build/uta_app.spec`）

```python
# 精简示意，实际构建脚本补全路径
a = Analysis(
    ['uta_app.py'],                    # 入口
    pathex=['.'],                      # 让 PyInstaller 找到 core/ llm/ tools/
    datas=[
        ('desktop/frontend', 'frontend'),
        ('examples', 'examples'),
    ],
    hiddenimports=[
        'webview.platforms.cocoa',     # pywebview 的 macOS 后端，PyInstaller 常漏
        'core.loop', 'core.state',     # 动态 import 的模块显式声明
        'llm.llm_client',
    ],
)
exe = EXE(a.scripts, a.binaries, a.datas, name='uta_app',
          console=False)               # console=False：不弹黑色终端窗口
app = BUNDLE(exe, name='UTA Desktop.app',
             icon='desktop/build/icon.icns',
             info_plist={
                 'CFBundleName': 'UTA Desktop',
                 'CFBundleShortVersionString': '2.0.0',
                 'LSMinimumSystemVersion': '11.0',
                 'NSHighResolutionCapable': True,
             })
```

### 4.3 两个最容易踩的打包坑（写进文档"打包注意事项"）

1. **`hiddenimports`**：pywebview 的 Cocoa 后端是运行时动态加载的，PyInstaller 静态分析扫不到，不显式声明打包后启动直接崩。core/llm/tools 里凡是 `importlib` 或字符串拼接 import 的也要列进来。
2. **`console=False`**：默认会带一个终端窗口，桌面应用不需要。但**开发期调试要切回 `console=True`**，否则看不到 traceback——构建脚本里留一个 `--debug` 开关。

### 4.4 配置与运行产物落地（脱离代码仓）

打包后没有代码仓，所有运行时文件必须落到**用户目录**，不能往 `.app` 内部写（macOS 代码签名后 `.app` 内部只读）：

| 文件 | 落地位置 | 作用 |
|---|---|---|
| LLM 配置 | `~/.uta/config.json` | base_url / model / api_key / ssl_verify |
| 任务产物 | `~/.uta/outputs/states/` | 每次 task 的 state.json（替代现有 `outputs/`） |
| 运行日志 | `~/.uta/outputs/logs/` | 每次 task 的 .log |

**这意味着桌面版运行时要把 state/log 写到 `~/.uta/outputs/`**——但不改 `run_task` 函数的默认值（那会影响 CLI）：`desktop/runner.py` 调 `run_task` 时显式传 `output_root=Path.home()/".uta"/"outputs"`，CLI 路径继续用 `outputs/`。`run_task` 已支持 `output_root` 参数，所以**对 main.py / run_task 零改动**。

### 4.5 `~/.uta/config.json` 的结构

```json
{
  "llm_base_url": "https://open.bigmodel.cn/api/paas/v4",
  "llm_model": "glm-5.2",
  "llm_api_key": "sk-...",
  "llm_ssl_verify": true
}
```

- 默认值给云端 GLM 官方端点（对应"云端 API"决策），用户首次启动在设置页填自己的 Key。
- api_key 明文存在这个文件里。**声明**：这是本地明文存储，等同浏览器保存密码的本地存储方式；后续可升级到 macOS Keychain，但 v2.0 首版不做（进 Backlog）。

### 4.6 一键构建脚本（`desktop/build/build_macos.sh`）

```bash
#!/usr/bin/env bash
set -e
# 1. 确认在 venv 里、依赖装齐
# 2. 跑测试（不允许带伤打包）
pytest -q
# 3. （可选）下载 marked.min.js 到 frontend/vendor/
# 4. PyInstaller 打包
pyinstaller desktop/build/uta_app.spec --distpath dist --noconfirm
# 5. 产物：dist/UTA Desktop.app
echo "✓ 构建完成：dist/UTA Desktop.app"
```

构建产出的 `.app` 在 `dist/` 下，不进 Git（加进 `.gitignore`）。

### 4.7 开发期运行（不用每次打包）

开发时直接跑未打包的入口，pywebview 照样能开窗口：

```bash
python desktop/app.py
# 窗口弹出，前端从 desktop/frontend/index.html 实时加载
# 改完 app.js 刷新窗口即可，不用重新打包
```

这是和"打包链路"解耦的——开发循环很快，只有要分发时才走 `build_macos.sh`。

---

## 5. 版本路线、验收标准、与 PRD 主线关系

### 5.1 版本路线

桌面版是 **v2.0**，紧跟在 v1.0 CLI 学习版之后。内部拆三个小版本，对应"架构预留 + 首版最小"：

| 版本 | 目标 | Tag |
|---|---|---|
| **v2.0.0-alpha** | 能跑通的最小桌面版：pywebview 窗口 + 单页控制台 + 打通当前 v0.4 的总结任务 + 设置页填云端 Key | `v2.0.0-alpha-desktop` |
| **v2.0.0** | 完整打包链路：PyInstaller 出 `.app`、配置落 `~/.uta/`、构建脚本 | `v2.0.0-desktop` |
| **v2.1.0** | 对齐主线 v1.0：随主线补 Verifier 重试/Reflection/Memory/Skill，前端接口已预留、只接不重写 | `v2.1.0-desktop-v1aligned` |

> **关键约束**：v2.0.0-alpha 依赖的核心能力，**只用当前 v0.4 已有的**（Loop / Planner / Router / Executor / file/text/report tool）。它不卡在"等 v1.0 做完"上。v2.1.0 才去对齐完整 v1.0。

### 5.2 验收标准（桌面版专有，D1-D10）

新增一组 D 编号，和 PRD 现有的 A（核心）/T（TAM）并列：

| 编号 | 验收项 | 必须 |
|---|---|---|
| D1 | 双击 `.app` 能弹原生窗口、不弹终端 | 必须 |
| D2 | 设置页能填云端 base_url/model/key，保存后重启仍在 | 必须 |
| D3 | 没填 Key 时运行，前端给出明确提示而非崩溃 | 必须 |
| D4 | 输入总结任务能跑通，左侧逐步显示计划/工具/校验事件 | 必须 |
| D5 | 右侧能渲染 Markdown 最终报告 + 可折叠 state.json | 必须 |
| D6 | `.app` 不向代码仓写任何文件（全落 `~/.uta/`） | 必须 |
| D7 | CLI 仍能照常 `python main.py` 运行，不受桌面版影响 | 必须 |
| D8 | `core/` 唯一改动是 Loop 的可选 `on_progress` 回调 | 必须 |
| D9 | 构建脚本带伤（测试不过）时不许产出 `.app` | 应该 |
| D10 | 改了前端刷新窗口即可，无需重新打包（开发循环） | 应该 |

### 5.3 与 PRD 主线的关系（三处需同步进 PRD）

桌面版作为独立里程碑加入后，PRD 需补充说明，避免与主线产生版本矛盾：

1. **第 7 节非目标**"复杂前端 / 先 CLI"——补一句：CLI 优先原则在 v0.x-v1.0 维持不变；桌面化是 v2.0 独立里程碑，不提前侵入 v1.0 的范围。
2. **第 23 节 Backlog**"简单 Web UI（v1.2）"——补一句：该 Web UI 项被 v2.0 桌面版吸收并升级为"原生打包桌面应用"，v1.2 不再单独立项。
3. **新增小节**记录桌面版定位、技术栈、与 CLI 的隔离原则（本设计文档即其内容载体）。

### 5.4 学习价值（呼应 PRD 核心立意）

PRD 反复强调"能看懂、能调试"。桌面版在此立意上加码：

- 左侧执行过程的**逐步事件流**，把原本散在日志里的 Loop 行为可视化——比 CLI 更直观地"看懂 Agent Loop 怎么转"。
- 可折叠的 state.json，让学习者**对着真实运行产物理解 State 结构**。
- 前后端打包链路本身是独立学习模块：PyInstaller 冻结、app bundle 结构、配置脱离代码仓——这些是 CLI 学不到的工程知识。

### 5.5 不做的事（范围钉死）

- ❌ 多任务并发（首版单任务）
- ❌ 任务取消（接口留空实现）
- ❌ Keychain 加密存储（进 Backlog）
- ❌ Tauri/Electron 那套原生外壳（已排除，pywebview 够用）
- ❌ 在 v2.0 之前对 core/ 做任何为桌面版而设的改造（回调除外）

---

## 6. 依赖清单（新增）

桌面版引入的新依赖（CLI 不受影响）：

| 依赖 | 用途 | 加入方式 |
|---|---|---|
| `pywebview` | 原生窗口 + JS-Python 桥 | 新增 `requirements-desktop.txt`，与 `requirements.txt` 分离 |
| `pyinstaller` | 打包 `.app` | 同上，仅打包时需要 |

> 分离的原因：CLI 学习者只需 `pip install -r requirements.txt`（当前仅 pytest），不被迫装 pywebview/pyinstaller。桌面版用 `requirements-desktop.txt` 包含两者。

---

## 7. 待审阅

本设计文档待用户审阅。审阅通过后，将进入实现计划阶段（writing-plans）。

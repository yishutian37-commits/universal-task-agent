# Universal Task Agent 项目说明

更新时间：2026-06-24

## 1. 项目一句话

Universal Task Agent，简称 UTA，是一个学习型任务 Agent 框架。它的目标不是只做一次问答，而是把一次任务从“用户输入”到“执行、校验、反思、重新规划、沉淀记忆”的完整链路跑通，并逐步变成一个能复用经验的本地智能助理。

## 2. 这个项目要解决什么问题

很多 Agent Demo 只展示“模型回答了什么”，但真正能长期使用的 Agent 需要更多能力：

- 能理解任务类型，而不是所有输入都当成普通聊天。
- 能把任务拆成步骤，并按步骤执行。
- 能选择合适工具，例如读文件、总结文本、分析表格、生成报告。
- 能校验输出是否合格，不合格时能重试或重新规划。
- 能保存短期状态和长期记忆，下一次任务可以参考过去经验。
- 能有桌面端界面，让状态、日志、历史记录和记忆变得可见。

UTA 当前就是围绕这条主线逐步搭建出来的。

## 3. 当前能做什么

### 3.1 命令行任务

项目已经支持以下核心任务：

- 文本总结：读取文本或文件，生成结构化中文总结。
- 表格分析：读取 CSV / Excel，输出字段说明、基础统计、缺失值、异常值和分类汇总。
- 学习型 Agent Loop：任务会经过计划、执行、校验、反思和必要时重新规划。
- JSON Memory：任务完成后会保存任务历史、经验、失败规则和 Skill 候选。
- Skill Loader：可以从 `skills/*.md` 加载本地 Skill，命中后优先使用 Skill 里的 workflow。

示例：

```bash
.venv/bin/python main.py --task "帮我总结一段文本：UTA 要跑通 Agent Loop、Verifier、Memory 和 Skill。"
```

```bash
.venv/bin/python main.py --task "分析 examples/orders.csv"
```

### 3.2 桌面端应用

桌面端把 Python Agent 包进本地 macOS 应用里，主要能力包括：

- 输入任务并运行 Agent。
- 查看实时状态和执行日志。
- 查看运行记录。
- 查看历史任务的 state/log。
- 查看只读 JSON Memory，包括任务历史、经验、负向规则和 Skill 候选。
- 保存 LLM 配置，不在界面里明文回显 API Key。

当前本地打包产物：

```text
/Users/tianjiashu/项目/dist/UTA Desktop.app
/Users/tianjiashu/项目/dist/UTA Desktop-macos.zip
```

### 3.3 V1.2 代码阅读能力

本地 V1.2 桌面包已经支持代码阅读任务，可以让 Agent 阅读当前 UTA 项目关键代码，并说明一次任务从输入到输出怎么跑。

测试输入：

```text
阅读 UTA 代码，说明一次任务从输入到输出怎么跑
```

正常报告会包含：

- `## 任务链路`
- `## 关键文件`
- `## 模块职责`
- `## 调用顺序`
- `## 状态与记忆`
- `## 桌面端入口`
- `## 风险点`
- `## 下一步建议`

注意：代码阅读任务是只读能力，只扫描打包进桌面应用的 UTA 源码快照，不会自动修改代码。

### 3.4 RAG 知识库方向

项目里已经开始设计独立 RAG 知识库模块，目录是：

```text
rag-knowledge-base/
```

它的定位是独立运行的知识库系统，未来再接入 UTA。设计目标包括：

- 支持 Markdown / TXT 起步，后续扩展 PDF / Word / 网页。
- 使用可替换的 Embedding 接口。
- 使用 SQLite 保存文本片段和向量。
- 暴露 `KnowledgeBase` 作为未来 UTA 的唯一接入口。
- 提供 CLI 和 REST API。

RAG 当前属于设计和早期骨架方向，不是 UTA 主链路的必需依赖。

## 4. 核心运行链路

UTA 的主链路可以理解为：

```text
用户输入
  ↓
TaskParser：识别任务类型、意图、输入类型、期望输出
  ↓
SkillLoader：尝试匹配本地 Skill
  ↓
Planner：生成任务步骤
  ↓
Agent Loop：按步骤推进
  ↓
Router：根据步骤选择工具
  ↓
Executor：执行工具
  ↓
Verifier：校验结果是否合格
  ↓
Reflection / Replan：失败时反思，必要时重新规划
  ↓
Memory：保存任务历史和经验
  ↓
最终输出
```

这条链路的重点是：Agent 不只生成答案，还会保留过程、校验结果，并把经验沉淀下来。

## 5. 主要目录说明

```text
core/
```

Agent 核心逻辑，包括任务解析、计划、循环、路由、执行、校验、反思、Skill 加载等。

```text
tools/
```

工具层。不同任务会路由到不同工具，例如文件读取、文本总结、表格分析、报告生成等。

```text
memory_providers/
```

长期记忆实现，目前是 JSON 文件形式。

```text
memory/
```

本地长期记忆数据，包括：

- `task_history.json`
- `lessons.json`
- `negative_rules.json`
- `skill_candidates.json`
- `user_profile.json`

```text
skills/
```

本地 Markdown Skill。当前已有文本总结和表格分析 Skill。

```text
desktop/
```

桌面端代码。前端在 `desktop/frontend/`，Python 桥接 API 在 `desktop/api.py`，后台任务 runner 在 `desktop/runner.py`。

```text
examples/
```

示例输入文件，例如 `orders.csv` 和总结示例文本。

```text
tests/
```

自动化测试。

```text
rag-knowledge-base/
```

独立 RAG 知识库方向，未来可作为 UTA 的知识检索模块。

## 6. 记忆系统怎么看

UTA 里有两类记忆。

### 6.1 短期记忆

短期记忆是单次任务运行过程中的 `AgentState`。它记录：

- task_id
- task_type
- intent
- plan
- 每步执行结果
- verifier 检查结果
- reflection 反馈
- replan 事件
- final_output

命令行默认输出到：

```text
outputs/states/
outputs/logs/
```

桌面端默认输出到：

```text
~/.uta/outputs/
```

### 6.2 长期记忆

长期记忆是跨任务保存的 JSON Memory。

命令行项目内默认位置：

```text
memory/
```

桌面端默认位置：

```text
~/.uta/memory/
```

主要文件：

- `task_history.json`：任务历史。
- `lessons.json`：成功任务沉淀出的可复用经验。
- `negative_rules.json`：失败任务沉淀出的负向规则。
- `skill_candidates.json`：未来可能沉淀成 Skill 的候选。
- `user_profile.json`：用户偏好和画像信息。

桌面端的“记忆”页面可以直观看到这些长期记忆。

## 7. 如何运行

### 7.1 安装依赖

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

桌面端需要额外依赖：

```bash
.venv/bin/python -m pip install -r requirements-desktop.txt
```

### 7.2 配置 LLM

复制环境变量模板：

```bash
cp .env.example .env
```

在 `.env` 里填写本地使用的 LLM 配置。不要把真实 API Key 提交到 Git。

如果 HTTPS 访问 LLM 接口遇到证书问题，可以只在本地 `.env` 里配置：

```text
LLM_SSL_VERIFY=0
```

### 7.3 运行命令行任务

```bash
.venv/bin/python main.py --task "帮我总结一段文本"
```

```bash
.venv/bin/python main.py --task "分析 examples/orders.csv"
```

### 7.4 运行桌面端开发版

```bash
.venv/bin/python desktop/app.py
```

### 7.5 构建桌面端

```bash
bash desktop/build/build_macos.sh
```

构建产物：

```text
dist/UTA Desktop.app
dist/UTA Desktop-macos.zip
```

## 8. 如何测试

跑全量测试：

```bash
.venv/bin/python -m pytest -q
```

跑桌面端相关测试：

```bash
.venv/bin/python -m pytest tests/test_desktop_api.py tests/test_desktop_frontend_assets.py -q
```

跑主链路相关测试：

```bash
.venv/bin/python -m pytest tests/test_main.py tests/test_loop.py tests/test_verifier.py -q
```

## 9. 当前本地状态说明

截至 2026-06-24，本地项目有几条需要区分的线：

- 主目录当前分支是 `codex/v2-desktop-app`，主要包含桌面端、记忆视图和 RAG 设计相关内容。
- V1.2 代码阅读能力在 `codex/v1.2-code-reading-agent` 分支上完成，并已经重新打包进主目录 `dist/UTA Desktop.app`。
- 本地桌面包版本是 `1.2.0`，前端显示 `V1.2`。
- 如果从 Dock、启动台或 Applications 打开旧应用，可能看不到最新能力；测试时应直接打开 `/Users/tianjiashu/项目/dist/UTA Desktop.app`。

## 10. 安全注意事项

- 不要把 `.env`、API Key、GitHub Token 提交到 Git。
- 如果 token 曾经出现在聊天或日志里，应去 GitHub 撤销并重新生成。
- 桌面端设置里可以保存 LLM Key，但界面不会明文回显。
- 代码阅读功能只读打包内的 UTA 源码快照，不会自动修改项目文件。

## 11. 下一步建议

建议后续按这个顺序推进：

1. 先把 V1.2 代码阅读分支和当前桌面 V2 分支合并整理，避免“源码分支”和“打包产物”能力不一致。
2. 把桌面端版本号、README、CHANGELOG 统一更新到当前真实能力。
3. 推送到 GitHub 前先清理 `.env`、memory 运行记录和原型 HTML 脏文件。
4. RAG 知识库先保持独立模块，跑通最小 ingest/query/ask 后再接入 UTA。
5. 桌面端后续可以增加“当前能力/版本/最近一次构建时间”页面，减少打开旧包造成的混淆。

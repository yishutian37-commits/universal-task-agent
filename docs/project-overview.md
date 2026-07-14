# Universal Task Agent 项目简介

更新时间：2026-07-15

## 一句话介绍

Universal Task Agent，简称 UTA，是一个本地运行的学习型 Agent 项目。它不是普通聊天窗口，而是一个可以把用户任务拆解成步骤、自动选择工具、执行任务、校验结果、记录经验，并逐步沉淀 Skill 的本地智能工作台。

## 当前项目能做什么

当前 UTA 已经具备命令行、FastAPI、桌面端和本地知识库能力。用户可以从一句自然语言任务开始，让系统完成解析、规划、执行、校验、生成报告和保存记录。

主要能力包括：

- 文本总结：把文章、说明、资料整理成结构化中文总结。
- 表格分析：读取 CSV / Excel，输出字段说明、基础统计、异常数据和业务解释。
- 联网调研：根据问题进行搜索，并生成带来源的调研报告。
- 实时天气：识别天气类问题，调用天气接口生成结果。
- 代码阅读：只读扫描项目代码，说明任务链路、关键文件和模块职责。
- RAG 知识库：摄入本地文档，进行检索和问答。
- GEO 分析：基于 `geo-agent-marketing-optimized` 技能包，生成问题矩阵、内容 Brief、事实缺口和平台合规建议。
- 历史任务查询：用户可以问“我之前让你进行过什么任务”，UTA 会从历史 state 和 JSON Memory 中列出任务记录。
- 复杂任务拆解：识别“分步骤执行”或 `[1][2][3]` 类任务，自动生成步骤清单，逐步执行，并用 `[ ]/[x]` 标记进度。
- 模型结构化规划：根据任务、约束和真实工具目录生成 1-8 个可校验步骤。
- 动态工具编排：模型可在已注册工具中选择 action 和参数，无效时回退确定性规则。
- 证据驱动重规划：失败后使用校验原因、修复建议、已完成结果和文件证据重新规划。
- 人工介入：缺少信息时暂停等待回复，复杂或高风险计划可在执行前确认、编辑或取消。
- 可恢复交互：等待信息或计划确认会保存稳定 request id，应用重启后继续原任务且不重跑已完成步骤。
- 成功标准证据：每条步骤标准都保存结论、来源和证据，不可判定时明确失败。
- Skill 包查看：桌面端“技能包”页可以查看运行时 Skill、vendor 规则包和加载问题。
- 对话式桌面前端：桌面端主界面支持聊天消息流，执行过程放在右侧详情区。

## 桌面端能看到什么

桌面端把 Python Agent 包进本地 macOS 应用里。当前桌面端可以看到：

- 当前任务状态和对话消息流。
- 执行步骤，以及 `[ ]/[x]` 形式的步骤完成状态。
- 实时日志。
- 最终结果。
- 会话历史和历史运行记录。
- 历史 state/log。
- 短期记忆和长期 JSON Memory。
- RAG 知识库文档和问答。
- 已安装 Skill 和 vendor 规则包。

桌面端运行数据默认保存在：

```text
~/.uta/
```

构建产物位于：

```text
dist/UTA Desktop.app
dist/UTA Desktop-macos.zip
```

## 核心运行链路

UTA 的主链路是：

```text
用户输入
  ↓
TaskParser：识别任务类型、意图、输入类型、期望输出
  ↓
SkillLoader：尝试匹配本地 Skill
  ↓
Planner：使用模型和工具目录生成结构化任务步骤
  ↓
Agent Loop：按步骤推进
  ↓
Router：在实际注册工具中动态选择 action，失败时回退规则
  ↓
Executor：执行工具
  ↓
Verifier：校验结果是否合格
  ↓
Reflection / Replan：失败时反思，必要时重新规划
  ↓
Memory：保存任务历史、经验和候选 Skill
  ↓
最终输出
```

这条链路的重点是：UTA 不只给答案，还会保留任务过程、校验结果、失败反馈和可复用经验。

## 记忆系统

UTA 有两类记忆。

短期记忆是单次任务的 `AgentState`，记录任务类型、计划、每一步工具结果、校验结果、反思、replan 事件和最终输出。

命令行默认保存到：

```text
outputs/states/
outputs/logs/
```

桌面端默认保存到：

```text
~/.uta/outputs/
```

长期记忆是跨任务的 JSON Memory。

命令行默认保存到：

```text
memory/
```

桌面端默认保存到：

```text
~/.uta/memory/
```

长期记忆文件包括：

- `task_history.json`：历史任务。
- `lessons.json`：成功任务沉淀出的经验。
- `negative_rules.json`：失败任务沉淀出的负向规则。
- `skill_candidates.json`：可能值得固化为 Skill 的候选。
- `user_profile.json`：用户画像和偏好预留。

## 主要目录

```text
core/
```

Agent 核心逻辑，包括任务解析、计划、循环、路由、执行、校验、反思和 Skill 加载。

```text
tools/
```

工具层，例如文件读取、文本总结、表格分析、搜索、代码阅读、GEO 分析、历史任务查询和报告生成。

```text
memory_providers/
```

长期记忆实现，目前是 JSON 文件形式。

```text
skills/
```

本地 Markdown Skill，以及 `skills/vendor/` 下的外部规则包。

```text
rag/
```

RAG 知识库模块，提供文档摄入、切片、向量检索、问答、CLI 和 API。

```text
desktop/
```

桌面端代码。前端在 `desktop/frontend/`，Python 桥接 API 在 `desktop/api.py`，后台任务 runner 在 `desktop/runner.py`。
主任务页采用聊天消息流，执行详情仍显示步骤、日志和 state。

```text
tests/
```

自动化测试。

## 常用示例

文本总结：

```bash
.venv/bin/python main.py --task "帮我总结一段文本：UTA V1.0 要跑通 Agent Loop、Verifier、Memory 和 Skill。"
```

表格分析：

```bash
.venv/bin/python main.py --task "分析 examples/orders.csv"
```

代码阅读：

```bash
.venv/bin/python main.py --task "阅读 UTA 代码，说明一次任务从输入到输出怎么跑"
```

GEO 分析：

```bash
.venv/bin/python main.py --task "帮我做 GEO 分析：行业是本地装修，地区是包头，品牌事实：有官网、提供设计和施工服务、需要避免夸大承诺。"
```

历史任务查询：

```bash
.venv/bin/python main.py --task "我之前让你进行过什么任务，给我列出来"
```

复杂任务拆解：

```bash
.venv/bin/python main.py --task "帮我执行复杂任务：[1]分析当前项目状态 [2]列出下一步计划 [3]总结风险点"
```

## 当前阶段

当前主线已经完成学习型 Agent 核心闭环、调研搜索/API、代码阅读、RAG 桌面集成、GEO skill 包嫁接、技能包可视化、历史任务查询和桌面端对话前端。v1.11.0 的模型规划、action 契约、成功标准证据、编辑后重绑定和可恢复人工介入已完成自动化与 25 条离线评测，真实桌面、macOS 重打包、签名和 ZIP 完整性门禁也已通过，并于 2026-07-15 正式发布。

下一步适合继续做：

- 增强联网搜索质量和来源核验。
- 增强长期记忆的可视化、编辑和检索。
- 把更多高频任务沉淀成正式 Skill。
- 继续增加多工具长任务评测，优化模型计划的稳定性和成本。

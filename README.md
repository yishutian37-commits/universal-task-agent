# Universal Task Agent

UTA 是一个学习型 Agent 框架。当前核心里程碑是 `v1.0-learning-agent`：支持文本总结和表格分析两类任务，跑通 Task Parser、Planner、Agent Loop、Router、Executor、Verifier、Reflection、Replan、JSON Memory 和 Skill Loader。

## 快速开始

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py --task "帮我总结一段文本"
```

## V1.0 Demo

文本总结：

```bash
.venv/bin/python main.py --task "帮我总结一段文本：UTA V1.0 要跑通 Agent Loop、Verifier、Memory 和 Skill。"
```

表格分析：

```bash
.venv/bin/python main.py --task "分析 examples/orders.csv"
```

## 短期记忆与长期记忆

- 短期记忆：单次任务内的 `AgentState`，保存到 `outputs/states/<task_id>_state.json`，日志保存到 `outputs/logs/<task_id>.log`。
- 长期记忆：跨任务 JSON Memory，保存在 `memory/*.json`。
- `memory/task_history.json`：任务历史。
- `memory/lessons.json`：成功任务沉淀出的可复用经验。
- `memory/negative_rules.json`：失败任务沉淀出的负向规则。
- `memory/skill_candidates.json`：可能值得人工确认成 Skill 的候选。

## 记忆示例

任务完成后，UTA 会更新 `memory/*.json`：

```bash
.venv/bin/python main.py --task "分析 examples/orders.csv"
```

重点文件：

- `memory/task_history.json`：跨任务历史。
- `memory/lessons.json`：成功任务的可复用经验。
- `memory/negative_rules.json`：失败任务的负向规则。
- `memory/skill_candidates.json`：Skill Builder 的候选输入。

## Skill 示例

UTA 会在任务开始时读取 `skills/*.md`。命中 Skill 后，`Planner` 优先使用 Skill 的 `workflow`：

```bash
.venv/bin/python main.py --task "分析 examples/orders.csv"
```

正式 Skill 文件放在：

- `skills/summarize_article.md`
- `skills/analyze_table.md`

草稿 Skill 放在 `skills/drafts/`，不会被运行时自动加载。人工确认后，把草稿移动到 `skills/` 根目录，并把 `enabled` 改为 `true`。

## LLM 配置

V0.2 开始支持真实 LLM Task Parser。复制 `.env.example` 为 `.env`，只在本地 `.env` 填入真实 API key：

```bash
cp .env.example .env
```

`.env` 已被 `.gitignore` 排除，不要把真实 key 提交到 Git。

如果本机 Python 访问 HTTPS LLM 接口时报证书错误，可以只在本地 `.env` 加：

```bash
LLM_SSL_VERIFY=0
```

## 当前状态

- `v0.1-skeleton`: CLI 输入、AgentState、MockTool、Executor、Verifier、最小 Loop、state/log 输出。
- `v0.2-llm-parser`: 新增 LLMClient、TaskParser，支持识别 `summarize` / `data_analysis` / `unknown`。
- `v0.3-planner-router`: 新增 Planner 和 Router，执行多步计划，但仍使用占位工具。
- `v0.4-summary-demo`: `file_tool` 读取文本，`text_tool` 调 LLM 生成中文结构化总结，`report_tool` 输出 Markdown 报告。
- `v0.5-verifier-reflection`: `Verifier` 做总结结构硬校验，`Reflection` 分类失败并驱动单步重试。
- `v0.6-data-analysis`: `table_tool` 读取 CSV / Excel，生成字段、基础统计、缺失值、异常值和分类汇总，并由 `Verifier` 做表格报告校验。
- `v0.7-memory`: 新增 `JsonMemoryProvider`，任务完成后写入 `memory/*.json`，保存任务历史、经验、失败规则和 Skill 候选。
- `v0.8-skill-runtime`: 新增 `SkillLoader` 和 `SkillBuilder`，支持本地 Markdown Skill 的加载、候选草稿生成和 Planner workflow 注入。
- `v1.0-learning-agent`: 新增 A11 replan，单个 step 重试耗尽后可重新规划一次，并从失败 step 继续；完成 README、CHANGELOG 和两类 demo 验收。
- TAM Memory 不属于 UTA v1.0 核心范围。

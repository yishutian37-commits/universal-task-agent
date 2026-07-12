# Universal Task Agent

UTA 是一个学习型 Agent 框架。当前主线已经整合 V1.0 学习型 Agent、V1.1 调研搜索/API、V1.2 代码阅读、RAG 知识库、GEO 分析 Skill、复杂任务拆解执行和桌面端体验层。

桌面端支持对话式前端：每条消息先由模型结合会话上下文判断普通聊天或任务执行，普通聊天可实时增量显示，任务在右侧展示步骤、日志、文件变更和产物。输入区可添加 MD、TXT、PDF、DOCX 作为当前消息附件；需要跨会话使用的文档则通过知识库长期导入。文件写入、删除、目录创建、Shell、Python REPL 等高风险操作始终进入受控任务与手动授权流程。记忆中心支持搜索、编辑、停用、启用和删除长期记忆，停用内容不会继续进入模型上下文。

项目中文简介见：`docs/project-overview.md`

## 快速开始

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py --task "帮我总结一段文本"
```

## 常用 Demo

文本总结：

```bash
.venv/bin/python main.py --task "帮我总结一段文本：UTA V1.0 要跑通 Agent Loop、Verifier、Memory 和 Skill。"
```

表格分析：

```bash
.venv/bin/python main.py --task "分析 examples/orders.csv"
```

调研报告：

```bash
.venv/bin/python main.py --task "调研 UTA Agent 路线"
```

实时天气：

```bash
.venv/bin/python main.py --task "包头今日天气状况"
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

UTA API：

```bash
.venv/bin/python -m uvicorn api.server:app --host 127.0.0.1 --port 8000
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
- `skills/geo_analysis.md`

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
- `research-search`: 当前分支新增 `research` 任务类型、可插拔 Search Provider、`search_tool`、带来源的调研报告和 CLI demo；默认使用 Bing HTML 联网搜索，无需额外 search key。天气类问题会走 Open-Meteo 实时天气接口，避免把普通网页摘要误当成天气结果。
- `api-code-reading-alignment`: 当前分支已恢复 UTA 根 FastAPI 接口，并合并只读代码阅读任务；桌面端会打包源码快照供 `code_tool` 扫描。
- `rag-integration`: 当前分支已把 RAG 整合进主项目，提供 CLI、FastAPI、桌面端知识库 Tab 和自动 seed。
- `geo-skill-adapter`: 当前分支嫁接 `geo-agent-marketing-optimized` Skill 包，新增 `geo_analysis` 任务类型、`geo_tool`、GEO 报告生成和硬校验，并会随桌面端一起打包。
- `history-query`: 当前分支新增 `history_query` 任务类型和 `history_tool`，用户可直接询问“之前让我做过什么任务”，UTA 会从 state 历史和 JSON Memory 中列出历史任务。
- `complex-task-checklist`: 当前分支新增 `complex_task` 任务类型，支持把复杂任务拆成 `[ ]/[x]` 步骤清单，按步骤执行，并在桌面端实时显示步骤状态。
- TAM Memory 不属于 UTA v1.0 核心范围。

## RAG 知识库

`rag/` 模块提供文档摄入、向量检索和问答能力，可独立使用，也可供 Agent 和桌面端调用。当前支持 Markdown、TXT、PDF、DOCX，已经完成真实文件摄入、定长切片、SQLite 持久化、向量召回与关键词重排、CLI、FastAPI、桌面端知识库接入，以及可选真实模型模式。

```python
from rag import create_default_kb
kb = create_default_kb()
kb.ingest_path("notes.md")
print(kb.ask("问题").answer)
```

常用命令：

```bash
.venv/bin/python -m rag.cli --help
.venv/bin/python -m rag.cli ingest README.md
.venv/bin/python -m rag.cli ask "UTA 当前能做什么"
.venv/bin/python -m rag.api
```

详见 `rag/README.md` 和 `docs/superpowers/specs/2026-06-24-rag-knowledge-base-design.md`。

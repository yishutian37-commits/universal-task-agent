# Changelog

## 当前 rag-knowledge-base 分支

- RAG 已从独立目录整合进 UTA 主项目，代码位于 `rag/`，测试位于 `tests/test_rag_*.py`。
- 新增 RAG CLI、FastAPI、桌面端知识库 Tab、自动 seed，以及可选真实 bge + mimo 模式。
- 新增 research 任务链路：Search Provider、`search_tool`、调研报告生成和来源校验。
- research 默认搜索从 fixture 改为 Bing HTML 联网搜索，fixture 只保留给测试/演示使用。
- 修复天气类问题被普通搜索摘要误导的问题：`search_tool` 会识别天气意图并调用 Open-Meteo 实时天气接口，`report_tool` 会生成天气报告。
- 恢复 UTA 根 FastAPI 接口：`api.server` 提供健康检查、同步任务运行、运行记录列表和运行详情接口。
- 合并 V1.2 只读代码阅读能力：新增 `code_reading` 任务类型、`code_tool`、代码阅读报告和硬校验。
- 桌面端注册 `code_tool`，并把一份源码快照打包到 `.app` 内，供代码阅读任务只读扫描。
- 将桌面端历史记录读取逻辑迁移到 `core.history_store`，供桌面/API 等入口复用。
- 修正 RAG API 真实模型环境变量，统一使用 `KB_USE_REAL_MODELS`。
- 嫁接 `geo-agent-marketing-optimized` Skill 包：新增 `geo_analysis` 任务类型、`geo_tool`、GEO 问题矩阵/内容 Brief/平台合规报告和 Verifier 硬校验。
- 桌面端注册 `geo_tool`，并把 GEO vendor 规则包随 `.app` 一起打包。
- 桌面端新增“技能包”页，可直观看到运行时 Skill、vendor 规则包和 Skill 加载问题。
- 新增 `history_query` 任务类型和 `history_tool`，修复“我之前让你进行过什么任务”被误判为文本总结的问题。
- 新增 `complex_task` 任务类型：可识别复杂任务、按用户输入拆成多步计划、逐步执行，并在最终输出和桌面端用 `[ ]/[x]` 展示步骤状态。
- 修正复杂任务最终输出只显示 checklist 的问题：现在会额外输出每一步的“分步结果”，文本类步骤会按当前步骤目标生成内容。
- 修正“正文 + 你可以让 Agent 做这几个任务：1. ... 2. ...”被误判为普通总结或代码阅读的问题，任务清单现在会优先识别为复杂任务。
- 修正复杂任务最终报告冗余显示执行清单的问题；桌面端 Markdown 渲染新增一级标题、加粗、行内代码和编号列表支持。
- 新增桌面端对话式前端，支持聊天消息流、会话历史和执行详情侧栏。

## v1.0-learning-agent

- 补齐 UTA 学习型 Agent 核心闭环，覆盖文本总结和表格分析两类任务。
- 在单个 step 重试耗尽后增加一次 replan，并把 replan 事件保存到 state/log。
- 补充短期 State 记忆和长期 JSON Memory 的说明。
- 使用文本总结 demo 和表格分析 demo 完成 V1.0 验收。

## v0.8-skill-runtime

- 新增 Markdown Skill 加载、草稿生成和 Planner workflow 注入。
- 新增 `v0.7-memory`：JSON Memory 任务历史、经验、负向规则和 Skill 候选。
- 新增 `v0.6-data-analysis`：CSV/Excel 表格分析、表格报告和数字校验。
- 新增 `v0.5-verifier-reflection`：总结结构校验和 Reflection retry。
- 新增 `v0.4-summary-demo`：真实总结工具。
- 新增 `v0.3-planner-router`：Planner 和 Router。
- 新增 `v0.2-llm-parser`：LLMClient 和 TaskParser。
- 启动 UTA `v0.1-skeleton`。

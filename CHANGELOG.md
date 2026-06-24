# Changelog

## 当前 rag-knowledge-base 分支

- RAG 已从独立目录整合进 UTA 主项目，代码位于 `rag/`，测试位于 `tests/test_rag_*.py`。
- 新增 RAG CLI、FastAPI、桌面端知识库 Tab、自动 seed，以及可选真实 bge + mimo 模式。
- 新增 research 任务链路：Search Provider、`search_tool`、调研报告生成和来源校验。
- research 默认搜索从 fixture 改为 Bing HTML 联网搜索，fixture 只保留给测试/演示使用。
- 将桌面端历史记录读取逻辑迁移到 `core.history_store`，供桌面/API 等入口复用。
- 修正 RAG API 真实模型环境变量，统一使用 `KB_USE_REAL_MODELS`。

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

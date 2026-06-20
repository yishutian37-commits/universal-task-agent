# Universal Task Agent

UTA 是一个学习型 Agent 框架。当前里程碑是 `v0.6-data-analysis`：在总结链路之外，新增 CSV / Excel 表格分析工具、Markdown 表格报告和数字一致性校验。

## Quickstart

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py --task "帮我总结一段文本"
```

## 表格分析示例

```bash
.venv/bin/python main.py --task "分析 examples/orders.csv"
```

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
- TAM Memory 不属于 UTA v1.0 核心范围。

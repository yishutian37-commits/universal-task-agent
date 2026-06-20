# Universal Task Agent

UTA 是一个学习型 Agent 框架。当前里程碑是 `v0.2-llm-parser`：在 v0.1 最小骨架上，新增 LLMClient 和 TaskParser。

## Quickstart

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py --task "帮我总结一段文本"
```

## LLM 配置

V0.2 开始支持真实 LLM Task Parser。复制 `.env.example` 为 `.env`，只在本地 `.env` 填入真实 API key：

```bash
cp .env.example .env
```

`.env` 已被 `.gitignore` 排除，不要把真实 key 提交到 Git。

## 当前状态

- `v0.1-skeleton`: CLI 输入、AgentState、MockTool、Executor、Verifier、最小 Loop、state/log 输出。
- `v0.2-llm-parser`: 新增 LLMClient、TaskParser，支持识别 `summarize` / `data_analysis` / `unknown`。
- TAM Memory 不属于 UTA v1.0 核心范围。

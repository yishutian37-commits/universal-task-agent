# Universal Task Agent

UTA 是一个学习型 Agent 框架。当前里程碑是 `v0.1-skeleton`：不接 LLM，只跑通 CLI、State、MockTool、Executor、Verifier 和最小 Loop。

## Quickstart

```bash
pip install -r requirements.txt
python main.py --task "帮我总结一段文本"
```

## 当前状态

- `v0.1-skeleton`: CLI 输入、AgentState、MockTool、Executor、Verifier、最小 Loop、state/log 输出。
- TAM Memory 不属于 UTA v1.0 核心范围。

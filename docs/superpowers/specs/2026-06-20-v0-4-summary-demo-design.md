# UTA V0.4 文本总结 Demo 设计

## 背景

当前 `v0.3-planner-router` 已经具备：

- `TaskParser`：识别 `summarize` / `data_analysis` / `unknown`；
- `Planner`：为 `summarize` 生成三步计划；
- `Router`：按步骤目标选择 `file_tool` / `text_tool` / `report_tool`；
- `Executor` 和 `Verifier`：执行工具并检查 `ToolResult.success`；
- CLI、state、log、Git tag 链路已经跑通。

但 v0.3 的工具仍是占位工具，所以 CLI 最终仍输出 `mock result`。v0.4 的目标是把文本总结 Demo 做成真正可用：用户输入一段文本或一个本地文本文件路径后，Agent 输出中文结构化总结。

## 目标

完成 `v0.4-summary-demo`：

1. `file_tool` 可以读取任务中的本地文本文件；如果没有文件路径，则使用用户输入本身作为文本；
2. `text_tool` 调用统一的 `LLMClient` 生成中文结构化总结；
3. `report_tool` 输出最终 Markdown 报告；
4. `run_minimal_loop()` 可以把上一步工具结果传给下一步工具；
5. CLI 最终输出不再是固定 `mock result`，而是真实总结文本；
6. 没有 LLM API key 或 LLM 调用失败时，程序不崩溃，返回清楚的失败信息。

## 非目标

v0.4 不做以下内容：

- 不做 Reflection、重试、replan；
- 不做 v0.5 的结构性硬条件校验；
- 不做 L1 数字一致性来源约束；
- 不做 CSV / Excel 表格分析；
- 不做多 Agent；
- 不接 TAM Memory；
- 不把真实 API key 写进 Git。

## 方案选择

### 方案 A：只替换 `text_tool`

保留 `file_tool` 和 `report_tool` 占位，只让 `text_tool` 调 LLM。

优点：改动最小。缺点：不能总结文件，三步计划的前后数据流仍然是假的。

### 方案 B：实现三件最小真工具

实现 `FileTool`、`TextTool`、`ReportTool`，并在 Router action 参数中传递上一步结果。

优点：最小闭环真实可用，符合 v0.4 Demo。缺点：需要改 Router/Loop 的数据传递测试。

### 方案 C：一次性做完整 Report/Verifier/Reflection

同时做报告质量校验、失败反思、重试。

优点：更接近 v1.0。缺点：越过 v0.5 边界，学习复杂度过高。

选择方案 B。它让 v0.4 真正从 `mock result` 走到“可用总结”，同时保持范围足够小。

## 架构

### 数据流

```text
main.py
-> TaskParser.parse()
-> Planner.create_plan()
-> Router.choose_tool()
-> Executor.run()
-> Verifier.check()
-> next step receives previous_result
-> final_output
```

`Router.choose_tool(state, step)` 已经能看到 `state.results`。v0.4 在生成 `Action.params` 时增加：

```python
{
    "user_input": state.user_input,
    "goal": step.goal,
    "previous_result": state.results[-1].result if state.results else None,
}
```

这样三步计划的数据流是：

1. `file_tool.read` 返回 `content`；
2. `text_tool.process` 从 `previous_result["content"]` 拿文本，调用 LLM 返回 `summary_markdown`；
3. `report_tool.generate` 从 `previous_result["summary_markdown"]` 生成最终 `message`。

### FileTool

`tools/file_tool.py` 负责：

- 从 `user_input` 中识别第一个存在的 `.txt` 或 `.md` 路径；
- 支持相对路径和绝对路径；
- 如果找到文件，读取 UTF-8 文本；
- 如果没有找到文件，则把 `user_input` 当作文本内容；
- 返回 `content`、`source_type`、`source`、`message`。

### TextTool

`tools/text_tool.py` 负责：

- 从 `previous_result["content"]` 或 `user_input` 中取待总结文本；
- 通过 `LLMClient.from_config()` 调用 LLM；
- 要求 LLM 输出中文 Markdown，包含：
  - 摘要
  - 核心观点
  - 关键事实
  - 待办事项
  - 风险点
- 返回 `summary_markdown` 和 `message`；
- 如果没有可总结文本，返回失败结果交给 Executor 捕获；
- 如果 LLM 异常，抛出清楚错误，Executor 转成 `ToolResult(success=False)`。

### ReportTool

`tools/report_tool.py` 负责：

- 从 `previous_result["summary_markdown"]` 读取总结；
- 返回最终 `report_markdown` 和 `message`；
- 不再调用 LLM；
- 如果前一步没有总结文本，返回一个清楚的默认失败报告。

## 错误处理

- `FileTool` 文件读取失败时抛出异常，由 `Executor` 包装为 `tool_error`；
- `TextTool` 没有文本或 LLM 调用失败时抛出异常，由 `Executor` 包装为 `tool_error`；
- `run_minimal_loop()` 在任一步 `Verifier` 不通过时停止，`state.status="failed"`；
- CLI 输出 `任务失败：...`，不打印堆栈；
- `.env` 仍然只保存在本地，不提交。

## 测试策略

所有测试不依赖真实网络：

1. `FileTool` 单元测试：
   - 有文件路径时读取文件；
   - 没有文件路径时使用输入文本；
2. `TextTool` 单元测试：
   - fake LLM 返回总结时，工具返回 `summary_markdown`；
   - 缺少文本时抛出异常；
3. `ReportTool` 单元测试：
   - 能把前一步总结作为最终 `message`；
4. `Router` 测试：
   - 第二步 action 参数包含上一步 `previous_result`；
5. `Loop/Main` 测试：
   - fake LLM + summary task 最终输出真实总结文本，而不是 `mock result`；
6. 完整测试：
   - `.venv/bin/python -m pytest -v`；
   - CLI demo 在有本地 `.env` 时可以调用真实 LLM。

## 验收

完成后应满足：

- `python main.py --task "帮我总结 examples/summarize_example.txt"` 能输出真实总结；
- state 中保留三步计划和每步结果；
- log 中能看到 Planner、Router、Executor、Verifier 的关键节点；
- 没有真实 API key 被提交；
- tag 为 `v0.4-summary-demo`。

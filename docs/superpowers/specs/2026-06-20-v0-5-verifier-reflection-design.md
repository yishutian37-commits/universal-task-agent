# UTA V0.5 Verifier + Reflection 设计

## 背景

当前 `v0.4-summary-demo` 已经能完成真实文本总结：

- `file_tool` 读取本地文本或使用用户输入；
- `text_tool` 调用 LLM 生成中文 Markdown 总结；
- `report_tool` 输出最终报告；
- `run_minimal_loop()` 按 Planner 的步骤顺序执行，并把上一步结果传给下一步。

但当前 `Verifier` 仍然只判断 `ToolResult.success`。这会导致一个问题：只要工具调用成功，即使总结缺少必要小节，Agent 也会当作成功。v0.5 的目标是让 Agent 具备最小“自检和修复”能力。

## 目标

完成 `v0.5-verifier-reflection`：

1. `Verifier` 支持文本总结结构性硬条件校验；
2. `Reflection` 可以把校验失败分类，并给出修复方向；
3. `run_minimal_loop()` 支持单个 step 的有限重试；
4. 重试时把校验失败原因和修复建议传给工具；
5. `TextTool` 在收到修复建议时，把建议加入 LLM prompt；
6. 保留 L1 数字一致性规则接口，但不在 v0.5 主流程强制接入表格分析；
7. 完成后打 tag：`v0.5-verifier-reflection`。

## 非目标

v0.5 不做：

- 不实现真实 `table_tool`；
- 不做 CSV / Excel 读取；
- 不实现完整 replan；
- 不做 LLM 语义级来源判断；
- 不接 Memory / Skill / TAM；
- 不改变 CLI 的基本使用方式。

## 方案选择

### 方案 A：只增强 Verifier

只检查报告是否包含必要小节，失败就直接终止。

优点：最小改动。缺点：没有体现 PRD 里的 Reflection 和重试，用户需要手动再跑。

### 方案 B：Verifier + 规则 Reflection + 单步重试

Verifier 做结构硬校验；Reflection 用 Python 规则分类失败；Loop 在当前 step 内重试，不做完整 replan。

优点：贴合 v0.5 的学习目标，稳定、可测试、不会提前扩大到 v0.6。缺点：暂时没有复杂重规划。

### 方案 C：完整 Reflection + Replan

实现 PRD 伪代码里的外层 replan、失败 step 后继续执行、完整 Planner.replan。

优点：更接近 v1.0。缺点：当前工具链和表格能力还不完整，容易把 v0.5 做得过大。

选择方案 B。

## 结构性硬条件

### 文本总结

当 `state.task_type == "summarize"` 且当前工具是 `report_tool` 时，`Verifier` 检查最终报告：

1. 包含 `摘要` 小节；
2. 包含 `核心观点` 小节；
3. 包含 `风险点` 小节；
4. 三个小节内容非空。

小节标题兼容：

- `## 摘要`
- `### 摘要`
- `摘要：`
- `摘要`

同理适用于 `核心观点`、`风险点`。

### 表格分析 L1 数字一致性

v0.5 新增一个纯规则方法：

```python
Verifier().check_table_numbers(report_text, table_stats)
```

它检查报告中的行数、列数、缺失值数量、异常值数量是否与 `table_stats` 完全一致。v0.5 只加单元测试和接口，不把它接入主流程，因为真实表格分析在 v0.6。

## Reflection

新增 `core/reflection.py`：

```python
class Reflection:
    def analyze(self, state, step, result, check) -> Feedback:
        ...
```

规则：

- 工具执行失败：`failure_type="tool_error"`；
- 报告缺少小节或小节为空：`failure_type="incomplete_output"`；
- 数字一致性失败：`failure_type="violated_constraint"`；
- 其他失败：`failure_type="format_error"`。

Reflection 返回现有 `Feedback` dataclass：

- `root_cause`：失败原因汇总；
- `repair_strategy`：下一次重试应如何修；
- `need_replan=False`；
- `need_user_input=False`。

## Loop 重试

`run_minimal_loop()` 继续保持单计划顺序执行，但每个 step 增加内层重试：

```text
for step in plan.steps:
  attempts = 0
  while attempts <= step.max_retries:
    action = router.choose_tool(...)
    action.params["feedback"] = 上一次 feedback
    result = executor.run(action)
    check = verifier.check(state, step, result)
    if check.passed:
      step completed
      break
    feedback = reflection.analyze(...)
    state.feedbacks.append(feedback)
    attempts += 1
  如果仍失败：state failed
```

语义保持 PRD 约定：

- `max_retries=2` 表示失败后最多再重试 2 次；
- 总尝试次数为 3 次；
- v0.5 不做完整 replan，达到重试上限后失败。

## TextTool 修复建议接入

`TextTool` 读取 `params["feedback"]`。如果存在修复建议，就追加到用户 prompt：

```text
上一次输出未通过校验，请按以下修复建议重新生成：
- 补齐风险点小节
```

这样当第一次 LLM 输出缺小节时，第二次有机会补齐。

## 日志和状态

v0.5 会继续保存：

- `checks`：每次尝试的校验结果；
- `feedbacks`：每次失败后的反思结果；
- `results`：每次工具执行结果。

log 增加：

- `[Reflection] failure_type = ...`
- `[Reflection] repair_strategy = ...`

## 测试策略

全部自动测试都不依赖真实网络：

1. `Verifier`：
   - 完整总结通过；
   - 缺少 `风险点` 失败；
   - 空小节失败；
   - 工具失败仍失败；
   - 表格 L1 数字一致性纯函数测试；
2. `Reflection`：
   - 缺小节返回 `incomplete_output`；
   - 工具错误返回 `tool_error`；
3. `Loop`：
   - 第一次报告缺小节、第二次补齐时完成；
   - 连续失败超过 `max_retries` 后失败；
4. `TextTool`：
   - feedback 会进入 LLM prompt；
5. `Main`：
   - state/log 能保存 check 和 feedback。

## 验收

完成后应满足：

- `.venv/bin/python -m pytest -v` 全部通过；
- 真实 CLI 总结仍可运行；
- 当报告缺少必要小节时，Verifier 能拦截；
- Reflection 能写入 `state.feedbacks`；
- Loop 能在当前 step 内重试；
- tag 为 `v0.5-verifier-reflection`。

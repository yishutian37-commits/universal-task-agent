# UTA V0.1 最小骨架设计

## 1. 背景

本文档按照 `universal_task_agent_prd_v6_1_final_start.md` 编写。

当前交付目标是 `v0.1-skeleton`：先做一个不接 LLM 的最小可运行 UTA 骨架。这个阶段的重点不是“智能”，而是把 Agent 的第一条执行链路跑通、看懂、能测试、能打日志、能打 Git tag。

本阶段不做 TAM Memory、Task Parser、Planner、Router、Reflection、JSON Memory、Skill Builder、Skill Loader。

## 2. 本阶段范围

V0.1 只支持下面这条流程：

```text
CLI 输入任务
-> 创建 AgentState，task_type 写死为 summarize
-> 创建硬编码的单步 Plan
-> 创建硬编码 Action，指向 mock_tool
-> Executor 执行 MockTool
-> Verifier 检查 ToolResult.success
-> 保存 state 和 log 到 outputs/
-> CLI 打印最终 mock 结果
```

完成标志：

运行下面命令后：

```bash
python main.py --task "帮我总结一段文本"
```

程序应该：

1. 生成一个完成状态的 state 文件；
2. 生成一份可读日志；
3. 在终端打印 `任务已完成：mock result`。

## 3. 模块设计

`main.py` 是唯一 CLI 入口。它负责读取 `--task` 参数，创建 `AgentState`，调用最小 Loop，保存运行产物，并打印结果。

`core/state.py` 保存 V0.1 需要的所有数据结构：`Task`、`PlanStep`、`Plan`、`Action`、`ToolResult`、`CheckResult`、`Feedback`、`AgentState`。它还负责把这些 dataclass 转成能写入 JSON 的字典。

`tools/base_tool.py` 定义工具接口。`tools/mock_tool.py` 实现一个固定返回成功结果的假工具。`tools/registry.py` 暴露工具注册表：`TOOL_REGISTRY = {"mock_tool": MockTool()}`。

`core/executor.py` 只负责执行工具。它接收 `Action`，根据 `tool_name` 从注册表找工具，调用工具，并且无论成功失败都返回统一的 `ToolResult`。

`core/verifier.py` 只做 V0.1 最小校验：检查 `ToolResult.success` 是否为 `True`。它不判断总结质量，也不做来源校验。

`core/loop.py` 串起最小流程：创建硬编码 Plan，设置 `state.current_step_id`，创建 mock action，调用 Executor，调用 Verifier，把 result 和 check 写回 state，最后把 step 和 state 标记为 `completed` 或 `failed`。

## 4. 数据流

1. `main.py` 接收用户输入的任务字符串。
2. `main.py` 创建 `AgentState`，其中 `task_type="summarize"`，`intent="v0.1 hard-coded summarize skeleton"`。
3. `run_minimal_loop(state)` 创建单步计划：`PlanStep(step_id=1, goal="执行 V0.1 mock 工具")`。
4. Loop 创建 `Action(tool_name="mock_tool", action_name="run", params={"user_input": state.user_input})`。
5. `Executor.run(action)` 调用 `MockTool.run(...)`。
6. `Verifier.check(result)` 判断工具是否执行成功。
7. Loop 更新 state 和 final output。
8. `main.py` 写入 `outputs/states/<task_id>_state.json` 和 `outputs/logs/<task_id>.log`。

## 5. 错误处理

如果工具注册表里找不到指定工具，Executor 返回：

```text
ToolResult(success=False, error="tool_unavailable: ...")
```

如果工具执行时抛出异常，Executor 捕获异常并返回：

```text
ToolResult(success=False, error="tool_error: ...")
```

如果 Verifier 不通过，Loop 会：

1. 把当前 step 标记为 `failed`；
2. 把 `state.status` 设置为 `failed`；
3. 把失败原因写入 `state.checks`；
4. 在导出的 state 文件里保留错误信息。

V0.1 不做重试。两层 Loop 里的“失败后 Reflection + Retry + Replan”从后续版本开始实现。

## 6. 测试设计

本阶段用小而清楚的单元测试覆盖每个模块：

1. `test_state.py`：验证 `AgentState` 可以导出成 JSON 兼容字典。
2. `test_mock_tool.py`：验证 `MockTool` 返回固定成功结果 `mock result`。
3. `test_executor.py`：验证 Executor 能执行已注册工具、能处理工具不存在、能捕获工具异常。
4. `test_verifier.py`：验证 Verifier 对成功结果通过、对失败结果不通过。
5. `test_loop.py`：验证最小 Loop 能把 state 跑到 completed，并记录一个 result 和一个 check。
6. `test_main.py`：验证 CLI 能在指定输出目录写入 state 和 log。

实现时遵守 TDD：先写失败测试，看见它失败，再写最小生产代码让它通过。

## 7. Git 和版本

本阶段完成后，需要提交清晰的 Git 记录，并打 tag：

```bash
git tag v0.1-skeleton
```

当前目录一开始是空目录，所以项目会先初始化 Git，再提交设计文档、实现代码和测试。

## 8. 明确不做

V0.1 不做下面这些内容：

1. 不调用 LLM；
2. 不解析 task type；
3. 不动态生成 plan；
4. 不按规则选择工具；
5. 不读取真实文件；
6. 不生成真实摘要；
7. 不写入 Memory；
8. 不加载 Skill；
9. 不接入 TAM。

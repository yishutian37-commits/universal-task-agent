# UTA V0.3 Planner Router 设计

## 1. 背景

本文档按照 `universal_task_agent_prd_v6_1_final_start.md` 编写。

当前项目已经完成：

1. `v0.1-skeleton`：CLI、AgentState、MockTool、Executor、Verifier、最小 Loop；
2. `v0.2-llm-parser`：LLMClient、TaskParser，可以识别 `summarize` / `data_analysis` / `unknown`。

`v0.3-planner-router` 的目标是新增 Planner 和 Router，让 Agent 从“知道任务类型”推进到“能生成步骤，并为步骤选择工具”。

## 2. 本阶段范围

V0.3 支持下面这条流程：

```text
CLI 输入任务
-> TaskParser 识别 task_type
-> Planner 根据 task_type 生成 Plan
-> Loop 按 Plan 的 Step 顺序执行
-> Router 根据 Step.goal 选择 Action
-> Executor 执行 Action
-> Verifier 检查 ToolResult.success
-> 保存 state 和 log
```

完成标志：

1. `Planner` 可以为 `summarize` 生成 3 个步骤；
2. `Planner` 可以为 `data_analysis` 生成 3 个步骤；
3. `Planner` 遇到 `unknown` 时生成保守的 1 个 mock 步骤；
4. `PlanStep` 只包含目标 `goal`，不包含工具名；
5. `Router` 可以根据 `goal` 关键词选择工具；
6. `Router` 每次选择都返回 `reason`；
7. 主流程使用 Planner + Router，不再在 Loop 里硬编码 Plan 和 Action；
8. 输出仍然可以是 `mock result`，因为真实总结在 v0.4 才做。

## 3. 关键边界

Planner 和 Router 的职责必须分开：

```text
Planner：这一步要干什么
Router：这一步用什么工具干
Executor：真正执行工具
```

因此 Planner 不能输出 `tool_name`、`action_name` 或任何工具参数。

Router 不能执行工具，只能返回 `Action`。

Executor 仍然只负责执行工具，不判断结果质量。

## 4. 模块设计

### 4.1 `core/planner.py`

`Planner` 接收 `Task`，返回 `Plan`。

V0.3 可以先用固定模板，不强依赖 LLM。这样可以稳定验证 Planner / Router 的职责边界，避免 v0.3 被 LLM 输出不稳定卡住。

接口：

```python
class Planner:
    def create_plan(self, task: Task) -> Plan:
        ...
```

`summarize` 默认步骤：

```text
1. 读取输入内容
2. 提取核心信息
3. 生成结构化报告
```

`data_analysis` 默认步骤：

```text
1. 读取表格文件
2. 分析字段、行数、列数和缺失值
3. 生成表格分析报告
```

`unknown` 默认步骤：

```text
1. 执行 V0.3 mock 工具
```

每个 `PlanStep`：

```python
PlanStep(step_id=1, goal="...", status="pending", max_retries=2)
```

### 4.2 `core/router.py`

`Router` 接收 `AgentState` 和 `PlanStep`，返回 `Action`。

接口：

```python
class Router:
    def choose_tool(self, state: AgentState, step: PlanStep) -> Action:
        ...
```

规则：

| goal 关键词 | tool_name | action_name |
|---|---|---|
| 读取 / 文件 / txt / md / csv / excel / 表格文件 | file_tool | read |
| 文本 / 摘要 / 提取 / 核心信息 / 核心观点 / 风险 | text_tool | process |
| 表格 / 字段 / 行数 / 列数 / 缺失值 / 异常值 | table_tool | analyze |
| 报告 / Markdown / 输出 | report_tool | generate |
| mock / 无法判断 | mock_tool | run |

V0.3 先用规则优先；LLM Router 兜底可以保留接口位置，但不强制实现真实 LLM 选择。

原因：V0.3 的学习重点是“Planner 不指定工具，Router 才决策工具”，不是优化 LLM Router。

### 4.3 工具注册表

V0.3 需要在 `tools/registry.py` 里先注册占位工具：

```text
file_tool
text_tool
table_tool
report_tool
```

这些工具在 V0.3 可以继承 `MockTool` 或返回固定结果，因为真实能力在后续版本实现：

1. `text_tool` 的真实总结能力在 v0.4；
2. `table_tool` 的真实表格分析能力在 v0.6；
3. `report_tool` 的真实报告生成能力在 v0.4/v0.6；
4. `file_tool` 的真实读取能力在 v0.4/v0.6。

这样 Router 选到这些工具时，Executor 不会因为工具不存在而失败。

## 5. 主流程改造

`core/loop.py` 从 v0.1 的硬编码：

```text
create_v0_1_plan()
create_v0_1_action()
```

升级为：

```text
Planner.create_plan(task)
for step in plan.steps:
    Router.choose_tool(state, step)
    Executor.run(action)
    Verifier.check(result)
```

V0.3 可以先执行完整 plan，也可以为了保持最小复杂度只执行第一个 step。

本设计选择：**执行完整 plan**。

理由：

1. PRD 中 Planner 生成的是多步计划；
2. 执行完整 plan 更能体现 Agent Loop 的外层循环；
3. V0.3 工具都是占位工具，不会引入复杂真实业务逻辑。

## 6. 输出和日志

CLI 输出仍然可以是：

```text
任务已完成：mock result
```

或者最后一个工具的 message。

log 需要增加：

```text
[Planner] created 3 steps
[Loop] step 1 started: 读取输入内容
[Router] selected tool = file_tool, reason = ...
[Loop] step 2 started: 提取核心信息
[Router] selected tool = text_tool, reason = ...
```

state 中需要保存：

1. `plan`；
2. `current_action` 保存最近一次 Action；
3. `results` 保存每一步的 ToolResult；
4. `checks` 保存每一步的 CheckResult；
5. 最终 `status`。

## 7. 错误处理

V0.3 错误处理保持简单：

1. Router 无法判断时返回 `mock_tool`，reason 说明使用兜底；
2. Executor 找不到工具时返回 `tool_unavailable`；
3. Verifier 不通过时，当前 step 和 state 标记为 `failed`；
4. V0.3 不做 Reflection，也不做 retry/replan。

## 8. 测试设计

新增测试：

1. `tests/test_planner.py`
   - summarize 生成 3 个 goal；
   - data_analysis 生成 3 个 goal；
   - unknown 生成 1 个 mock goal；
   - PlanStep 不包含工具字段。

2. `tests/test_router.py`
   - 读取类 goal 路由到 `file_tool`；
   - 文本提取类 goal 路由到 `text_tool`；
   - 表格统计类 goal 路由到 `table_tool`；
   - 报告类 goal 路由到 `report_tool`；
   - 无法判断时路由到 `mock_tool`；
   - 每个 Action 都有 reason。

3. `tests/test_loop.py`
   - loop 可以执行完整 plan；
   - results/checks 数量等于 plan steps 数量；
   - 所有 step 完成时 state 为 `completed`。

4. `tests/test_main.py`
   - CLI state 文件中保存多步 plan；
   - log 中出现 Planner 和 Router 信息。

## 9. 明确不做

V0.3 不做下面内容：

1. 不做真实文本总结；
2. 不做真实文件读取；
3. 不做真实表格分析；
4. 不做 Markdown 报告生成；
5. 不做 Reflection；
6. 不做 retry/replan；
7. 不做 Memory；
8. 不做 Skill；
9. 不接入 TAM。

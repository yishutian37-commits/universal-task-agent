# UTA V1.0 学习版与记忆可见性设计

> 状态：待进入实施计划
> 日期：2026-06-23

## 目标

这次要把 PRD v6.1 里的 UTA V1.0 学习版主线收口，但不把范围扩大成桌面端产品化，也不接 TAM。

本次 V1.0 实现范围只做四件事：

1. 补 A11：支持一次 replan，并且从失败步骤之后继续，不重跑前面已经成功的步骤。
2. 更新 README、CHANGELOG 和明显的版本说明。
3. 跑一遍文本总结 demo 和表格分析 demo，留下验收结果。
4. 验收通过后打 `v1.0-learning-agent` tag。

记忆系统这次主要做“说清楚”和“设计清楚”：解释短期记忆、长期记忆分别在哪里看，桌面端后续应该怎么做一个直观的记忆入口。V1.0 本次不做 TAM、不做向量库、不做语义检索、不做完整桌面记忆编辑器。

## 当前背景

仓库主线已经完成这些 tag：

```text
v0.1-skeleton
v0.2-llm-parser
v0.3-planner-router
v0.4-summary-demo
v0.5-verifier-reflection
v0.6-data-analysis
v0.7-memory
v0.8-skill-runtime
```

当前桌面分支里还有 macOS 桌面应用、运行记录页、LLM curl fallback 等增强。这些对产品体验有价值，但 PRD 里的 V1.0 不是桌面版，而是核心学习框架：

```text
Task Parser -> Planner -> Agent Loop -> Router -> Executor
-> Verifier -> Reflection -> Replan -> Output -> Memory -> Skill
```

因此，`v1.0-learning-agent` 这个 tag 应该落在干净的核心主线上，也就是从 `main` / `v0.8-skill-runtime` 出发，而不是直接打在桌面端分支头上。这样可以避免把“核心学习版”和“桌面产品化增强”混在一起。

当前 V1.0 最明显的缺口是 A11：

```text
可以重新规划一次（replan 从失败 step 后继续）
```

现在的 `core.loop.run_minimal_loop()` 已经支持单步失败后的 Reflection + retry。但如果 retry 用完，任务会直接失败。现在的 `Reflection.analyze()` 也总是返回 `need_replan=False`。

## V1.0 范围边界

V1.0 包含：

- 可以从 CLI 输入任务：`main.py --task`。
- 可以识别 `summarize` 和 `data_analysis` 两类任务。
- Planner 可以生成结构化计划，而且 `PlanStep` 只包含目标，不指定工具。
- Agent Loop 有两层含义：外层按计划推进，内层对当前步骤重试。
- Router、Executor、Verifier、Reflection、JSON Memory、Skill Builder、Skill Loader 都能跑通。
- 某一步 retry 用完之后，可以触发一次 replan。
- 文本总结和表格分析都能输出 Markdown 报告。
- 能保存 state、log 和长期 JSON Memory。
- README、CHANGELOG、版本说明都准确写到 V1.0。
- 验证通过后打 `v1.0-learning-agent` tag。

V1.0 不包含：

- TAM Memory 接入。
- TAM Output Guard / Faithfulness Gate。
- 语义级记忆检索。
- 自动搜索或调研任务。
- 新的桌面端记忆 UI 实现。
- 编辑或删除记忆。
- 多 Agent 协作。

桌面端“记忆”入口可以在这份设计里规划方向，但默认是 V1.0 之后再做，不塞进本次 V1.0 必做范围。

## Replan 设计

### 行为规则

当某个 plan step 经过 retry 后仍然校验失败：

1. 把当前失败 step 标记为 `failed`。
2. 让 Reflection 给出失败原因和修复建议。
3. 如果不能 replan，或者 `state.max_replans` 已经用完，就像现在一样让任务失败。
4. 如果还能 replan：
   - 为同一个任务重新生成 plan。
   - 保留失败步骤之前已经完成的结果。
   - 从新 plan 中对应的失败位置继续执行。
   - 不重跑前面已经成功的步骤。
   - 把 replan 事件写进 state 和 progress events。

PRD 允许 V1.0 简化 replan，但这次建议实现更清楚一点：前面已经完成的步骤不重跑，失败位置由新 plan 中相同位置的 step 接上。如果新 plan 太短，找不到对应位置，就给出清晰失败信息。

### State 增加字段

`AgentState` 已经有 `max_replans`，建议再加两个字段：

```python
replan_count: int = 0
replan_events: list[dict[str, Any]] = field(default_factory=list)
```

每条 replan event 记录：

- 失败 step id
- 失败 goal
- 失败原因
- 旧 plan 的 goals
- 新 plan 的 goals
- 从哪个 step 继续
- 时间戳

这样 replan 不只是“内部发生过”，而是可以在 `state.json` 里看见。

### Planner 设计

V1.0 不需要很聪明的 replan。第一版保持确定性规则即可：

- `summarize`：重新生成标准总结计划。
- `data_analysis`：重新生成标准表格分析计划。
- 如果命中 Skill：继续从 Skill workflow 生成计划。

这一版的学习重点不是“让 LLM 想出多高级的新计划”，而是让用户看懂：失败、反思、重新规划、从中间继续，这条控制流是怎么工作的。

### Reflection 设计

Reflection 仍然负责解释失败原因和修复建议。

实现时可以选择两种小改法：

1. 保持 `Reflection.analyze()` API 不变，让 Loop 在 retry 用完时决定是否 replan。
2. 给 `Reflection.analyze()` 加一个参数，例如 `retries_exhausted=True`，让 Reflection 返回 `need_replan=True`。

实施计划里应该选择改动更小、测试更清楚的方案。

## 记忆系统设计

### 短期记忆

短期记忆就是当前任务的状态，也就是 `AgentState`。

它回答这些问题：

```text
Agent 现在在做什么？
它已经执行了哪些步骤？
每个工具返回了什么？
哪些校验通过了？
哪些校验失败了？
Reflection 给了什么反馈？
有没有发生 replan？
最终输出是什么？
```

短期记忆的来源：

- 任务运行中的内存对象：`AgentState`
- 保存后的 state 文件：`outputs/states/<task_id>_state.json`
- 保存后的 log 文件：`outputs/logs/<task_id>.log`

现在从哪里看：

- CLI 用户：直接看 `outputs/states/` 和 `outputs/logs/`。
- 桌面端用户：从“运行记录”里查看历史任务的 state、log 和结果。

V1.0 要求：

- replan 信息必须能在 `state.json` 里看到。
- log 里也要能看出发生过 replan。
- README 要明确说明：State 是短期记忆，不是长期记忆。

### 长期记忆

长期记忆是跨任务保存下来的 JSON Memory。

它回答这些问题：

```text
UTA 过去做过什么任务？
哪些成功经验被沉淀了？
哪些失败规则要避免？
哪些任务流程重复成功，值得变成 Skill？
```

长期记忆的来源：

```text
memory/user_profile.json
memory/task_history.json
memory/lessons.json
memory/negative_rules.json
memory/skill_candidates.json
```

在桌面端打包环境里，这些文件默认在：

```text
~/.uta/memory/
```

当前从哪里看：

- CLI 用户：直接打开 `memory/*.json`。
- 桌面端用户：现在还没有专门的“记忆”入口。

V1.0 要求：

- README 要解释每个长期记忆文件是什么。
- demo 验收时要确认任务完成后 memory 有写入。
- V1.0 不要求自动语义召回长期记忆。

## 桌面端记忆可见性方向

V1.0 之后，桌面端建议新增一级入口：**记忆**。

第一版只读，不编辑。目标是先让记忆“看得见、讲得清、追得到来源”。

推荐分成四个 tab：

### 1. 当前任务记忆

展示当前任务或某次历史任务的 `AgentState`。

内容包括：

- plan
- 当前 step
- tool results
- checks
- feedbacks
- replan events
- final output

这部分复用“运行记录”的 state/log 数据。

### 2. 任务历史

读取 `task_history.json`。

展示：

- task id
- task type
- status
- 更新时间
- final output preview

如果存在对应 state 文件，可以跳转到运行记录详情。

### 3. 经验与规则

左侧展示 `lessons.json`，右侧展示 `negative_rules.json`。

`lessons` 是正向经验：以后可以复用什么。

`negative_rules` 是负向规则：以后应该避免什么。

每条都要显示来源任务和创建时间。

### 4. Skill 候选

读取 `skill_candidates.json`。

展示：

- task type
- success count
- latest task id
- status
- reason

这个区域用来解释：普通记忆如何逐步变成可复用能力。

后续再单独设计：

- 删除错误记忆
- 编辑记忆
- 把候选提升为正式 Skill
- 记忆来源追踪和清理

## 版本文档更新

A11 实现后，需要更新这些文件：

### README.md

需要写清楚：

- 当前版本是 `v1.0-learning-agent`。
- V1.0 已完成哪些能力。
- 如何跑文本总结 demo。
- 如何跑表格分析 demo。
- 短期记忆和长期记忆分别是什么。
- TAM 不属于 V1.0 必选范围。

### CHANGELOG.md

新增 `v1.0-learning-agent` 条目，包含：

- A11 replan
- V1.0 demo 验收
- 记忆说明完善
- V1.0 tag

### main.py

把 argparse 里过时的版本描述从旧版本改成 V1.0。

桌面端 README 不作为本次 V1.0 必改项，除非实施计划里只加一句“桌面端属于 V1.0 后体验层”。

## Demo 验收

建议用临时 output root 跑 demo，避免污染正常 outputs：

### 文本总结 demo

```bash
.venv/bin/python main.py \
  --output-root /private/tmp/uta-v1-summary \
  --task "帮我总结一段文本：UTA V1.0 要跑通 Agent Loop、Verifier、Memory 和 Skill。"
```

### 表格分析 demo

```bash
.venv/bin/python main.py \
  --output-root /private/tmp/uta-v1-table \
  --task "分析 examples/orders.csv"
```

验收标准：

- 命令退出码是 0。
- final output 是 Markdown 风格文本。
- `outputs/states/<task_id>_state.json` 存在。
- `outputs/logs/<task_id>.log` 存在。
- memory save 被记录。
- 表格 demo 包含字段说明、基础统计、缺失值、异常数据等内容。

如果真实 LLM key 不可用，测试仍然可以通过，但不能贸然打 V1.0 tag。除非实现一个明确标注的 controlled demo path，并且它符合项目现有的测试注入方式。

## Tag 策略

只有满足以下条件后，才打：

```text
v1.0-learning-agent
```

条件：

- A11 目标测试通过。
- 全量测试通过。
- README 和 CHANGELOG 已更新。
- 文本总结 demo 跑过并检查。
- 表格分析 demo 跑过并检查。
- 没有误暂存无关文件。

因为当前桌面分支包含 V1.0 之后的桌面增强，所以 V1.0 实现应该从 `main` / `v0.8-skill-runtime` 新建干净分支或 worktree。tag 应该指向核心学习版提交，而不是桌面分支头。

## 测试策略

### 单元测试

为 Loop 增加测试：

- step retry 用完后触发一次 replan。
- `max_replans=1` 时最多只 replan 一次。
- replan 后不重跑已经完成的前置 step。
- replan 信息写入 `AgentState.replan_events`。
- replan 用完后任务按原逻辑失败。
- progress events 包含 replan 事件。

如果 Reflection API 改动，再补 Reflection 测试。

### 回归测试

现有能力必须继续通过：

- 文本总结流程
- 表格分析流程
- Reflection retry
- Skill workflow 注入
- JSON Memory 写入
- 桌面分支上的 desktop tests，如果在桌面分支运行

### 文档检查

实施 review 时检查：

- README 不再说当前版本停在 v0.8。
- `main.py` 不再显示旧版本描述。
- CHANGELOG 有 V1.0。
- TAM 仍然明确标注为 V1.0 之外。

## 实施计划里的开放决策

实施计划需要进一步决定：

1. CLI 是否新增 `--memory-root`，让 demo 可以完全隔离 memory 写入。
2. replan 是否只替换当前 `Plan`，还是同时保存旧 plan 快照到 `replan_events`。
3. 桌面端“记忆”视图是在 V1.0 tag 之后马上开新 spec，还是等下一轮。

推荐选择：

- 给 `AgentState` 增加 `replan_events`，方便学习和排查。
- 如果 demo 隔离确实需要，就加 `--memory-root`；否则不加。
- 先打 V1.0，再单独做桌面端记忆可见性 spec。

## 验收标准

这份设计进入实施后，最终应该产出：

- `v1.0-learning-agent` tag 落在核心学习版主线上。
- A11 replan 有测试覆盖。
- README、CHANGELOG、版本说明与 V1.0 一致。
- 文本总结和表格分析 demo 有验收记录。
- 记忆模型在 README 或相关文档里说清楚：
  - 短期记忆 = State / log / 运行记录
  - 长期记忆 = JSON Memory 文件
  - Skill 候选 = 从记忆走向可复用能力
  - 桌面端记忆面板 = V1.0 后的只读可见性工作

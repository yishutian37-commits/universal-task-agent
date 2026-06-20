# UTA V0.7 JSON Memory 设计

## 背景

当前 `v0.6-data-analysis` 已经跑通两类核心任务：

- 文本总结：读取文本、生成结构化总结、校验必要小节、失败后 Reflection 重试；
- 表格分析：读取 CSV / Excel、生成基础统计和表格报告、校验字段覆盖和数字一致性；
- 每次运行都会保存 `AgentState` 和日志到 `outputs/`。

但这些信息仍然只属于单次任务。PRD 要求 v0.7 实现 UTA 自带的基础 JSON Memory，让 Agent 开始区分：

- `State`：单次任务内的短期状态；
- `Memory`：跨任务保留的长期 JSON 记录。

v0.7 不追求智能检索，重点是建立稳定、可测试、可解释的跨任务文件写入。

## 目标

完成 `v0.7-memory`：

1. 新增 `memory_providers/base_memory_provider.py`，定义最小 MemoryProvider 接口；
2. 新增 `memory_providers/json_memory_provider.py`，实现 UTA 自带 JSON Memory；
3. 首次运行时自动创建 `memory/` 目录和 5 个 JSON 文件；
4. 每次任务完成后保存 `task_history`；
5. 成功任务保存一条可复用 `lesson`；
6. 失败任务保存一条 `negative_rule`；
7. 成功任务更新 `skill_candidates`，给 v0.8 Skill Builder 铺垫；
8. CLI / `run_task()` 默认启用 JSON Memory；
9. README / CHANGELOG 更新 v0.7 说明；
10. 完成后打 tag：`v0.7-memory`。

## 非目标

v0.7 不做：

- 不接 TAM；
- 不做向量库；
- 不做语义检索；
- 不把 Memory 注入 Planner；
- 不做 Output Guard；
- 不自动生成正式 Skill 文件；
- 不保存用户 API key、原始大段输入或完整报告全文；
- 不改变现有 CLI 参数的基本使用方式。

## 方案选择

### 方案 A：JsonMemoryProvider + 任务后写入

新增独立 `memory_providers/` 包。`run_task()` 在 Agent Loop 完成后调用 `memory_provider.save_task(state)`，由 provider 负责写入 JSON 文件。

优点：边界清晰，符合 PRD；不污染 Loop / Tool；v0.8 可以继续读取 `skill_candidates.json`。缺点：v0.7 只写入，不做智能调用。

### 方案 B：只保存 task_history

只实现 `memory/task_history.json`。

优点：最快。缺点：没有 `lessons` / `negative_rules` / `skill_candidates`，v0.8 缺少铺垫，也不符合 PRD 对 v0.7 的完整目标。

### 方案 C：Memory 检索并注入 Planner

在任务开始前读取历史，影响 Planner 计划。

优点：更像真正有记忆的 Agent。缺点：会把 v0.7 扩大到规划策略，容易和 v0.8 / v1.0 混在一起。

选择方案 A。

## 文件结构

新增代码：

```text
memory_providers/
├── __init__.py
├── base_memory_provider.py
└── json_memory_provider.py
```

运行时创建：

```text
memory/
├── user_profile.json
├── task_history.json
├── lessons.json
├── negative_rules.json
└── skill_candidates.json
```

`memory/` 是项目学习产物，默认进入 Git 跟踪。它不保存密钥，不保存完整原文，只保存任务摘要级记录。

## JSON 文件格式

### user_profile.json

v0.7 先保留基础结构，不做复杂用户画像：

```json
{
  "version": 1,
  "profile": {},
  "updated_at": null
}
```

### task_history.json

```json
{
  "version": 1,
  "tasks": [
    {
      "task_id": "task_20260620_230000",
      "task_type": "data_analysis",
      "intent": "analyze_table",
      "status": "completed",
      "final_output_preview": "## 字段说明...",
      "result_count": 3,
      "check_count": 3,
      "feedback_count": 0,
      "created_at": "2026-06-20 23:00:00",
      "updated_at": "2026-06-20 23:00:01"
    }
  ]
}
```

规则：

- `tasks` 按运行顺序追加；
- 同一个 `task_id` 重复保存时更新旧记录，不重复追加；
- `final_output_preview` 最多保存 300 个字符。

### lessons.json

```json
{
  "version": 1,
  "lessons": [
    {
      "lesson_id": "lesson_task_20260620_230000",
      "task_id": "task_20260620_230000",
      "task_type": "summarize",
      "content": "summarize 任务已成功跑通，可复用流程：读取输入 -> 处理内容 -> 生成报告。",
      "source": "completed_task",
      "created_at": "2026-06-20 23:00:01"
    }
  ]
}
```

规则：

- 只对 `state.status == "completed"` 的任务写 lesson；
- lesson 只保存流程级经验，不保存原始正文。

### negative_rules.json

```json
{
  "version": 1,
  "negative_rules": [
    {
      "rule_id": "negative_task_20260620_230000",
      "task_id": "task_20260620_230000",
      "task_type": "data_analysis",
      "content": "失败任务需要避免重复：缺少必要小节：基础统计。",
      "source": "failed_task",
      "created_at": "2026-06-20 23:00:01"
    }
  ]
}
```

规则：

- 只对 `state.status != "completed"` 的任务写 negative rule；
- 优先使用最后一个 `CheckResult.failed_reasons`；
- 如果没有 check，就使用 `state.final_output`。

### skill_candidates.json

```json
{
  "version": 1,
  "candidates": [
    {
      "task_type": "summarize",
      "success_count": 3,
      "latest_task_id": "task_20260620_230000",
      "status": "candidate",
      "reason": "summarize 已成功执行 3 次，可在 v0.8 评估是否沉淀为 Skill。",
      "updated_at": "2026-06-20 23:00:01"
    }
  ]
}
```

规则：

- 每个 `task_type` 一条候选记录；
- 成功任务使 `success_count += 1`；
- 当 `success_count >= 3` 时，`status="candidate"`；
- 小于 3 时，`status="tracking"`。

## Provider 接口

`BaseMemoryProvider` 使用抽象基类，v0.7 只定义最小接口：

```python
class BaseMemoryProvider(ABC):
    @abstractmethod
    def save_task(self, state: AgentState) -> None:
        ...

    @abstractmethod
    def load_context(self) -> dict:
        ...
```

`JsonMemoryProvider` 实现：

- `save_task(state)`：写入 task_history / lesson / negative_rule / skill_candidate；
- `load_context()`：读取 5 个文件并返回 dict；
- `ensure_store()`：创建目录和默认文件；
- `_read_json()` / `_write_json()`：集中处理 UTF-8 JSON 读写。

## run_task 接入

`main.run_task()` 增加可注入参数：

```python
def run_task(..., memory_provider=None) -> AgentState:
    ...
```

默认行为：

- `memory_provider is None` 时使用 `JsonMemoryProvider()`；
- 传入 `False` 时跳过 Memory 写入，方便单元测试或临时关闭；
- 传入自定义 provider 时调用它的 `save_task(state)`。

写入时机：

```text
TaskParser -> Loop -> memory_provider.save_task(state) -> save state/log
```

这样 `state.memory_saved` 可以同时出现在 state JSON 和 log 中。

Memory 写入失败时，v0.7 让异常抛出并被测试捕捉，不静默吞掉。这样学习阶段更容易看到文件权限或 JSON 格式问题。

## 日志

`build_log_lines()` 增加一行：

```text
[Memory] saved = true
```

如果禁用 Memory，则写：

```text
[Memory] saved = false
```

实现方式是在 `AgentState` 上新增轻量字段：

```python
memory_saved: bool = False
```

该字段会随 state JSON 一起保存，帮助用户理解“这次任务有没有写入长期记忆”。

## 测试策略

全部测试不访问真实网络。

1. `JsonMemoryProvider`：
   - 首次初始化创建 5 个默认 JSON 文件；
   - 成功任务写入 `task_history` 和 `lessons`；
   - 失败任务写入 `task_history` 和 `negative_rules`；
   - 连续 3 次成功同类任务后，`skill_candidates` 状态变成 `candidate`；
   - 同一个 `task_id` 重复保存时不重复追加历史；
2. `main.run_task()`：
   - 默认写入 memory；
   - `memory_provider=False` 时跳过写入；
   - 自定义 fake provider 会被调用；
3. 日志：
   - Memory 写入后 log 包含 `[Memory] saved = true`；
4. 回归：
   - summarize 和 data_analysis CLI 主流程仍通过；
   - `.venv/bin/python -m pytest -v` 全部通过。

## 验收

完成后应满足：

- `.venv/bin/python -m pytest -v` 全部通过；
- `.venv/bin/python main.py --task "分析 examples/orders.csv"` 后生成 / 更新 `memory/*.json`；
- `memory/task_history.json` 能看到刚才任务；
- `memory/lessons.json` 对成功任务有流程经验；
- `memory/skill_candidates.json` 会累计任务类型成功次数；
- `git grep` 不包含真实 API key；
- tag 为 `v0.7-memory`。

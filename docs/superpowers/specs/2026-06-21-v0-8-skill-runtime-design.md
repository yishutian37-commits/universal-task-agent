# UTA V0.8 Skill Runtime 设计

## 背景

`v0.7-memory` 已经让 UTA 在任务结束后写入基础 JSON Memory，并能在 `memory/skill_candidates.json` 中累计 Skill 候选。下一步 `v0.8-skill-runtime` 要把 PRD 里的 Skill 闭环接起来：

```text
Memory 识别候选 -> 人工确认成 Skill 文件 -> 任务开始时加载 Skill -> Planner 使用 Skill workflow
```

这一版仍然保持学习项目的节奏：先做可读、可测、可解释的本地文件机制，不做复杂语义匹配，不接 TAM，不让 LLM 自动发布 Skill。

## 目标

完成 `v0.8-skill-runtime`：

1. 新增 `core/skill_loader.py`，从本地 `skills/*.md` 读取正式 Skill；
2. 新增 `core/skill_builder.py`，把 `memory/skill_candidates.json` 中的候选转换成可人工 review 的草稿 Markdown；
3. 新增 `skills/` 示例 Skill 文件，覆盖文本总结和表格分析两类已有任务；
4. `run_task()` 在 TaskParser 后调用 SkillLoader，命中后写入 `state.matched_skill`；
5. `Planner.create_plan()` 支持 `matched_skill`，优先用 Skill 的 `workflow` 生成计划；
6. 日志记录 Skill 命中情况；
7. README / CHANGELOG 更新 v0.8 使用说明；
8. 完成后打 tag：`v0.8-skill-runtime`。

## 非目标

v0.8 不做：

- 不自动把草稿发布到正式 `skills/`；
- 不让 LLM 判断 Skill 命中；
- 不做向量检索或相似度匹配；
- 不接 TAM；
- 不把 Skill 变成外部插件系统；
- 不改变 Tool / Router 的核心协议；
- 不支持任意 YAML，只支持本项目定义的 front matter 子集。

## 方案选择

### 方案 A：本地 Markdown Skill + 规则匹配 + Planner 注入

Skill 用 Markdown 文件保存，文件头部是受限 front matter。Loader 读取 `skills/*.md`，按 `task_type` 和关键词做确定性匹配；Planner 命中 Skill 时使用 Skill 的 `workflow`，未命中时保持现有默认计划。

优点：符合 PRD 的闭环，行为可测试，不引入新依赖。缺点：匹配不够智能，但适合 v0.8。

### 方案 B：只做 Builder，不做 Loader

只从 Memory 生成候选草稿，不影响运行时。

优点：风险最低。缺点：没有“加载 -> 注入”的闭环，不符合 v0.8 tag 的目标。

### 方案 C：Loader 用 LLM 或向量检索匹配

把用户任务和 Skill 描述交给 LLM 或向量检索判断是否命中。

优点：更灵活。缺点：测试不稳定，依赖更重，和当前学习阶段不匹配。

选择方案 A。

## 文件结构

新增代码：

```text
core/
├── skill_builder.py
└── skill_loader.py
```

新增 Skill 文件：

```text
skills/
├── summarize_article.md
├── analyze_table.md
└── drafts/
```

新增测试：

```text
tests/
├── test_skill_builder.py
└── test_skill_loader.py
```

修改现有文件：

```text
core/planner.py
core/loop.py
main.py
README.md
CHANGELOG.md
examples/expected_output_examples.md
tests/test_planner.py
tests/test_main.py
```

## Skill 文件格式

正式 Skill 使用 Markdown + front matter：

```markdown
---
id: summarize_article
name: 文本总结 Skill
version: 1
enabled: true
task_type: summarize
priority: 100
trigger_keywords:
  - 总结
  - 摘要
workflow:
  - 读取输入内容
  - 提取核心信息
  - 生成结构化报告
---

# 文本总结 Skill

适用于把一段中文文本整理成结构化摘要。
```

必填字段：

- `id`
- `name`
- `task_type`
- `workflow`

可选字段：

- `version`：默认 `1`
- `enabled`：默认 `true`
- `priority`：默认 `0`
- `trigger_keywords`：为空时只按 `task_type` 命中

解析规则：

- 只解析文件开头的 `---` front matter；
- 支持字符串、整数、布尔值和缩进列表；
- 不支持嵌套对象；
- 文件格式错误时跳过该 Skill，并记录到 Loader 的 `errors` 列表；
- Loader 只扫描 `skills/*.md`，不递归扫描 `skills/drafts/`。

## SkillLoader

`core/skill_loader.py` 负责运行时加载和匹配。

接口：

```python
class SkillLoader:
    def __init__(self, skills_root: Path | str = "skills"):
        ...

    def load_skills(self) -> list[dict]:
        ...

    def match(self, task: Task) -> dict | None:
        ...
```

匹配规则：

1. `enabled == false` 的 Skill 不参与匹配；
2. `task_type` 必须和当前任务一致；
3. 如果 `trigger_keywords` 非空，则至少一个关键词要出现在 `task.user_input` 或 `task.intent` 中；
4. 如果多个 Skill 命中，按 `priority` 降序选择；
5. `priority` 相同则按 `id` 字典序选择，保证结果稳定；
6. 没有命中时返回 `None`。

返回的 `matched_skill` 是可 JSON 序列化的 dict，至少包含：

```json
{
  "id": "summarize_article",
  "name": "文本总结 Skill",
  "task_type": "summarize",
  "workflow": ["读取输入内容", "提取核心信息", "生成结构化报告"],
  "source_path": "skills/summarize_article.md"
}
```

## SkillBuilder

`core/skill_builder.py` 负责把候选沉淀成草稿，不参与运行时匹配。

接口：

```python
class SkillBuilder:
    def __init__(self, drafts_root: Path | str = "skills/drafts"):
        ...

    def build_draft(self, candidate: dict, workflow: list[str]) -> str:
        ...

    def write_draft(self, candidate: dict, workflow: list[str]) -> Path:
        ...
```

行为：

- 只处理 `status == "candidate"` 的候选；
- 草稿写入 `skills/drafts/<task_type>.md`；
- 草稿包含同样的 front matter 格式；
- 草稿不会被 SkillLoader 自动加载；
- 用户人工确认后，可以把草稿移动到 `skills/` 根目录成为正式 Skill。

v0.8 提供 Builder 能力和测试，不在 CLI 默认任务运行中自动生成草稿。这样可以防止一次普通任务运行悄悄改写 Skill 库。

## Planner 注入

`Planner.create_plan()` 增加可选参数：

```python
def create_plan(self, task: Task, matched_skill: dict | None = None) -> Plan:
    ...
```

规则：

- 如果 `matched_skill` 存在且 `workflow` 是非空 list，则使用 `workflow` 生成 `PlanStep`；
- 否则沿用当前 `_goals_for(task.task_type)`；
- Planner 不关心 Skill 匹配原因，只消费 workflow；
- Router 继续按 step goal 选择 Tool，不新增 Tool 协议。

## run_task 接入

`main.run_task()` 增加可注入参数：

```python
def run_task(..., skill_loader=None) -> AgentState:
    ...
```

默认行为：

- `skill_loader is None` 时使用 `SkillLoader()`；
- `skill_loader is False` 时跳过 Skill 匹配，方便测试；
- 传入自定义 loader 时调用它的 `match(task)`。

执行顺序：

```text
TaskParser -> SkillLoader.match -> state.matched_skill -> Planner -> Loop -> Memory
```

`core.loop.run_minimal_loop()` 使用 `state.matched_skill` 调用 Planner。

## 日志和 State

`AgentState.matched_skill` 已经存在，v0.8 继续使用该字段，不新增状态字段。

日志新增一行：

```text
[SkillLoader] matched_skill = summarize_article
```

未命中时：

```text
[SkillLoader] matched_skill = none
```

State JSON 中会保存 `matched_skill`，方便用户看到本次计划是否来自 Skill。

## 示例 Skill

v0.8 提交两个人工确认的示例 Skill：

- `skills/summarize_article.md`
- `skills/analyze_table.md`

它们的 workflow 与现有默认 Planner 目标保持一致。这样第一版 Skill Runtime 先证明“命中、注入、执行、记录”链路，不改变已有任务输出。

## 测试策略

新增单元测试：

- Loader 可以读取合法 Skill；
- Loader 忽略 disabled Skill；
- Loader 按 task_type 和关键词匹配；
- Loader 多命中时按 priority 选择；
- Loader 跳过格式错误文件并记录 error；
- Builder 可以生成合法草稿；
- Builder 只为 candidate 状态写草稿；
- Planner 命中 Skill 时使用 workflow；
- `run_task()` 默认加载 Skill 并保存 `state.matched_skill`；
- `run_task(..., skill_loader=False)` 可以关闭 Skill 匹配。

回归测试：

- 文本总结链路仍完成；
- 表格分析链路仍完成；
- Memory 写入仍完成；
- 全量 pytest 通过。

## 版本完成标准

`v0.8-skill-runtime` 完成时需要满足：

1. `skills/*.md` 可以被加载；
2. 已有总结和表格分析任务能命中对应 Skill；
3. Planner 使用 Skill workflow 生成计划；
4. State 和日志能看到匹配到的 Skill；
5. Builder 能把候选写成草稿，但草稿不会自动生效；
6. README 说明如何新增一个 Skill；
7. 全量测试通过；
8. Git tag `v0.8-skill-runtime` 创建成功。

## 自检

- 占位符检查：本文没有遗留占位内容或未定义的未来步骤。
- 范围检查：只做本地 Markdown Skill、Builder 草稿、Loader 匹配、Planner 注入，不接 TAM、不做语义检索。
- 一致性检查：SkillLoader 返回 dict，符合现有 `AgentState.matched_skill: dict | None`。
- 可测试性检查：每个新增行为都能用本地文件和 pytest 直接验证，不依赖网络或真实 LLM。

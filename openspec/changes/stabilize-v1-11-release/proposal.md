## Why

UTA V1.11 已具备模型规划、动态路由、失败重规划和人工介入的主体实现，但步骤成功标准尚未参与真实校验，人工编辑后的步骤可能沿用旧工具绑定，模型 action 缺少细粒度白名单，等待用户的交互也未证明可跨应用重启恢复。现在需要先补齐这些发布级语义，再进行桌面打包，避免把“测试通过”误当成“行为闭环”。

## What Changes

- 让每个计划步骤的 `success_criteria` 进入 Verifier，并保存逐条校验结果与失败证据。
- 人工编辑步骤后使受影响步骤重新路由，避免复用与新目标不一致的工具、action、参数和依赖元数据。
- 扩展运行时工具目录，声明允许的 actions 与参数约束；Planner/Router 只能选择目录中真实存在的组合。
- 让 `waiting_user` 和计划确认请求能够从 checkpoint 恢复，并处理应用退出、超时、取消和重复回复。
- 增加相应自动化、真实桌面场景、版本一致性、应用打包、签名和 ZIP 完整性发布门禁。

## Capabilities

### New Capabilities

- `step-success-verification`: 按计划步骤的成功标准校验工具结果，记录逐条结论并为 Replan 提供结构化失败依据。
- `validated-tool-routing`: 工具目录公开允许的 action/参数契约，模型选择和人工编辑后的计划必须重新通过契约校验与路由。
- `durable-task-interaction`: 人工补充信息和计划确认可持久化、跨应用重启恢复，并保证同一任务只接受一次有效决策。

### Modified Capabilities

无。当前 OpenSpec 仓库尚无已发布 capability spec，本变更为上述行为建立首批规范。

## Impact

- 核心：`core/state.py`、`core/planner.py`、`core/router.py`、`core/verifier.py`、`core/loop.py`、`core/tool_catalog.py`、`core/interaction.py`。
- 工具契约：`tools/base_tool.py` 及需要声明 action/参数能力的具体工具。
- 桌面端：`desktop/runner.py`、`desktop/api.py`、交互弹窗和任务恢复前端逻辑。
- 持久化：checkpoint 中的步骤校验、工具契约版本和 pending interaction 数据。
- 质量与交付：核心测试、桌面 API/前端测试、21 条以上评测、macOS `.app` 和 ZIP 发布产物。

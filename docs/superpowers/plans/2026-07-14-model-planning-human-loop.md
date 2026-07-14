# UTA V1.11 模型化编排与人工介入实施计划

## 目标

把 UTA 从“模型识别任务 + 固定计划 + 关键词工具路由”升级为可校验的模型编排闭环：

1. 模型生成结构化计划。
2. 模型可根据工具目录选择工具，代码保留安全强制规则。
3. 失败后使用校验结果和执行证据重新规划，不重跑已完成步骤。
4. 信息不足时进入 `waiting_user`，用户回复后从 checkpoint 继续。
5. 复杂或高风险计划在执行前允许用户确认、修改或取消。

## 安全与回退边界

- 模型 JSON 无效、步骤为空或工具不存在时，回退到当前 `Planner` / `Router` 规则。
- Shell、文件写入、文件删除、Python REPL 和目录创建继续由工具层强制人工授权。
- 模型不能把高风险任务降级为普通聊天或不需授权工具。
- 工具参数必须是 JSON 对象；任务原文、当前步骤和前置结果由 Router 统一注入。
- 已完成步骤、工具结果、证据和人工交互全部写入 `AgentState` 与 checkpoint。

## 实施顺序

### Task 1：结构化计划和工具目录

涉及：

- `core/state.py`
- 新增 `core/tool_catalog.py`
- `tools/base_tool.py`
- `tests/test_state.py`
- 新增 `tests/test_tool_catalog.py`

验收：计划步骤可保存工具提示、输入、依赖、成功标准和授权要求，且 checkpoint 往返不丢失。

### Task 2：模型 Planner

涉及：

- `core/planner.py`
- `main.py`
- `core/loop.py`
- `tests/test_planner.py`
- `tests/test_main.py`

验收：有可用 LLM 时生成 1-8 个结构化步骤；模型失败时现有任务全部继续可执行。

### Task 3：动态 Router

涉及：

- `core/router.py`
- `core/tool_catalog.py`
- `tests/test_router.py`

验收：模型可从实际注册工具中选择工具与 action；无效选择回退规则；危险工具保留授权边界。

### Task 4：真实 Replan

涉及：

- `core/planner.py`
- `core/loop.py`
- `core/state.py`
- `tests/test_loop.py`
- `tests/test_checkpoint_store.py`

验收：新计划显式接收失败步骤、校验原因、修复策略、已完成步骤和证据；从失败位置继续。

### Task 5：人工介入和计划确认

涉及：

- 新增 `core/interaction.py`
- `core/state.py`
- `core/loop.py`
- `main.py`
- `desktop/runner.py`
- `desktop/api.py`
- `desktop/frontend/index.html`
- `desktop/frontend/app.js`
- `desktop/frontend/style.css`
- 相关测试

验收：复杂/高风险计划可确认或编辑；信息不足时显示明确问题；用户回复后恢复同一 `task_id`；取消不会记为完成。

### Task 6：评测与交付

涉及：

- `evals/cases/core_scenarios.json`
- `evals/runner.py`
- `README.md`
- `CHANGELOG.md`
- 版本与打包配置

验收：新增计划、工具选择、失败重规划、等待用户和拒绝授权场景；完整测试、真实桌面验收和 macOS 重新打包通过。

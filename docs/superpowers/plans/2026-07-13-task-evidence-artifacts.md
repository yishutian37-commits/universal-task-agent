# UTA 任务证据与产物闭环实施计划

## 目标

让桌面端每次任务都能展示真实的文件读取、文件变更和产物证据，并阻止高风险文件操作在结果无法验证时被标记为完成。

## 架构

- `core/evidence.py` 负责工作区快照、前后差异、工具结果归一和证据去重。
- `AgentState` 持久化 `files`、`changes`、`artifacts`，checkpoint 和任务结果自然携带这些字段。
- `core/loop.py` 在高风险文件工具执行前后采集快照，写入证据并发送 `file_recorded`、`file_changed`、`artifact_created` 事件。
- `Verifier` 对目录创建、文件写入和文件删除结果进行真实文件系统校验。
- 桌面端右侧“文件 / 变更 / 产物”标签消费统一证据，不解析各工具私有返回结构。

## 实施任务

### Task 1：证据数据模型与归一层

涉及文件：

- 新增 `core/evidence.py`
- 修改 `core/state.py`
- 新增 `tests/test_evidence.py`
- 修改 `tests/test_state.py`

验收：证据可去重、可 JSON 序列化、可从 checkpoint 恢复；工作区快照能识别创建、修改和删除。

### Task 2：Agent Loop 事件与持久化

涉及文件：

- 修改 `core/loop.py`
- 修改 `tests/test_loop.py`
- 修改 `tests/test_checkpoint_store.py`

验收：工具完成后按顺序发送证据事件；重试和 resume 不产生重复证据；最终 state 包含完整证据。

### Task 3：高风险操作完成校验

涉及文件：

- 修改 `core/verifier.py`
- 修改 `tests/test_verifier.py`

验收：目录创建后目录必须存在；写入后文件必须存在且字节数匹配；删除后原路径必须消失且回收路径必须存在。

### Task 4：桌面端任务证据标签

涉及文件：

- 修改 `desktop/frontend/index.html`
- 修改 `desktop/frontend/app.js`
- 修改 `desktop/frontend/style.css`
- 修改 `tests/test_desktop_frontend_assets.py`

验收：三个标签显示真实记录；路径可复制；事件漏收时可以从 `get_result().state.evidence` 恢复。

### Task 5：集成验收与交付

验收场景：

1. 读取工作区文件，文件标签出现来源。
2. 创建目录和写入文件，授权后变更标签出现真实路径。
3. 删除文件后显示原路径和 UTA 回收位置。
4. 停止并从 checkpoint 继续，证据不重复。
5. 全量测试、JavaScript 语法、macOS 打包、签名和 ZIP 完整性全部通过。

## 延后事项

- 完整 Git diff 查看器和一键恢复文件。
- Shell 任意命令的进程级文件系统审计。
- 多任务并行证据合并。

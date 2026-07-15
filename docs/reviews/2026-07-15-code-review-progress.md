# 2026-07-15 项目代码审查记录

## 当前状态

- 分支：`feat/uta-cleanup-refactor`
- 审查起点：`ac6b2d7 release: v1.11.0`（tag `v1.11.0`）
- 审查与修复已完成，修改尚未提交。
- 本轮重新构建了 `dist/UTA Desktop.app` 和 `dist/UTA Desktop-macos.zip`，未发布新版本。

## 审查基线

- 修改前全量测试：`812 passed, 5 deselected`。
- 从用户输入经 TaskParser、Planner、Router、Executor、Reflection、Checkpoint/Interaction 追踪到 Desktop Runner/API/Frontend 与打包入口。
- 机械对照了前端 37 个静态 `callApi` 方法与 Python API，没有发现方法名断链；4 个动态 Skill 操作也逐一匹配。
- CLI、FastAPI、PyInstaller Info.plist 和已安装包元数据的版本均为 `1.11.0`。

## 已修复问题

1. Checkpoint 反序列化把明确设为 `0` 的 `max_replans` / `max_retries` 恢复成默认值，导致恢复后重新开启已禁用的重试。
2. TaskParser、FileTool 与 LangChain 工具重复实现“当前用户输入”提取；现已收敛为 `core.intent_rules.current_user_input`，同时保留当前请求的后续补充并隔离旧会话指令。
3. 危险与安全 LangChain 工具的 `tool_input` 可被旧会话污染，用户在步骤交互中补充的路径/内容也可能丢失；现在 Router、Adapter 和各工具均使用当前输入。
4. 回退 Replan 修改失败步骤 goal 后仍携带旧 tool/action/inputs/校验标准/授权标记，会把新计划再次绑定到旧执行路径。
5. 停止任务只唤醒普通交互，不唤醒正在等待的高风险操作授权；已增加 `AuthorizationManager.cancel_all()` 并接入 Runner。
6. 交互决策已写入 checkpoint、pending 尚未清理时崩溃，恢复后会重复提问；现在会直接消费已落盘终态，且不重复写 interaction history。
7. 消息预检和恢复 checkpoint 的 `await` 窗口内可被其他请求抢占，或在切换会话后继续运行旧请求；已增加预检互斥、revision 校验、二次 busy 检查、空 request 保护和附件锁定。
8. 任务 completed/error/cancelled 后可残留已失效的授权或用户交互弹窗；终态与运行界面重置现在会统一关闭。
9. `TaskRunner.wait_for_task(task_id)` 只 join 全局最后一个 thread，有可能等错任务；已改为按 task id 跟踪线程。
10. Runner 在取消旗标已置位时发送 error/progress，会再次抛出取消异常，结果可长期停在 `running`；现在终态写入和事件发送已分离。
11. 缺少 interaction manager、接受空补充、Planner 返回空计划时会继续执行或被判为成功；现在均显式失败。
12. 结构化工具结果不含 `message` 时最终输出为空；现在通过统一 `_result_text` 输出可读 JSON。
13. Reflection 不识别“缺少文件/目录/删除路径、Shell 命令、Python 代码”等可补充错误，会错过用户补充分支。
14. FileWrite 无法解析“文件路径是 ...，内容是 ...”形式的后续补充；已增加解析并做真实写入回归。
15. 任务本身成功后，记忆保存异常会覆盖主任务结果；现在记忆失败会通过 `memory_saved` 事件单独报告。
16. httpx 新版已弃用字符串 `verify=<CA path>`，同步和流式 LLM 请求会持续告警；现在共用 certifi 创建的 `SSLContext`。
17. 构建脚本覆盖旧 ZIP 时会继承旧文件上的 `com.apple.quarantine`。实测中解压后的 adhoc 签名应用被 macOS 以 137 终止；现在压缩前先删除旧归档，避免属性继承。
18. 清理了 Ruff `F` 级别的未使用 import 和无意义 f-string 前缀；没有对历史代码做全库机械格式化。

## 回归与验证

- 最终全量 pytest：`842 passed, 5 deselected`，无 httpx 弃用警告。
- 核心离线评测：`25 / 25`。
- RAG 检索评测：`3 / 3`，Hit@K 和 MRR 均为 `1.0`。
- Python `compileall`、Node 对 `app.js` / `shell.js` / `markdown.js` 的语法检查、`pip check`、Ruff `F`、`git diff --check` 全部通过。
- `bash desktop/build/build_macos.sh` 通过，构建内部再次执行全量测试。PyInstaller 仅报告平台或可选模块（如 `msvcrt` / `user32`），未发现 UTA 源码导入断链。
- 原始 `.app` 与全新目录解压出的 `.app` 均通过 `codesign --verify --deep --strict`。
- ZIP 通过 `unzip -t`，不含 AppleDouble / `__MACOSX`，解压后不含 quarantine，`--version` 输出 `UTA Desktop 1.11.0`。
- 成品 GUI 进程实际启动后稳定存活超过 5 秒，随后主动正常结束。Orca 运行时未启动，因此未做自动化窗口内点击流程。
- 5 个真实 BGE 模型 integration 用例已单独执行：`5 / 5 passed`。模型本地缓存存在，加载时仍需向 `hf-mirror.com` 查询元数据；禁网沙箱中的首轮失败已通过获准网络复测确认为环境限制，不是代码缺陷。

## 工作区边界

- 本次修改主要位于 core/desktop/tools/llm 与对应测试，没有提交、推送或发布。
- 审查开始前已存在的其他未跟踪内容保持原样：`.arch-viz-skill-update/`、`.arch-viz.yml`、architecture visualizer 相关 plans/specs/diff 以及 `docs/uta-agent-architecture-interactive.html`。

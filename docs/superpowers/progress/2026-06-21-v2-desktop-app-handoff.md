# UTA Desktop 当前进度记录

记录时间：2026-06-21 05:56 后

## 当前状态

- 已完成真实 macOS 桌面应用打包，不再是静态 HTML 压缩包。
- 当前开发分支：`codex/v2-desktop-app`。
- 最新产物：
  - `dist/UTA Desktop.app`
  - `dist/UTA Desktop-macos.zip`
- 桌面应用已实际打开验证，pywebview 桥显示“已连接”。
- 左上角多余的前端假红黄绿按钮已删除，只保留 macOS 原生窗口按钮。
- `执行过程` 面板高度已修复，不会再被压成一条；日志面板独立滚动。
- SSL 证书问题已修复：`LLMClient` 在启用 SSL 校验时使用 `certifi` CA 包，`.app` 内已包含 `certifi/cacert.pem`。
- TLS 探测到 `https://token-plan-cn.xiaomimimo.com/v1/chat/completions` 已通过证书校验，返回 `405`，说明证书链可用，只是 GET 方法不被接口接受。

## 已验证

- `.venv/bin/python -m pytest -q`：`138 passed`
- `bash desktop/build/build_macos.sh`：构建成功
- `unzip -t "dist/UTA Desktop-macos.zip"`：无错误
- 打开 `dist/UTA Desktop.app`：窗口正常，界面正常

## 这轮新增/修改的关键文件

- `desktop/`：桌面端后端、前端和打包入口
- `desktop/frontend/index.html`
- `desktop/frontend/style.css`
- `desktop/frontend/app.js`
- `desktop/build/uta_app.spec`
- `desktop/build/build_macos.sh`
- `desktop/api.py`
- `desktop/runner.py`
- `desktop/settings_store.py`
- `llm/llm_client.py`：新增 certifi SSL 上下文
- `main.py`、`core/loop.py`：新增 `on_progress` 事件回调
- `requirements.txt`：新增 `certifi`
- `requirements-desktop.txt`：桌面打包依赖
- `tests/test_desktop_*`、`tests/test_llm_client.py`：新增桌面与 SSL 测试

## 晚上继续建议

1. 先让用户再跑一次总结任务，确认真实模型输出稳定。
2. 如果流程稳定，继续做“运行记录”页：读取 `~/.uta/outputs/states/`，列表展示历史任务，点开复盘执行过程和结果。
3. 后续可以加“复制 state / 打开输出目录 / 导出报告”这类实用按钮。

## 注意事项

- `memory/lessons.json`、`memory/skill_candidates.json`、`memory/task_history.json` 仍有之前烟测留下的脏改，未处理，避免误删用户运行记录。
- 当前 `dist/` 被 `.gitignore` 忽略，但本地最新 `.app` 和 zip 已在 `dist/`。

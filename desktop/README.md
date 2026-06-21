# UTA Desktop

桌面版把现有 Python Agent 打包进本地 macOS 窗口：前端是 `desktop/frontend/`，后端是 `desktop.api.DesktopAPI`，任务仍然走 `main.run_task()`。

## 开发运行

```bash
.venv/bin/python -m pip install -r requirements-desktop.txt
.venv/bin/python desktop/app.py
```

## 构建 macOS 应用

```bash
bash desktop/build/build_macos.sh
```

构建产物：

- `dist/UTA Desktop.app`
- `dist/UTA Desktop-macos.zip`

运行时配置和任务产物写入 `~/.uta/`，不会写入代码仓。

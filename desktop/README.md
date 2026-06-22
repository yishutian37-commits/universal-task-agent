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

## 状态与记忆

桌面端可以查看实时任务状态、运行记录、历史 state/log，以及只读 JSON Memory。

- 短期记忆：当前任务或历史任务的 `state.json` 和 log。
- 长期记忆：`~/.uta/memory/*.json`，包括任务历史、经验、负向规则和 Skill 候选。
- 当前版本只读展示记忆，不支持编辑或删除。

运行时配置和任务产物写入 `~/.uta/`，不会写入代码仓。

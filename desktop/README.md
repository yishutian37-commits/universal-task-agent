# UTA Desktop

桌面版把现有 Python Agent 打包进本地 macOS 窗口：前端是 `desktop/frontend/`，后端是 `desktop.api.DesktopAPI`，任务仍然走 `main.run_task()`。

当前桌面包支持文本总结、表格分析、调研搜索、实时天气、RAG 知识库、只读代码阅读、GEO 分析和历史任务查询。代码阅读任务扫描打包进 `.app` 的 `source/` 源码快照，不会修改项目文件；GEO 分析会读取打包进 `.app` 的 vendor 规则包。

## 对话式前端

桌面端主任务页采用“聊天主界面 + 执行详情侧栏”。发送消息后，任务仍走 `main.run_task()`，右侧同步显示 Planner 步骤、实时日志和 state.json。

左侧“技能包”页会显示：

- 运行时 Skill，例如 `geo_analysis`。
- Vendor 规则包，例如 `geo-agent-marketing-optimized`。
- Skill 加载问题，便于判断包是否真的被桌面端识别。

GEO 示例：

```bash
帮我做 GEO 分析：行业是本地装修，地区是包头，品牌事实：有官网、提供设计和施工服务、需要避免夸大承诺。
```

历史任务查询示例：

```bash
我之前让你进行过什么任务，给我列出来
```

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

# UTA Desktop LLM SSL Debug Handoff

记录时间：2026-06-22 06:01 CST

## 当前上下文

- 当前分支：`codex/v2-desktop-app`
- 最新本地功能提交：`ee6ab41 fix: prevent duplicate task ids`
- 桌面端已重新打包：
  - `dist/UTA Desktop.app`
  - `dist/UTA Desktop-macos.zip`
- 打包验证已通过：
  - `bash desktop/build/build_macos.sh`：退出码 0
  - pytest：`154 passed in 0.45s`
  - `unzip -t "dist/UTA Desktop-macos.zip"`：`No errors detected`
  - `codesign --verify --deep --strict "dist/UTA Desktop.app"`：退出码 0
  - 包内 `frontend/app.js` 与源码 SHA 一致

## 用户遇到的问题

桌面端执行任务时报错：

```text
工具执行失败：tool_error: LLM network error: [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1000)
```

## 当前 LLM 配置状态

`~/.uta/config.json` 的非敏感配置为：

```json
{
  "llm_base_url": "https://token-plan-cn.xiaomimimo.com/v1/chat/completions",
  "llm_model": "mimo-v2.5-pro",
  "llm_ssl_verify": true
}
```

API Key 未打印、未记录。

## 已完成排查

1. 读取了 `llm/llm_client.py`、`config.py`、`desktop/settings_store.py`、`desktop/api.py`、`desktop/runner.py`。
2. 确认桌面端会通过 `SettingsStore.apply_to_environment()` 把 LLM 配置注入环境，再由 `LLMClient.from_config()` 使用。
3. 确认当前 `LLMClient` 使用标准库 `urllib.request.urlopen()`。
4. 使用 curl 探测同一 endpoint：
   - `curl GET https://token-plan-cn.xiaomimimo.com/v1/chat/completions` 返回 HTTP 405，TLS 正常。
   - `curl POST ... Authorization: Bearer dummy` 返回 HTTP 401，TLS 正常。
   - `curl --http1.1 POST ... Authorization: Bearer dummy` 返回 HTTP 401，TLS 正常。
5. 使用项目实际 Python 客户端探测同一 endpoint：
   - `LLMClient(... api_key="dummy").chat(...)` 复现同样的 `UNEXPECTED_EOF_WHILE_READING`。
   - `urllib.request.urlopen()` GET 同一 URL 也复现 EOF。
   - `ssl_verify=True` 和 `ssl_verify=False` 都复现 EOF。
6. 检查当前虚拟环境：
   - `requests`：未安装
   - `httpx`：未安装
   - `urllib3`：未安装
   - `certifi`：已安装
7. 验证了一个 curl 备用传输思路：
   - 通过 `subprocess.run(["curl", "--config", "-"], input=...)` 把 URL、headers、JSON body 从 stdin 传给 curl。
   - dummy key 返回 HTTP 401，说明这种方式可以绕开 `urllib` 的 SSL EOF。
   - 该方式不要把 API Key 放进命令行参数，避免出现在进程列表里。

## 当前判断

根因不是 `.app` 没打包进去，也不是单纯的证书信任问题。

目前证据指向：

```text
token-plan-cn.xiaomimimo.com 的网关可以接受 curl 的 TLS/HTTP 请求，
但会提前断开 Python 标准库 urllib 的 HTTPS 连接。
```

也就是说，问题更像是该网关与 Python `urllib` 的 TLS/客户端行为不兼容，而不是 UTA 业务逻辑错误。

## 晚上继续建议

优先方案：

1. 给 `LLMClient` 增加一个可测试的备用传输层。
2. 当默认 `urllib` 传输遇到 `UNEXPECTED_EOF_WHILE_READING` 时，自动 fallback 到 curl 传输。
3. curl fallback 使用 `curl --config -`，通过 stdin 传递配置，避免 API Key 出现在命令参数中。
4. 为 fallback 写单元测试：
   - urllib EOF 时会调用 curl fallback。
   - curl 返回 401 时转换成 `LLM HTTP error 401: ...`。
   - curl 返回正常 JSON 时解析 `choices[0].message.content`。
   - 没有 curl 或 curl 超时时给出清晰错误。
5. 更新打包后再次运行：
   - `.venv/bin/python -m pytest -q`
   - `bash desktop/build/build_macos.sh`
   - `unzip -t "dist/UTA Desktop-macos.zip"`
   - `codesign --verify --deep --strict "dist/UTA Desktop.app"`

备选方案：

- 安装并切换到 `httpx` 或 `requests`，但会增加依赖和打包体积；需要先验证这些库对该 endpoint 是否真的不 EOF。
- 让用户更换一个 Python 标准库兼容的 LLM Base URL。

## 注意事项

- 不要打印真实 API Key。
- 不要处理当前未纳入提交的 `memory/*.json` 和原型 HTML 文件，除非用户明确要求。
- 当前剩余脏文件仍包括：
  - `memory/lessons.json`
  - `memory/skill_candidates.json`
  - `memory/task_history.json`
  - `.od-skills/`
  - `critique.json`
  - `desktop.html`
  - `desktop.html.artifact.json`
  - `index.html`
  - `index.html.artifact.json`
  - `landing.html`
  - `landing.html.artifact.json`
  - `mqmhzojl-2026-06-20-desktop-app-design.md`
  - `mqmi5wkc-2026-06-20-desktop-app-design.md`
  - `mqmid6ez-2026-06-20-desktop-app-design.md`

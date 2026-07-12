# Task 4 Report: 迁移 LLMClient 到 httpx

## Status

已完成。`llm/llm_client.py` 的默认 transport 已从 urllib 迁移到 `httpx`，并保留 `transport` / `fallback_transport` 注入接口。`use_curl_fallback: bool = False` 已加入 `__init__`，默认不启用 curl fallback。

## Questions and Resolutions

### Q1: 测试里 monkeypatch 了 urllib 内部实现，迁移后如何处理？

`tests/test_llm_client.py` 中有两个旧测试直接 mock `llm.llm_client.request.urlopen` 和 `llm.llm_client.ssl.create_default_context`。迁移到 httpx 后它们不再适用，因此更新为 mock `llm.llm_client.httpx.Client` 并断言传入的 `verify` 参数，以验证 SSL 开关行为。

### Q2: `use_curl_fallback=False` 是否会影响显式注入的 `fallback_transport`？

不会。`use_curl_fallback` 只控制默认是否把 `_curl_transport` 作为 fallback；如果调用方显式传入 `fallback_transport`，则始终保留并使用该注入的 callable。这样原有 fallback 机制相关测试无需改动。

### Q3: 是否需要在模块顶层导入 `httpx` / `certifi`？

brief 中的 `_default_transport` 在方法内 `import httpx`。但这样测试无法通过 `monkeypatch.setattr("llm.llm_client.httpx.Client", ...)` 注入 fake。为保留可测试性，改为在模块顶层 `import certifi` 和 `import httpx`，这是与 brief 唯一的实现细节偏差。

## Test Commands and Output

### LLMClient 专项测试

```bash
.venv/bin/python -m pytest tests/test_llm_client.py -q
```

输出：

```
14 passed in 0.04s
```

### 全量回归测试

```bash
.venv/bin/python -m pytest tests/ -q
```

输出：

```
2 failed, 441 passed, 5 deselected in 1.73s
```

失败用例：
- `tests/test_desktop_api.py::test_desktop_api_general_chat_includes_same_conversation_context`
- `tests/test_desktop_api.py::test_desktop_api_task_includes_same_conversation_context_without_polluting_saved_message`

这两个失败与 Task 4 无关：它们断言桌面端对话上下文注入（"同一对话前文"），且 `tests/test_desktop_api.py` 的改动在任务开始前已存在于工作区，不属于本次提交范围。LLMClient transport 变更未影响 desktop API 的提示词构造逻辑。

## Commit Hash and Message

- Hash: `3c9ef65`
- Message: `refactor: migrate LLMClient default transport to httpx`

## Concerns or Deviations

1. 模块顶层导入 `httpx` / `certifi`（brief 中为方法内 `import httpx`），原因是需要支持测试 monkeypatch。
2. `tests/test_llm_client.py` 中两个 SSL 相关测试从 mock urllib 改为 mock `httpx.Client`，属于迁移后的必要调整。
3. 全量测试存在 2 个与本次任务无关的 pre-existing 失败，已确认不涉及 `llm/llm_client.py`。

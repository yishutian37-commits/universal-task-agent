# Task 4: 迁移 LLMClient 到 httpx

**Files:**
- Modify: `llm/llm_client.py`
- Test: `tests/test_llm_client.py`

**Interfaces:**
- `LLMClient.__init__` 签名不变，新增 `use_curl_fallback: bool = False`
- `LLMClient.chat` / `LLMClient.chat_json` 行为不变
- 默认 transport 改为同步 `httpx.Client`

- [ ] **Step 1: 阅读当前 test_llm_client.py**

Run: `cat tests/test_llm_client.py`
确认注入 `transport` 和 `fallback_transport` callable 的接口仍被测试依赖。

- [ ] **Step 2: 重写 LLMClient 默认 transport**

将 `llm/llm_client.py` 中的 `_default_transport` 替换为 httpx 实现：

```python
def _default_transport(
    self,
    endpoint: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    import httpx

    verify: str | bool = certifi.where() if self.ssl_verify else False
    try:
        with httpx.Client(timeout=timeout, verify=verify) as client:
            response = client.post(endpoint, headers=headers, json=payload)
    except httpx.HTTPStatusError as exc:
        raise LLMClientError(f"LLM HTTP error {exc.response.status_code}: {exc.response.text}") from exc
    except httpx.RequestError as exc:
        raise LLMClientError(f"LLM network error: {exc}") from exc

    try:
        parsed = response.json()
    except ValueError as exc:
        raise LLMClientError(f"Invalid LLM HTTP JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise LLMClientError("Invalid LLM HTTP JSON: expected object")
    return parsed
```

并在 `__init__` 中增加 `use_curl_fallback: bool = False` 参数，默认不启用 curl fallback。

- [ ] **Step 3: 保留 transport 注入能力**

确保测试仍可通过 `transport=` 参数注入 fake transport。

- [ ] **Step 4: 运行 LLMClient 测试**

Run: `pytest tests/test_llm_client.py -q`
Expected: 全部通过。

- [ ] **Step 5: Commit**

```bash
git add llm/llm_client.py
git commit -m "refactor: migrate LLMClient default transport to httpx"
```

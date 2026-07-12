# Task 4 Review: Migrate LLMClient default transport to httpx

## Verdict

- **Spec compliance:** ✅
- **Code quality:** Approved, with fixes requested for Important issues below
- **Tests:** `tests/test_llm_client.py` passes (14/14); full suite passes (`441 passed, 5 deselected`)

## Summary

The implementer migrated `llm/llm_client.py` from `urllib` to `httpx`, added `use_curl_fallback: bool = False` to `LLMClient.__init__`, preserved `transport` / `fallback_transport` injection, and updated the two SSL-related tests in `tests/test_llm_client.py` to mock `httpx.Client` instead of urllib internals. The diff is limited to `llm/llm_client.py` and `tests/test_llm_client.py`; the unrelated `tests/test_desktop_api.py` changes noted in the report are not part of the review package.

## Critical Issues

None.

## Important Issues

### 1. HTTP error handling regression — `httpx.HTTPStatusError` branch is unreachable

In `_default_transport`:

```python
with httpx.Client(timeout=timeout, verify=verify) as client:
    response = client.post(endpoint, headers=headers, json=payload)
except httpx.HTTPStatusError as exc:
    ...
except httpx.RequestError as exc:
    ...
```

`httpx.Client.post()` does **not** raise `HTTPStatusError` for 4xx/5xx responses unless `response.raise_for_status()` is called or an `event_hook` is configured. As written, the `HTTPStatusError` handler is dead code. Non-2xx responses will be parsed as JSON; if they are valid JSON they will be returned and `chat()` will later fail with `Invalid LLM response`, and if they are not valid JSON they will fail with `Invalid LLM HTTP JSON`. This loses the explicit `LLM HTTP error {code}: {detail}` behavior that the urllib implementation provided.

**Fix:** Call `response.raise_for_status()` immediately after `client.post(...)` so the `HTTPStatusError` branch can fire and preserve the intended error message format.

### 2. Default curl fallback disabled changes production runtime behavior

`use_curl_fallback=False` means `LLMClient.from_config()` (used in `core/task_parser.py`, `tools/text_tool.py`, `rag/generation/llm_generator.py`, and `desktop/api.py`) now has **no fallback transport** by default. Previously, `_curl_transport` was always the default fallback. This is intentional per the brief ("默认不启用 curl fallback"), but it is a behavioral change for all production callers that previously relied on implicit curl fallback for SSL EOF errors.

**Recommendation:** Ensure this change is communicated to downstream callers and consider exposing `use_curl_fallback` through `from_config()` if any caller needs to opt back in without abandoning the convenience constructor.

## Minor Issues

1. **Stale test name:** `test_chat_falls_back_to_curl_transport_on_urllib_ssl_eof` still references "urllib", although the test is now transport-agnostic and only uses injected callables. Rename to `test_chat_falls_back_on_ssl_eof` or similar.
2. **`from_config` does not expose `use_curl_fallback`:** Callers using the convenience constructor cannot opt into curl fallback without switching to direct instantiation. Evaluate whether this is intentional.
3. **`certifi` is now a hard import-time dependency:** The previous implementation gracefully fell back to `ssl.create_default_context()` if `certifi` was missing. The new code imports `certifi` at module load time, so a missing dependency will crash import. This is acceptable because `certifi>=2024.0.0` is declared in `pyproject.toml`, but it is a slight robustness reduction.

## Notes

- The implementer deviated from the brief by placing `import httpx` and `import certifi` at module top level instead of inside `_default_transport`. This deviation is justified: it makes the tests' `monkeypatch.setattr("llm.llm_client.httpx.Client", ...)` work correctly, which would not be possible with a method-local import.
- The review diff package (`task-4-review-package.diff`) is truncated at line 277, cutting off the end of `test_chat_falls_back_to_curl_transport_on_urllib_ssl_eof`. The current working tree was inspected directly to complete the review.

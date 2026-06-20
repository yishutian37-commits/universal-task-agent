# UTA V0.2 LLM Parser 设计

## 1. 背景

本文档按照 `universal_task_agent_prd_v6_1_final_start.md` 编写。

`v0.1-skeleton` 已经完成：CLI 可以接收任务，创建 `AgentState`，执行硬编码 `mock_tool`，保存 state/log，并打了 `v0.1-skeleton` tag。

`v0.2-llm-parser` 的目标是把“任务理解”接入主流程：新增统一 LLM 调用封装和 Task Parser，让 Agent 能把自然语言任务识别为 `summarize`、`data_analysis` 或 `unknown`。

## 2. 本阶段范围

V0.2 支持下面这条流程：

```text
CLI 输入任务
-> 创建 AgentState
-> TaskParser 调用 LLMClient
-> LLM 返回结构化 JSON
-> Python 校验 task_type 枚举
-> 把 task_type / intent 写入 state
-> 继续执行 V0.1 的 mock loop
-> 保存 state 和 log
```

完成标志：

1. `TaskParser` 可以把“帮我总结……”识别为 `summarize`；
2. `TaskParser` 可以把“分析 CSV / 表格……”识别为 `data_analysis`；
3. LLM 返回异常、JSON 解析失败、网络失败时，程序兜底为 `unknown`，不崩溃；
4. `main.py` 不再写死 `task_type="summarize"`，而是使用 Task Parser 的结果；
5. 仍然可以运行现有 demo，并保存 state/log；
6. 通过测试后打 tag：`v0.2-llm-parser`。

## 3. 配置设计

真实配置写在 `.env`，不提交到 Git。

本机这次使用的配置形态是：

```env
LLM_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1/chat/completions
LLM_MODEL=mimo-v2.5-pro
LLM_API_KEY=<只写在本地 .env，不提交>
```

`LLMClient` 必须支持两种地址：

1. 完整 chat completions 地址：

```text
https://token-plan-cn.xiaomimimo.com/v1/chat/completions
```

2. 普通 base url：

```text
http://127.0.0.1:15721/v1
```

如果传入普通 base url，代码内部补成 `/chat/completions`。如果传入的地址已经以 `/chat/completions` 结尾，就直接使用。

## 4. 模块设计

### 4.1 `llm/llm_client.py`

`LLMClient` 是唯一允许直接调用 LLM HTTP API 的模块。其他模块不能裸调接口。

它提供两个方法：

```python
chat(system_prompt: str, user_prompt: str) -> str
chat_json(system_prompt: str, user_prompt: str, schema: dict | None = None) -> dict
```

`chat()` 负责：

1. 组装 OpenAI-compatible chat completions 请求；
2. 设置 `Authorization: Bearer <api_key>`；
3. 发送 `model`、`messages`、`temperature`；
4. 读取 `choices[0].message.content`；
5. 网络失败或响应格式异常时抛出清楚的 `LLMClientError`。

`chat_json()` 负责：

1. 调用 `chat()`；
2. 从返回文本中解析 JSON；
3. 支持模型返回纯 JSON，也支持模型把 JSON 包在 ```json 代码块里；
4. 解析失败时抛出 `LLMClientError`。

### 4.2 `core/task_parser.py`

`TaskParser` 负责把用户输入解析成 `Task`。

它接收一个可替换的 `llm_client`，方便测试时传入 fake client，不依赖真实网络。

输出字段：

```python
Task(
    task_id=...,
    user_input=...,
    task_type="summarize" | "data_analysis" | "unknown",
    intent=...,
    input_type=...,
    expected_output=...,
    constraints=[...],
    missing_info=[...],
)
```

Python 层必须做枚举校验：

```text
允许：summarize / data_analysis / unknown
其他：统一改成 unknown
```

如果 LLM 调用失败、返回非 JSON、字段缺失或字段类型异常，Task Parser 返回一个兜底 Task：

```python
task_type="unknown"
intent="parse_failed"
input_type="unknown"
expected_output="unknown"
missing_info=["task_type"]
```

## 5. 主流程改造

`main.py` 从 v0.1 的固定写死：

```python
task_type="summarize"
intent="v0.1 hard-coded summarize skeleton"
```

升级为：

```text
create_initial_state()
-> TaskParser.parse()
-> state.task_type = task.task_type
-> state.intent = task.intent
```

V0.2 仍然继续使用 V0.1 的 `run_minimal_loop()` 和 `mock_tool`。这意味着：即使 task_type 被识别为 `data_analysis`，本阶段也不会真的分析表格，只证明“任务理解模块已经接入主流程”。

## 6. 错误处理

V0.2 必须做到“LLM 有问题，CLI 不崩”。

错误场景和处理：

| 场景 | 处理 |
|---|---|
| 没有 `LLM_API_KEY` | `LLMClient` 抛出 `LLMClientError`，TaskParser 兜底为 `unknown` |
| 网络失败 | TaskParser 兜底为 `unknown` |
| 模型返回非 JSON | TaskParser 兜底为 `unknown` |
| 模型返回未知 task_type | Python 改成 `unknown` |
| 模型漏字段 | Python 用默认值补齐 |

log 里需要记录：

```text
[TaskParser] task_type = summarize
```

或：

```text
[TaskParser] task_type = unknown
```

## 7. 测试设计

测试不依赖真实 LLM 网络。单元测试使用 fake client。

新增测试：

1. `tests/test_llm_client.py`
   - 验证完整 `/chat/completions` 地址不会重复拼接；
   - 验证普通 `/v1` base url 会补成 `/chat/completions`；
   - 验证 `chat_json()` 可以解析纯 JSON；
   - 验证 `chat_json()` 可以解析 ```json 代码块；
   - 验证坏 JSON 会抛出 `LLMClientError`。

2. `tests/test_task_parser.py`
   - fake client 返回 `summarize` 时，输出 `Task.task_type == "summarize"`；
   - fake client 返回 `data_analysis` 时，输出 `Task.task_type == "data_analysis"`；
   - fake client 返回未知类型时，输出 `Task.task_type == "unknown"`；
   - fake client 抛异常时，输出兜底 Task；
   - 字段缺失时能补默认值。

3. `tests/test_main.py`
   - `run_task()` 可以注入 fake parser；
   - state 文件中保存 parser 得到的 `task_type` 和 `intent`；
   - log 中包含 `[TaskParser] task_type = ...`。

## 8. 安全边界

API key 不写入：

1. spec；
2. implementation plan；
3. README；
4. 测试；
5. Git commit。

如果需要本地真实调用，只写入 `.env`。`.env` 已在 `.gitignore` 中。

## 9. 明确不做

V0.2 不做下面内容：

1. 不做 Planner；
2. 不做 Router；
3. 不做真实总结；
4. 不做真实表格分析；
5. 不做 Reflection；
6. 不做 Memory；
7. 不做 Skill；
8. 不接入 TAM；
9. 不把 API key 提交到 Git。

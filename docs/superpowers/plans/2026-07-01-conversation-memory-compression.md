# 会话记忆压缩实现计划

> 给后续执行者：实现时必须按任务逐步勾选。建议使用 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans`，每个任务先写测试，再写实现，再验证，再提交。

**目标：** 给 UTA 桌面端加入“会话压缩 + 短期记忆 + 长期记忆”能力，让历史对话不会无限膨胀，同时能保留真正重要的信息。

**总体架构：**  
在现有 `ConversationStore` 和 `MemoryStore` 中间新增一层“记忆压缩器”。每个会话单独保存短期摘要和最近原文消息；稳定、长期有用的信息再写入长期记忆。压缩触发不写死为某个数字，而是按模型上下文窗口和安全比例计算。

**技术栈：** Python 标准库、现有桌面端 API、现有 LLM Client、pytest、桌面端 HTML/CSS/JS。

---

## 一、对你的建议的评估

你的四点建议整体是对的，我建议做这些微调：

1. **压缩内容要分类型，不要一股脑塞进记忆。**  
   需要区分：用户画像、偏好、工作习惯、项目事实、明确约束、决策记录、待确认问题。  
   例如“用户要求中文回复”是长期偏好；“这次想修输入框”更像项目事实或短期任务上下文。

2. **压缩频率不能只固定为 200-300k。**  
   这个范围适合大上下文模型，但如果后续模型只有 32k、64k，就会爆上下文。  
   建议策略：  
   `触发阈值 = min(250000, 模型上下文窗口 * 0.70)`  
   也就是说，大模型最多到 25 万 token 左右触发，小模型按 70% 提前触发。

3. **长期记忆必须增量更新，不是每次覆盖。**  
   后续压缩得到的新信息，要填补旧记忆的空缺。  
   如果发现旧记忆不准确，要记录来源、更新时间、置信度，而不是静默覆盖。

4. **短期记忆必须按会话隔离。**  
   A 对话框的短期记忆不能自动污染 B 对话框。  
   长期记忆可以跨会话共享，但短期记忆只服务当前会话。

---

## 二、目标数据结构

### 1. 单个会话文件

位置：`~/.uta/conversations/conv_*.json`

新增字段：

```json
{
  "conversation_id": "conv_20260701_120000_000000",
  "title": "新对话",
  "created_at": "2026-07-01T12:00:00.000000",
  "updated_at": "2026-07-01T12:05:00.000000",
  "messages": [],
  "short_term": {
    "summary": "",
    "compressed_until_index": 0,
    "recent_message_limit": 12,
    "token_estimate": 0,
    "updated_at": ""
  },
  "compression": {
    "last_compressed_at": "",
    "last_trigger_tokens": 0,
    "runs": []
  }
}
```

解释：

- `short_term.summary`：当前会话的短期摘要。
- `compressed_until_index`：已经压缩到第几条消息。
- `recent_message_limit`：保留最近几轮原文，默认 12 条。
- `compression.runs`：每次压缩记录，方便排查。

### 2. 长期记忆文件

位置：`~/.uta/memory/long_term_memory.json`

结构：

```json
{
  "version": 1,
  "profile": {
    "identity": [],
    "preferences": [],
    "work_habits": [],
    "projects": [],
    "constraints": [],
    "open_questions": []
  },
  "facts": []
}
```

单条长期记忆：

```json
{
  "memory_id": "mem_20260701_120000_000000",
  "kind": "preference",
  "content": "用户明确要求使用中文回复。",
  "source_conversation_id": "conv_20260701_120000_000000",
  "source_message_ids": ["msg_1"],
  "confidence": 0.95,
  "first_seen_at": "2026-07-01T12:00:00.000000",
  "last_seen_at": "2026-07-01T12:00:00.000000"
}
```

---

## 三、要新增和修改的文件

### 新增文件

- `desktop/memory_compression.py`  
  负责：token 估算、压缩触发策略、压缩结果解析、长期记忆合并。

- `tests/test_memory_compression.py`  
  负责：测试压缩策略、解析结果、长期记忆合并。

### 修改文件

- `desktop/conversation_store.py`  
  给会话文件增加短期记忆字段、压缩记录字段、消息 ID。

- `desktop/memory_store.py`  
  读取长期记忆，并在记忆页面返回长期压缩结果。

- `desktop/api.py`  
  增加手动压缩接口，后续加入自动压缩触发。

- `desktop/frontend/index.html`  
  记忆页面新增“短期会话记忆”和“长期压缩记忆”区域。

- `desktop/frontend/app.js`  
  渲染短期/长期记忆，增加手动压缩按钮。

- `desktop/frontend/style.css`  
  给新的记忆卡片加样式。

- `tests/test_desktop_conversation_store.py`  
  测试会话新字段和旧文件兼容。

- `tests/test_desktop_memory_store.py`  
  测试长期记忆读取。

- `tests/test_desktop_api.py`  
  测试手动压缩和自动压缩。

- `tests/test_desktop_frontend_assets.py`  
  测试桌面端是否有对应按钮和展示区域。

---

## 四、执行任务

### 任务 1：实现压缩触发策略

**目标：** 不写死 200-300k，而是根据模型上下文计算。

**文件：**

- 新增：`desktop/memory_compression.py`
- 新增：`tests/test_memory_compression.py`

#### 步骤 1：写失败测试

在 `tests/test_memory_compression.py` 写：

```python
from desktop.memory_compression import CompressionPolicy, estimate_tokens


def test_estimate_tokens_uses_conservative_character_ratio():
    assert estimate_tokens("abcd" * 100) == 100


def test_large_context_policy_caps_at_250k():
    policy = CompressionPolicy(context_window_tokens=400_000)
    assert policy.trigger_tokens == 250_000
    assert policy.should_compress(249_999) is False
    assert policy.should_compress(250_000) is True


def test_small_context_policy_triggers_before_model_limit():
    policy = CompressionPolicy(context_window_tokens=32_000)
    assert policy.trigger_tokens == 22_400
    assert policy.should_compress(22_399) is False
    assert policy.should_compress(22_400) is True
```

#### 步骤 2：确认测试失败

运行：

```bash
.venv/bin/python -m pytest tests/test_memory_compression.py -q
```

预期：失败，因为 `desktop.memory_compression` 还不存在。

#### 步骤 3：实现最小代码

在 `desktop/memory_compression.py` 写：

```python
from __future__ import annotations

from dataclasses import dataclass


def estimate_tokens(text: str) -> int:
    return max(1, (len(str(text or "")) + 3) // 4)


@dataclass(frozen=True)
class CompressionPolicy:
    context_window_tokens: int = 400_000
    trigger_ratio: float = 0.70
    trigger_cap_tokens: int = 250_000
    target_recent_messages: int = 12

    @property
    def trigger_tokens(self) -> int:
        return int(min(self.trigger_cap_tokens, self.context_window_tokens * self.trigger_ratio))

    def should_compress(self, token_estimate: int) -> bool:
        return int(token_estimate) >= self.trigger_tokens
```

#### 步骤 4：验证通过

运行：

```bash
.venv/bin/python -m pytest tests/test_memory_compression.py -q
```

预期：通过。

#### 步骤 5：提交

```bash
git add desktop/memory_compression.py tests/test_memory_compression.py
git commit -m "feat: add conversation compression policy"
```

---

### 任务 2：给会话文件增加短期记忆结构

**目标：** 每个会话都有独立短期记忆。

**文件：**

- 修改：`desktop/conversation_store.py`
- 修改：`tests/test_desktop_conversation_store.py`

#### 步骤 1：写失败测试

新增测试：

```python
def test_conversation_store_initializes_short_term_and_compression(tmp_path):
    store = ConversationStore(tmp_path)
    conversation = store.new_conversation()["conversation"]

    assert conversation["short_term"] == {
        "summary": "",
        "compressed_until_index": 0,
        "recent_message_limit": 12,
        "token_estimate": 0,
        "updated_at": "",
    }
    assert conversation["compression"] == {
        "last_compressed_at": "",
        "last_trigger_tokens": 0,
        "runs": [],
    }


def test_conversation_store_appends_stable_message_ids(tmp_path):
    store = ConversationStore(tmp_path)
    conversation_id = store.new_conversation()["conversation"]["conversation_id"]

    store.append_message(conversation_id, role="user", content="你好")
    loaded = store.get_conversation(conversation_id)["conversation"]

    assert loaded["messages"][0]["message_id"].startswith("msg_")
```

#### 步骤 2：确认测试失败

运行：

```bash
.venv/bin/python -m pytest tests/test_desktop_conversation_store.py -q
```

预期：失败，因为字段还没有。

#### 步骤 3：实现会话结构

在 `desktop/conversation_store.py` 增加：

```python
def _default_short_term() -> dict[str, Any]:
    return {
        "summary": "",
        "compressed_until_index": 0,
        "recent_message_limit": 12,
        "token_estimate": 0,
        "updated_at": "",
    }


def _default_compression() -> dict[str, Any]:
    return {
        "last_compressed_at": "",
        "last_trigger_tokens": 0,
        "runs": [],
    }


def _message_id() -> str:
    return "msg_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
```

在 `new_conversation()` 里增加：

```python
"short_term": _default_short_term(),
"compression": _default_compression(),
```

在 `append_message()` 里增加：

```python
"message_id": _message_id(),
```

在 `get_conversation()` 里兼容旧文件：

```python
data.setdefault("short_term", _default_short_term())
data.setdefault("compression", _default_compression())
```

#### 步骤 4：验证通过

运行：

```bash
.venv/bin/python -m pytest tests/test_desktop_conversation_store.py -q
```

#### 步骤 5：提交

```bash
git add desktop/conversation_store.py tests/test_desktop_conversation_store.py
git commit -m "feat: add short-term conversation memory schema"
```

---

### 任务 3：定义压缩结果格式

**目标：** LLM 压缩后必须输出固定 JSON，不允许随意生成散文。

**文件：**

- 修改：`desktop/memory_compression.py`
- 修改：`tests/test_memory_compression.py`

#### 压缩结果格式

```json
{
  "short_term_summary": "当前会话摘要",
  "long_term_candidates": [
    {
      "kind": "preference",
      "content": "用户要求使用中文回复。",
      "confidence": 0.95,
      "source_message_ids": ["msg_1"]
    }
  ],
  "open_questions": ["需要确认是否默认开启自动压缩"]
}
```

#### 支持的长期记忆类型

- `identity`：用户身份或画像
- `preference`：偏好
- `work_habit`：工作习惯
- `project`：项目事实
- `constraint`：明确约束
- `decision`：已做决定
- `open_question`：待确认问题

#### 验收命令

```bash
.venv/bin/python -m pytest tests/test_memory_compression.py -q
```

---

### 任务 4：实现长期记忆合并

**目标：** 新压缩内容写入长期记忆，但不能重复堆积。

**文件：**

- 修改：`desktop/memory_compression.py`
- 修改：`desktop/memory_store.py`
- 修改：`tests/test_memory_compression.py`
- 修改：`tests/test_desktop_memory_store.py`

#### 合并规则

1. 用 `kind + content` 判断是否重复。
2. 如果重复，只更新 `last_seen_at`、`confidence`、来源。
3. 如果不重复，新增一条长期记忆。
4. 不直接删除旧记忆，除非后续单独做“记忆修订”功能。

#### 验收命令

```bash
.venv/bin/python -m pytest tests/test_memory_compression.py tests/test_desktop_memory_store.py -q
```

---

### 任务 5：增加手动压缩 API

**目标：** 先做一个稳定可控的手动压缩入口，避免一上来自动压缩不好排查。

**文件：**

- 修改：`desktop/api.py`
- 修改：`tests/test_desktop_api.py`

#### 新接口

```python
def compress_conversation(self, conversation_id: str) -> dict[str, Any]:
    ...
```

#### 行为

1. 读取对应会话。
2. 找出尚未压缩的消息。
3. 调 LLM 生成压缩 JSON。
4. 更新该会话的 `short_term.summary`。
5. 把长期候选信息合并到 `long_term_memory.json`。
6. 返回压缩状态。

#### 验收命令

```bash
.venv/bin/python -m pytest tests/test_desktop_api.py -q
```

---

### 任务 6：增加自动压缩触发

**目标：** 当会话过长时自动压缩。

**文件：**

- 修改：`desktop/api.py`
- 修改：`desktop/settings_store.py`
- 修改：`tests/test_desktop_api.py`
- 修改：`tests/test_desktop_settings_store.py`

#### 新设置

```json
{
  "memory_compression_enabled": true,
  "memory_context_window_tokens": 400000,
  "memory_compression_trigger_ratio": 0.7,
  "memory_compression_cap_tokens": 250000
}
```

#### 触发规则

```text
如果 当前会话 token 估算 >= min(250000, 模型上下文窗口 * 0.70)
则触发压缩
```

#### 重要约束

自动压缩失败时，不应该影响用户当前消息发送。  
也就是说：压缩失败要记录错误，但不能让正常聊天失败。

#### 验收命令

```bash
.venv/bin/python -m pytest tests/test_desktop_api.py tests/test_desktop_settings_store.py -q
```

---

### 任务 7：桌面端记忆页面展示

**目标：** 让你能直观看到短期和长期记忆。

**文件：**

- 修改：`desktop/frontend/index.html`
- 修改：`desktop/frontend/app.js`
- 修改：`desktop/frontend/style.css`
- 修改：`tests/test_desktop_frontend_assets.py`

#### 页面新增区域

在“记忆”页面新增：

```html
<div class="memorySection">
  <h4>短期会话记忆</h4>
  <div class="memoryBlock" id="memoryConversationShortTerm"></div>
</div>

<div class="memorySection">
  <h4>长期压缩记忆</h4>
  <div class="memoryBlock" id="memoryLongTermFacts"></div>
</div>
```

#### 需要显示的信息

短期会话记忆：

- 会话标题
- 会话 ID
- 短期摘要
- 压缩到第几条消息
- 最近更新时间

长期压缩记忆：

- 类型
- 内容
- 置信度
- 来源会话
- 首次出现时间
- 最近出现时间

#### 验收命令

```bash
.venv/bin/python -m pytest tests/test_desktop_frontend_assets.py -q
```

---

### 任务 8：完整验证和打包

**目标：** 所有功能通过测试，并重新打包进桌面端。

#### 步骤 1：完整测试

```bash
.venv/bin/python -m pytest
```

预期：全部通过。

#### 步骤 2：前端 JS 语法检查

```bash
node --check desktop/frontend/app.js
```

预期：无输出，退出码为 0。

#### 步骤 3：打包桌面端

```bash
bash desktop/build/build_macos.sh
```

预期生成：

- `dist/UTA Desktop.app`
- `dist/UTA Desktop-macos.zip`

#### 步骤 4：签名和哈希校验

```bash
codesign --verify --deep --strict --verbose=1 "dist/UTA Desktop.app"
shasum -a 256 "dist/UTA Desktop-macos.zip"
```

预期：

- `codesign` 通过
- 输出 zip 的 SHA256

---

## 五、最终验收标准

完成后必须满足：

1. 会话历史仍然能正常查看。
2. 每个会话都有独立短期摘要。
3. 长期记忆能持续合并用户画像、偏好、工作习惯和项目事实。
4. 压缩不会把不同会话的短期内容混在一起。
5. 压缩触发按模型上下文窗口计算，不写死单一阈值。
6. 记忆页面能看到短期会话记忆和长期压缩记忆。
7. 压缩失败不会导致正常聊天失败。
8. 完整测试通过并打包进桌面应用。

---

## 六、建议执行顺序

建议按这个顺序做：

1. 先做任务 1-2：把压缩策略和会话结构打稳。
2. 再做任务 3-4：实现压缩结果格式和长期记忆合并。
3. 再做任务 5：手动压缩 API。
4. 确认手动压缩稳定后，再做任务 6：自动压缩。
5. 最后做任务 7-8：桌面端展示和打包。

这样风险最低，因为自动压缩最容易隐藏问题，应该放在手动压缩稳定之后。

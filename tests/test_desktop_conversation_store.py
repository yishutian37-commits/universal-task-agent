import re

from desktop.conversation_store import ConversationStore


def test_conversation_store_creates_and_reads_conversation(tmp_path):
    store = ConversationStore(tmp_path)

    created = store.new_conversation(title="第一次对话")
    conversation_id = created["conversation"]["conversation_id"]
    loaded = store.get_conversation(conversation_id)

    assert created["ok"] is True
    assert re.match(r"conv_\d{8}_\d{6}_\d{6}", conversation_id)
    assert loaded["ok"] is True
    assert loaded["conversation"]["title"] == "第一次对话"
    assert loaded["conversation"]["messages"] == []


def test_conversation_store_appends_user_and_assistant_messages(tmp_path):
    store = ConversationStore(tmp_path)
    conversation_id = store.new_conversation()["conversation"]["conversation_id"]

    user = store.append_message(
        conversation_id,
        role="user",
        content="帮我总结这篇文章",
        task_id="task_1",
        status="completed",
    )
    assistant = store.append_message(
        conversation_id,
        role="assistant",
        content="正在处理...",
        task_id="task_1",
        status="running",
    )
    loaded = store.get_conversation(conversation_id)

    assert user["ok"] is True
    assert assistant["ok"] is True
    assert [message["role"] for message in loaded["conversation"]["messages"]] == ["user", "assistant"]
    assert loaded["conversation"]["messages"][0]["content"] == "帮我总结这篇文章"
    assert loaded["conversation"]["messages"][1]["status"] == "running"


def test_conversation_store_updates_assistant_message_by_task_id(tmp_path):
    store = ConversationStore(tmp_path)
    conversation_id = store.new_conversation()["conversation"]["conversation_id"]
    store.append_message(conversation_id, role="user", content="任务", task_id="task_1")
    store.append_message(conversation_id, role="assistant", content="正在处理...", task_id="task_1", status="running")

    updated = store.update_assistant_message(
        conversation_id,
        task_id="task_1",
        content="## 摘要\n完成",
        status="completed",
    )
    loaded = store.get_conversation(conversation_id)

    assert updated["ok"] is True
    assistant = loaded["conversation"]["messages"][1]
    assert assistant["content"] == "## 摘要\n完成"
    assert assistant["status"] == "completed"


def test_conversation_store_lists_newest_first_and_skips_bad_json(tmp_path):
    store = ConversationStore(tmp_path)
    first = store.new_conversation(title="旧会话")["conversation"]["conversation_id"]
    second = store.new_conversation(title="新会话")["conversation"]["conversation_id"]
    (tmp_path / "conv_bad.json").write_text("{bad json", encoding="utf-8")

    listed = store.list_conversations()

    assert listed["ok"] is True
    ids = [item["conversation_id"] for item in listed["conversations"]]
    assert ids[0] == second
    assert first in ids
    assert "conv_bad" not in ids


def test_conversation_store_rejects_unsafe_ids(tmp_path):
    store = ConversationStore(tmp_path)

    result = store.get_conversation("../secret")

    assert result == {"ok": False, "error": "会话不存在"}

import json
import re

from desktop.conversation_store import ConversationStore


def test_conversation_store_init_has_no_filesystem_side_effect(tmp_path):
    root = tmp_path / "missing" / "conversations"

    store = ConversationStore(root)
    listed = store.list_conversations()

    assert root.exists() is False
    assert listed == {"ok": True, "conversations": []}


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


def test_conversation_store_appends_stable_message_ids(tmp_path):
    store = ConversationStore(tmp_path)
    conversation_id = store.new_conversation()["conversation"]["conversation_id"]

    appended = store.append_message(conversation_id, role="user", content="你好")
    loaded = store.get_conversation(conversation_id)["conversation"]

    assert appended["message"]["message_id"].startswith("msg_")
    assert loaded["messages"][0]["message_id"] == appended["message"]["message_id"]


def test_conversation_store_adds_memory_defaults_when_reading_old_file(tmp_path):
    store = ConversationStore(tmp_path)
    conversation_id = "conv_20260701_120000_000000"
    (tmp_path / f"{conversation_id}.json").write_text(
        json.dumps(
            {
                "conversation_id": conversation_id,
                "title": "旧会话",
                "created_at": "2026-07-01T12:00:00.000000",
                "updated_at": "2026-07-01T12:00:00.000000",
                "messages": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    loaded = store.get_conversation(conversation_id)

    assert loaded["ok"] is True
    assert loaded["conversation"]["short_term"]["recent_message_limit"] == 12
    assert loaded["conversation"]["compression"]["runs"] == []


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


def test_conversation_store_lists_at_most_100_recent_conversations(tmp_path):
    store = ConversationStore(tmp_path)
    for index in range(105):
        store.new_conversation(title=f"会话 {index}")

    listed = store.list_conversations()

    assert listed["ok"] is True
    assert len(listed["conversations"]) == 100
    assert listed["conversations"][0]["title"] == "会话 104"
    assert listed["conversations"][-1]["title"] == "会话 5"


def test_conversation_store_rejects_unsafe_ids(tmp_path):
    store = ConversationStore(tmp_path)

    result = store.get_conversation("../secret")

    assert result == {"ok": False, "error": "会话不存在"}


def test_conversation_store_deletes_conversation_and_compression_archive(tmp_path):
    store = ConversationStore(tmp_path)
    conversation_id = store.new_conversation(title="待删除")['conversation']["conversation_id"]
    archive_path = tmp_path / "archives" / f"{conversation_id}.json"
    archive_path.parent.mkdir(parents=True)
    archive_path.write_text('{"version": 1, "chunks": []}', encoding="utf-8")

    result = store.delete_conversation(conversation_id)

    assert result == {"ok": True, "conversation_id": conversation_id}
    assert not (tmp_path / f"{conversation_id}.json").exists()
    assert not archive_path.exists()
    assert store.get_conversation(conversation_id) == {"ok": False, "error": "会话不存在"}


def test_conversation_store_delete_rejects_missing_or_unsafe_conversation(tmp_path):
    store = ConversationStore(tmp_path)

    assert store.delete_conversation("../secret") == {"ok": False, "error": "会话不存在"}
    assert store.delete_conversation("conv_20260701_120000_000000") == {
        "ok": False,
        "error": "会话不存在",
    }

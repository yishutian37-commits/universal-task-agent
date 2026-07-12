import json

from desktop.memory_store import MemoryStore


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_memory_store_returns_empty_defaults_when_files_are_missing(tmp_path):
    result = MemoryStore(tmp_path).overview()

    assert result["ok"] is True
    assert result["task_history"] == []
    assert result["lessons"] == []
    assert result["negative_rules"] == []
    assert result["skill_candidates"] == []
    assert result["user_profile"] == {}
    assert result["long_term_memory"]["facts"] == []
    assert result["long_term_facts"] == []
    assert result["counts"] == {
        "tasks": 0,
        "lessons": 0,
        "negative_rules": 0,
        "skill_candidates": 0,
        "long_term_facts": 0,
    }


def test_memory_store_reads_all_memory_files(tmp_path):
    write_json(tmp_path / "task_history.json", {"version": 1, "tasks": [{"task_id": "task_1"}]})
    write_json(tmp_path / "lessons.json", {"version": 1, "lessons": [{"lesson_id": "lesson_1"}]})
    write_json(tmp_path / "negative_rules.json", {"version": 1, "negative_rules": [{"rule_id": "rule_1"}]})
    write_json(tmp_path / "skill_candidates.json", {"version": 1, "candidates": [{"task_type": "summarize"}]})
    write_json(tmp_path / "user_profile.json", {"version": 1, "profile": {"name": "UTA"}})
    write_json(
        tmp_path / "long_term_memory.json",
        {
            "version": 1,
            "profile": {"preferences": ["用户明确要求使用中文回复。"]},
            "facts": [{"memory_id": "mem_1", "kind": "preference"}],
        },
    )

    result = MemoryStore(tmp_path).overview()

    assert result["ok"] is True
    assert result["task_history"] == [{"task_id": "task_1"}]
    assert result["lessons"] == [{"lesson_id": "lesson_1"}]
    assert result["negative_rules"] == [{"rule_id": "rule_1"}]
    assert result["skill_candidates"] == [{"task_type": "summarize"}]
    assert result["user_profile"] == {"name": "UTA"}
    assert result["long_term_facts"] == [{"memory_id": "mem_1", "kind": "preference"}]
    assert result["counts"]["tasks"] == 1
    assert result["counts"]["long_term_facts"] == 1


def test_memory_store_reports_invalid_json(tmp_path):
    (tmp_path / "task_history.json").write_text("{bad json", encoding="utf-8")

    result = MemoryStore(tmp_path).overview()

    assert result["ok"] is False
    assert "task_history.json" in result["error"]


def test_memory_store_merges_long_term_candidates(tmp_path):
    store = MemoryStore(tmp_path)

    result = store.merge_long_term_candidates(
        [
            {
                "kind": "preference",
                "content": "用户明确要求使用中文回复。",
                "confidence": 0.95,
                "source_message_ids": ["msg_1"],
            }
        ],
        conversation_id="conv_20260701_120000_000000",
        now="2026-07-01T12:00:00.000000",
    )
    persisted = json.loads((tmp_path / "long_term_memory.json").read_text(encoding="utf-8"))

    assert result["ok"] is True
    assert result["long_term_memory"]["profile"]["preferences"] == ["用户明确要求使用中文回复。"]
    assert persisted["facts"][0]["content"] == "用户明确要求使用中文回复。"


def test_memory_store_searches_long_term_facts_and_hides_disabled_by_default(tmp_path):
    write_json(
        tmp_path / "long_term_memory.json",
        {
            "version": 1,
            "facts": [
                {"memory_id": "mem_1", "kind": "preference", "content": "用户喜欢中文回复"},
                {"memory_id": "mem_2", "kind": "project", "content": "UTA 使用桌面端", "enabled": False},
            ],
        },
    )
    store = MemoryStore(tmp_path)

    assert [item["memory_id"] for item in store.search_long_term_facts("中文")["facts"]] == ["mem_1"]
    assert store.search_long_term_facts("UTA")["facts"] == []
    assert [
        item["memory_id"] for item in store.search_long_term_facts("UTA", include_disabled=True)["facts"]
    ] == ["mem_2"]


def test_memory_store_updates_content_kind_and_enabled_state(tmp_path):
    write_json(
        tmp_path / "long_term_memory.json",
        {"version": 1, "facts": [{"memory_id": "mem_1", "kind": "preference", "content": "旧内容"}]},
    )
    store = MemoryStore(tmp_path)

    result = store.update_long_term_fact(
        "mem_1",
        {"content": "新内容", "kind": "work_habit", "enabled": False},
        now="2026-07-13T14:00:00+00:00",
    )
    persisted = json.loads((tmp_path / "long_term_memory.json").read_text(encoding="utf-8"))

    assert result["ok"] is True
    assert result["fact"]["content"] == "新内容"
    assert result["fact"]["kind"] == "work_habit"
    assert result["fact"]["enabled"] is False
    assert result["fact"]["updated_at"] == "2026-07-13T14:00:00+00:00"
    assert persisted["facts"][0] == result["fact"]


def test_memory_store_rejects_empty_updates_and_deletes_by_memory_id(tmp_path):
    write_json(
        tmp_path / "long_term_memory.json",
        {"version": 1, "facts": [{"memory_id": "mem_1", "kind": "project", "content": "UTA"}]},
    )
    store = MemoryStore(tmp_path)

    rejected = store.update_long_term_fact("mem_1", {"content": "  "})
    deleted = store.delete_long_term_fact("mem_1")

    assert rejected["ok"] is False
    assert deleted["ok"] is True
    assert deleted["fact"]["memory_id"] == "mem_1"
    assert store.load_long_term_memory()["facts"] == []

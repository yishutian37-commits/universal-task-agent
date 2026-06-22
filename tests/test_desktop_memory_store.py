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
    assert result["counts"] == {
        "tasks": 0,
        "lessons": 0,
        "negative_rules": 0,
        "skill_candidates": 0,
    }


def test_memory_store_reads_all_memory_files(tmp_path):
    write_json(tmp_path / "task_history.json", {"version": 1, "tasks": [{"task_id": "task_1"}]})
    write_json(tmp_path / "lessons.json", {"version": 1, "lessons": [{"lesson_id": "lesson_1"}]})
    write_json(tmp_path / "negative_rules.json", {"version": 1, "negative_rules": [{"rule_id": "rule_1"}]})
    write_json(tmp_path / "skill_candidates.json", {"version": 1, "candidates": [{"task_type": "summarize"}]})
    write_json(tmp_path / "user_profile.json", {"version": 1, "profile": {"name": "UTA"}})

    result = MemoryStore(tmp_path).overview()

    assert result["ok"] is True
    assert result["task_history"] == [{"task_id": "task_1"}]
    assert result["lessons"] == [{"lesson_id": "lesson_1"}]
    assert result["negative_rules"] == [{"rule_id": "rule_1"}]
    assert result["skill_candidates"] == [{"task_type": "summarize"}]
    assert result["user_profile"] == {"name": "UTA"}
    assert result["counts"]["tasks"] == 1


def test_memory_store_reports_invalid_json(tmp_path):
    (tmp_path / "task_history.json").write_text("{bad json", encoding="utf-8")

    result = MemoryStore(tmp_path).overview()

    assert result["ok"] is False
    assert "task_history.json" in result["error"]

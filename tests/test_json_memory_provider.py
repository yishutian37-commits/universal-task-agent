import json

from memory_providers.json_memory_provider import JsonMemoryProvider


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_json_memory_provider_creates_default_store_files(tmp_path):
    memory_root = tmp_path / "memory"

    provider = JsonMemoryProvider(memory_root)
    context = provider.load_context()

    assert sorted(context.keys()) == [
        "lessons",
        "negative_rules",
        "skill_candidates",
        "task_history",
        "user_profile",
    ]
    assert read_json(memory_root / "user_profile.json") == {
        "version": 1,
        "profile": {},
        "updated_at": None,
    }
    assert read_json(memory_root / "task_history.json") == {"version": 1, "tasks": []}
    assert read_json(memory_root / "lessons.json") == {"version": 1, "lessons": []}
    assert read_json(memory_root / "negative_rules.json") == {
        "version": 1,
        "negative_rules": [],
    }
    assert read_json(memory_root / "skill_candidates.json") == {
        "version": 1,
        "candidates": [],
    }

import json

from desktop.skill_store import SkillStore


def test_skill_store_generates_activates_toggles_and_rolls_back_user_skill(tmp_path):
    builtin_root = tmp_path / "builtin-skills"
    user_root = tmp_path / "user-skills"
    memory_root = tmp_path / "memory"
    builtin_root.mkdir()
    memory_root.mkdir()
    (memory_root / "skill_candidates.json").write_text(
        json.dumps(
            {
                "version": 1,
                "candidates": [
                    {
                        "task_type": "custom_review",
                        "success_count": 3,
                        "latest_task_id": "task_latest",
                        "status": "candidate",
                        "reason": "custom_review 已成功执行 3 次",
                        "updated_at": "2026-07-13 12:00:00",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    store = SkillStore(builtin_root, user_skills_root=user_root, memory_root=memory_root)

    draft = store.generate_draft("custom_review")
    activated = store.activate_draft("custom_review")
    disabled = store.set_enabled("custom_review_skill", False)
    rolled_back = store.rollback("custom_review_skill")

    assert draft["ok"] is True
    assert draft["draft"]["content"].startswith("---\n")
    assert activated["ok"] is True
    assert (user_root / "custom_review.md").exists()
    assert disabled["skill"]["enabled"] is False
    assert disabled["skill"]["version"] == 2
    assert rolled_back["skill"]["enabled"] is True
    assert rolled_back["skill"]["version"] == 1


def test_skill_store_overview_includes_candidates_and_drafts(tmp_path):
    builtin_root = tmp_path / "builtin-skills"
    user_root = tmp_path / "user-skills"
    memory_root = tmp_path / "memory"
    builtin_root.mkdir()
    (user_root / "drafts").mkdir(parents=True)
    memory_root.mkdir()
    (user_root / "drafts" / "custom.md").write_text("draft content", encoding="utf-8")
    (memory_root / "skill_candidates.json").write_text(
        json.dumps({"version": 1, "candidates": [{"task_type": "custom", "status": "candidate"}]}),
        encoding="utf-8",
    )

    overview = SkillStore(
        builtin_root,
        user_skills_root=user_root,
        memory_root=memory_root,
    ).overview()

    assert overview["candidates"][0]["task_type"] == "custom"
    assert overview["drafts"][0]["task_type"] == "custom"
    assert overview["drafts"][0]["content"] == "draft content"

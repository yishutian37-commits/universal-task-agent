import pytest

from core.skill_builder import SkillBuilder


def candidate(status="candidate"):
    return {
        "task_type": "data_analysis",
        "success_count": 3,
        "latest_task_id": "task_1",
        "status": status,
        "reason": "data_analysis 已成功执行 3 次，可在 v0.8 评估是否沉淀为 Skill。",
        "updated_at": "2026-06-21 00:00:00",
    }


def test_skill_builder_generates_markdown_draft():
    draft = SkillBuilder().build_draft(
        candidate(),
        ["读取表格文件", "分析字段、行数、列数和缺失值", "生成表格分析报告"],
    )

    assert draft.startswith("---\n")
    assert "id: data_analysis_skill\n" in draft
    assert "enabled: false\n" in draft
    assert "task_type: data_analysis\n" in draft
    assert "workflow:\n  - 读取表格文件\n" in draft
    assert "# data_analysis Skill 草稿" in draft
    assert "来源：data_analysis 已成功执行 3 次" in draft
    assert "人工审核通过后，可将本草稿移动到 skills/ 根目录，并将 enabled 改为 true。" in draft


def test_skill_builder_writes_candidate_draft(tmp_path):
    builder = SkillBuilder(tmp_path / "skills" / "drafts")

    path = builder.write_draft(candidate(), ["读取表格文件", "生成表格分析报告"])

    assert path == tmp_path / "skills" / "drafts" / "data_analysis.md"
    assert path.exists()
    assert "id: data_analysis_skill" in path.read_text(encoding="utf-8")


def test_skill_builder_rejects_tracking_candidate():
    builder = SkillBuilder()

    with pytest.raises(ValueError, match="candidate status"):
        builder.build_draft(candidate(status="tracking"), ["读取表格文件"])


def test_skill_builder_rejects_empty_workflow():
    builder = SkillBuilder()

    with pytest.raises(ValueError, match="workflow"):
        builder.build_draft(candidate(), [])

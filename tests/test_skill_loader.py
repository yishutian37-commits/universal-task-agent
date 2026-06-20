from pathlib import Path

from core.skill_loader import SkillLoader
from core.state import Task


def write_skill(path: Path, body: str) -> Path:
    path.write_text(body.strip() + "\n", encoding="utf-8")
    return path


def make_task(task_type="summarize", user_input="帮我总结一段文本", intent="summarize_article"):
    return Task(
        task_id="task_test",
        user_input=user_input,
        task_type=task_type,
        intent=intent,
        input_type="text",
        expected_output="report",
    )


def test_skill_loader_reads_markdown_front_matter(tmp_path):
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    write_skill(
        skills_root / "summarize_article.md",
        """
        ---
        id: summarize_article
        name: 文本总结 Skill
        version: 1
        enabled: true
        task_type: summarize
        priority: 100
        trigger_keywords:
          - 总结
          - 摘要
        workflow:
          - 读取输入内容
          - 提取核心信息
          - 生成结构化报告
        ---

        # 文本总结 Skill
        """,
    )

    skills = SkillLoader(skills_root).load_skills()

    assert len(skills) == 1
    assert skills[0]["id"] == "summarize_article"
    assert skills[0]["name"] == "文本总结 Skill"
    assert skills[0]["version"] == 1
    assert skills[0]["enabled"] is True
    assert skills[0]["task_type"] == "summarize"
    assert skills[0]["priority"] == 100
    assert skills[0]["trigger_keywords"] == ["总结", "摘要"]
    assert skills[0]["workflow"] == ["读取输入内容", "提取核心信息", "生成结构化报告"]
    assert skills[0]["source_path"].endswith("summarize_article.md")


def test_skill_loader_matches_by_task_type_and_keyword(tmp_path):
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    write_skill(
        skills_root / "summarize_article.md",
        """
        ---
        id: summarize_article
        name: 文本总结 Skill
        task_type: summarize
        trigger_keywords:
          - 总结
        workflow:
          - 读取输入内容
          - 提取核心信息
          - 生成结构化报告
        ---
        """,
    )

    matched = SkillLoader(skills_root).match(make_task())

    assert matched["id"] == "summarize_article"


def test_skill_loader_ignores_disabled_skill(tmp_path):
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    write_skill(
        skills_root / "disabled.md",
        """
        ---
        id: disabled_summary
        name: Disabled Summary
        enabled: false
        task_type: summarize
        trigger_keywords:
          - 总结
        workflow:
          - 读取输入内容
        ---
        """,
    )

    matched = SkillLoader(skills_root).match(make_task())

    assert matched is None


def test_skill_loader_uses_priority_then_id_for_stable_match(tmp_path):
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    write_skill(
        skills_root / "b_skill.md",
        """
        ---
        id: b_skill
        name: B Skill
        task_type: summarize
        priority: 10
        trigger_keywords:
          - 总结
        workflow:
          - B workflow
        ---
        """,
    )
    write_skill(
        skills_root / "a_skill.md",
        """
        ---
        id: a_skill
        name: A Skill
        task_type: summarize
        priority: 10
        trigger_keywords:
          - 总结
        workflow:
          - A workflow
        ---
        """,
    )
    write_skill(
        skills_root / "high_skill.md",
        """
        ---
        id: high_skill
        name: High Skill
        task_type: summarize
        priority: 99
        trigger_keywords:
          - 总结
        workflow:
          - High workflow
        ---
        """,
    )

    matched = SkillLoader(skills_root).match(make_task())

    assert matched["id"] == "high_skill"
    assert matched["workflow"] == ["High workflow"]


def test_skill_loader_skips_invalid_files_and_records_errors(tmp_path):
    skills_root = tmp_path / "skills"
    drafts_root = skills_root / "drafts"
    skills_root.mkdir()
    drafts_root.mkdir()
    write_skill(skills_root / "broken.md", "# Missing front matter")
    write_skill(
        drafts_root / "draft.md",
        """
        ---
        id: draft_skill
        name: Draft Skill
        task_type: summarize
        workflow:
          - Draft workflow
        ---
        """,
    )

    loader = SkillLoader(skills_root)
    skills = loader.load_skills()

    assert skills == []
    assert len(loader.errors) == 1
    assert loader.errors[0]["path"].endswith("broken.md")
    assert "missing front matter" in loader.errors[0]["error"]

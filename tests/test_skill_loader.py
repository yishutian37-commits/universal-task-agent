from pathlib import Path
from textwrap import dedent

import pytest

from core.skill_loader import SkillLoader
from core.state import Task


def write_skill(path: Path, body: str) -> Path:
    path.write_text(dedent(body).strip() + "\n", encoding="utf-8")
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


def test_skill_loader_adds_default_fields_when_omitted(tmp_path):
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    write_skill(
        skills_root / "minimal.md",
        """
        ---
        id: minimal_summary
        name: Minimal Summary
        task_type: summarize
        workflow:
          - Read
        ---
        """,
    )

    skills = SkillLoader(skills_root).load_skills()

    assert skills[0]["version"] == 1
    assert skills[0]["enabled"] is True
    assert skills[0]["priority"] == 0
    assert skills[0]["trigger_keywords"] == []


def test_skill_loader_uses_default_skills_root(tmp_path, monkeypatch):
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    write_skill(
        skills_root / "default.md",
        """
        ---
        id: default_summary
        name: Default Summary
        task_type: summarize
        workflow:
          - Read
        ---
        """,
    )
    monkeypatch.chdir(tmp_path)

    skills = SkillLoader().load_skills()

    assert len(skills) == 1
    assert skills[0]["id"] == "default_summary"
    assert skills[0]["source_path"].endswith("skills/default.md")


def test_project_geo_analysis_skill_is_available():
    matched = SkillLoader("skills").match(
        make_task(
            task_type="geo_analysis",
            user_input="帮我做 GEO 分析，生成问题矩阵和平台合规检查",
            intent="geo_analysis",
        )
    )

    assert matched is not None
    assert matched["id"] == "geo_analysis"
    assert matched["task_type"] == "geo_analysis"
    assert matched["workflow"] == [
        "读取 GEO 规则包并生成问题矩阵",
        "生成 GEO 分析报告",
    ]


def test_skill_loader_matches_by_task_type_when_keywords_omitted(tmp_path):
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    write_skill(
        skills_root / "type_only.md",
        """
        ---
        id: type_only_summary
        name: Type Only Summary
        task_type: summarize
        workflow:
          - Read
        ---
        """,
    )

    matched = SkillLoader(skills_root).match(make_task(user_input="plain text without keyword"))

    assert matched["id"] == "type_only_summary"


def test_skill_loader_matches_by_task_type_when_keywords_empty(tmp_path):
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    write_skill(
        skills_root / "empty_keywords.md",
        """
        ---
        id: empty_keywords_summary
        name: Empty Keywords Summary
        task_type: summarize
        trigger_keywords:
        workflow:
          - Read
        ---
        """,
    )

    matched = SkillLoader(skills_root).match(make_task(user_input="plain text without keyword"))

    assert matched["id"] == "empty_keywords_summary"


def test_skill_loader_matches_user_input_keyword_case_insensitively(tmp_path):
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    write_skill(
        skills_root / "english_summary.md",
        """
        ---
        id: english_summary
        name: English Summary
        task_type: summarize
        trigger_keywords:
          - REPORT
        workflow:
          - Read
        ---
        """,
    )

    matched = SkillLoader(skills_root).match(
        make_task(user_input="please write a report", intent="other_intent")
    )

    assert matched["id"] == "english_summary"


def test_skill_loader_matches_intent_keyword_case_insensitively(tmp_path):
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    write_skill(
        skills_root / "intent_summary.md",
        """
        ---
        id: intent_summary
        name: Intent Summary
        task_type: summarize
        trigger_keywords:
          - ARTICLE_SUMMARY
        workflow:
          - Read
        ---
        """,
    )

    matched = SkillLoader(skills_root).match(
        make_task(user_input="plain text", intent="article_summary")
    )

    assert matched["id"] == "intent_summary"


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


def test_skill_loader_uses_id_for_stable_match_when_priority_ties(tmp_path):
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

    matched = SkillLoader(skills_root).match(make_task())

    assert matched["id"] == "a_skill"
    assert matched["workflow"] == ["A workflow"]


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


def test_skill_loader_rejects_unsupported_list_indentation(tmp_path):
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    write_skill(
        skills_root / "bad_indent.md",
        """
        ---
        id: bad_indent
        name: Bad Indent
        task_type: summarize
        trigger_keywords:
            - 总结
        workflow:
          - Read
        ---
        """,
    )

    loader = SkillLoader(skills_root)
    skills = loader.load_skills()

    assert skills == []
    assert len(loader.errors) == 1
    assert loader.errors[0]["path"].endswith("bad_indent.md")
    assert "unsupported indentation" in loader.errors[0]["error"]


@pytest.mark.parametrize(
    ("field_name", "body"),
    [
        (
            "id",
            """
            ---
            id:
            name: Missing ID
            task_type: summarize
            workflow:
              - Read
            ---
            """,
        ),
        (
            "name",
            """
            ---
            id: missing_name
            name:
            task_type: summarize
            workflow:
              - Read
            ---
            """,
        ),
        (
            "task_type",
            """
            ---
            id: missing_task_type
            name: Missing Task Type
            task_type:
            workflow:
              - Read
            ---
            """,
        ),
        (
            "trigger_keywords",
            """
            ---
            id: scalar_keywords
            name: Scalar Keywords
            task_type: summarize
            trigger_keywords: summarize
            workflow:
              - Read
            ---
            """,
        ),
        (
            "workflow",
            """
            ---
            id: scalar_workflow
            name: Scalar Workflow
            task_type: summarize
            workflow: summarize
            ---
            """,
        ),
        (
            "workflow",
            """
            ---
            id: empty_workflow
            name: Empty Workflow
            task_type: summarize
            workflow:
            ---
            """,
        ),
        (
            "enabled",
            """
            ---
            id: empty_enabled
            name: Empty Enabled
            enabled:
            task_type: summarize
            workflow:
              - Read
            ---
            """,
        ),
        (
            "enabled",
            """
            ---
            id: scalar_enabled
            name: Scalar Enabled
            enabled: yes
            task_type: summarize
            workflow:
              - Read
            ---
            """,
        ),
        (
            "version",
            """
            ---
            id: bad_version
            name: Bad Version
            version: one
            task_type: summarize
            workflow:
              - Read
            ---
            """,
        ),
        (
            "priority",
            """
            ---
            id: bad_priority
            name: Bad Priority
            priority: high
            task_type: summarize
            workflow:
              - Read
            ---
            """,
        ),
    ],
)
def test_skill_loader_rejects_invalid_field_shapes(tmp_path, field_name, body):
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    write_skill(skills_root / f"bad_{field_name}.md", body)

    loader = SkillLoader(skills_root)
    skills = loader.load_skills()

    assert skills == []
    assert len(loader.errors) == 1
    assert field_name in loader.errors[0]["error"]


def test_repo_includes_official_runtime_skills():
    skills = SkillLoader("skills").load_skills()
    by_id = {skill["id"]: skill for skill in skills}

    assert by_id["summarize_article"]["workflow"] == ["读取输入内容", "提取核心信息", "生成结构化报告"]
    assert by_id["analyze_table"]["workflow"] == ["读取表格文件", "分析字段、行数、列数和缺失值", "生成表格分析报告"]

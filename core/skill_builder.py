from __future__ import annotations

from pathlib import Path
from typing import Any


TRIGGER_KEYWORDS = {
    "summarize": ["总结", "摘要"],
    "data_analysis": ["分析", "表格", "csv", "excel"],
}


class SkillBuilder:
    def __init__(self, drafts_root: Path | str = "skills/drafts"):
        self.drafts_root = Path(drafts_root)

    def build_draft(self, candidate: dict[str, Any], workflow: list[str]) -> str:
        task_type = self._validate_candidate(candidate)
        self._validate_workflow(workflow)

        lines = [
            "---",
            f"id: {task_type}_skill",
            f"name: {task_type} Skill",
            "version: 1",
            "enabled: false",
            f"task_type: {task_type}",
            "priority: 10",
            "trigger_keywords:",
        ]
        lines.extend(f"  - {keyword}" for keyword in self._keywords_for(task_type))
        lines.append("workflow:")
        lines.extend(f"  - {step}" for step in workflow)
        lines.extend(
            [
                "---",
                "",
                f"# {task_type} Skill 草稿",
                "",
                f"来源：{candidate['reason']}",
                f"最近任务：{candidate['latest_task_id']}",
                f"更新时间：{candidate['updated_at']}",
                "人工审核通过后，可将本草稿移动到 skills/ 根目录，并将 enabled 改为 true。",
                "",
            ]
        )

        return "\n".join(lines)

    def write_draft(self, candidate: dict[str, Any], workflow: list[str]) -> Path:
        task_type = self._validate_candidate(candidate)
        draft = self.build_draft(candidate, workflow)

        self.drafts_root.mkdir(parents=True, exist_ok=True)
        path = self.drafts_root / f"{task_type}.md"
        path.write_text(draft, encoding="utf-8")
        return path

    @staticmethod
    def _validate_candidate(candidate: dict[str, Any]) -> str:
        if candidate.get("status") != "candidate":
            raise ValueError("candidate status must be candidate")

        task_type = candidate.get("task_type")
        if not isinstance(task_type, str) or not task_type.strip():
            raise ValueError("task_type must be a non-empty string")
        return task_type

    @staticmethod
    def _validate_workflow(workflow: list[str]) -> None:
        if not workflow:
            raise ValueError("workflow must be non-empty")

    @staticmethod
    def _keywords_for(task_type: str) -> list[str]:
        return TRIGGER_KEYWORDS.get(task_type, [task_type])

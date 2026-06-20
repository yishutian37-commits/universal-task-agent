from __future__ import annotations

from pathlib import Path
from typing import Any

from core.state import Task


REQUIRED_FIELDS = ("id", "name", "task_type", "workflow")
DEFAULT_FIELDS = {
    "version": 1,
    "enabled": True,
    "priority": 0,
    "trigger_keywords": [],
}


class SkillLoader:
    def __init__(self, skills_root: Path | str):
        self.skills_root = Path(skills_root)
        self.errors: list[dict[str, str]] = []

    def load_skills(self) -> list[dict[str, Any]]:
        self.errors = []
        skills: list[dict[str, Any]] = []

        if not self.skills_root.exists():
            return skills

        for skill_path in sorted(self.skills_root.glob("*.md")):
            try:
                skill = self._read_skill(skill_path)
            except ValueError as exc:
                self.errors.append({"path": str(skill_path), "error": str(exc)})
                continue
            skills.append(skill)

        return skills

    def match(self, task: Task) -> dict[str, Any] | None:
        matches = [
            skill
            for skill in self.load_skills()
            if self._is_enabled(skill)
            and skill.get("task_type") == task.task_type
            and self._matches_keyword(skill, task)
        ]
        if not matches:
            return None

        return sorted(matches, key=lambda skill: (-self._priority(skill), str(skill["id"])))[0]

    def _read_skill(self, skill_path: Path) -> dict[str, Any]:
        text = skill_path.read_text(encoding="utf-8")
        front_matter = self._extract_front_matter(text)
        skill = self._parse_front_matter(front_matter)
        self._apply_defaults(skill)
        self._validate_skill(skill)
        skill["source_path"] = str(skill_path)
        return skill

    @staticmethod
    def _extract_front_matter(text: str) -> list[str]:
        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            raise ValueError("missing front matter")

        for index, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                return lines[1:index]

        raise ValueError("missing closing front matter delimiter")

    @staticmethod
    def _parse_front_matter(lines: list[str]) -> dict[str, Any]:
        data: dict[str, Any] = {}
        current_list_key: str | None = None

        for raw_line in lines:
            if not raw_line.strip():
                continue

            if raw_line.startswith("  - "):
                if current_list_key is None:
                    raise ValueError("list item without key")
                data[current_list_key].append(SkillLoader._parse_scalar(raw_line[4:].strip()))
                continue

            if raw_line.lstrip().startswith("- ") or raw_line[0].isspace():
                raise ValueError("unsupported indentation")

            line = raw_line.strip()
            if ":" not in line:
                raise ValueError(f"invalid front matter line: {line}")

            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if not key:
                raise ValueError("empty front matter key")

            if value:
                data[key] = SkillLoader._parse_scalar(value)
                current_list_key = None
            else:
                data[key] = []
                current_list_key = key

        return data

    @staticmethod
    def _apply_defaults(skill: dict[str, Any]) -> None:
        for key, value in DEFAULT_FIELDS.items():
            if key not in skill:
                skill[key] = value.copy() if isinstance(value, list) else value

    @staticmethod
    def _parse_scalar(value: str) -> str | int | bool:
        normalized = value.lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
        if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
            return int(value)
        return value

    @staticmethod
    def _validate_skill(skill: dict[str, Any]) -> None:
        missing = [field for field in REQUIRED_FIELDS if field not in skill]
        if missing:
            raise ValueError(f"missing required fields: {', '.join(missing)}")

        if not isinstance(skill["workflow"], list) or not skill["workflow"]:
            raise ValueError("workflow must be a non-empty list")

    @staticmethod
    def _is_enabled(skill: dict[str, Any]) -> bool:
        return skill.get("enabled", True) is not False

    @staticmethod
    def _matches_keyword(skill: dict[str, Any], task: Task) -> bool:
        keywords = skill.get("trigger_keywords", [])
        if not isinstance(keywords, list):
            return False
        if not keywords:
            return True

        searchable_text = f"{task.user_input}\n{task.intent}".casefold()
        return any(
            bool(keyword_text) and keyword_text in searchable_text
            for keyword_text in (str(keyword).casefold() for keyword in keywords)
        )

    @staticmethod
    def _priority(skill: dict[str, Any]) -> int:
        priority = skill.get("priority", 0)
        return priority if isinstance(priority, int) else 0

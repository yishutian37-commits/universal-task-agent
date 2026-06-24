from __future__ import annotations

from pathlib import Path
from typing import Any

from core.skill_loader import SkillLoader


class SkillStore:
    def __init__(self, skills_root: Path | str):
        self.skills_root = Path(skills_root)

    def overview(self) -> dict[str, Any]:
        loader = SkillLoader(self.skills_root)
        runtime_skills = [
            self._runtime_skill_summary(skill)
            for skill in loader.load_skills()
        ]
        vendor_packs = self._vendor_pack_summaries()
        return {
            "ok": True,
            "runtime_skills": runtime_skills,
            "vendor_packs": vendor_packs,
            "errors": loader.errors,
            "counts": {
                "runtime_skills": len(runtime_skills),
                "vendor_packs": len(vendor_packs),
            },
        }

    def _runtime_skill_summary(self, skill: dict[str, Any]) -> dict[str, Any]:
        workflow = skill.get("workflow") if isinstance(skill.get("workflow"), list) else []
        trigger_keywords = (
            skill.get("trigger_keywords")
            if isinstance(skill.get("trigger_keywords"), list)
            else []
        )
        return {
            "id": skill.get("id"),
            "name": skill.get("name"),
            "task_type": skill.get("task_type"),
            "enabled": skill.get("enabled", True),
            "priority": skill.get("priority", 0),
            "version": skill.get("version", 1),
            "source_path": skill.get("source_path"),
            "trigger_keywords": trigger_keywords,
            "workflow": workflow,
        }

    def _vendor_pack_summaries(self) -> list[dict[str, Any]]:
        vendor_root = self.skills_root / "vendor"
        if not vendor_root.exists():
            return []

        packs = []
        for pack_path in sorted(path for path in vendor_root.iterdir() if path.is_dir()):
            readme_path = pack_path / "README.md"
            skill_files = sorted(pack_path.glob("skills/*/SKILL.md"))
            packs.append(
                {
                    "name": pack_path.name,
                    "path": str(pack_path),
                    "has_readme": readme_path.exists(),
                    "skill_count": len(skill_files),
                    "skills": [
                        str(skill_file.parent.name)
                        for skill_file in skill_files
                    ],
                }
            )
        return packs

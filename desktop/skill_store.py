from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from core.skill_builder import SkillBuilder
from core.skill_loader import SkillLoader
from desktop.paths import uta_home


DEFAULT_WORKFLOWS = {
    "summarize": ["读取输入内容", "提取核心信息", "生成结构化报告"],
    "data_analysis": ["读取表格文件", "分析字段与数据质量", "生成分析报告"],
    "research": ["检索可信来源", "核对关键事实", "生成带来源报告"],
    "code_reading": ["扫描项目结构", "追踪关键调用链", "生成代码阅读报告"],
}


class SkillStore:
    def __init__(
        self,
        skills_root: Path | str,
        *,
        user_skills_root: Path | str | None = None,
        memory_root: Path | str | None = None,
    ):
        self.skills_root = Path(skills_root)
        self.user_skills_root = Path(user_skills_root) if user_skills_root else uta_home() / "skills"
        self.memory_root = Path(memory_root) if memory_root else uta_home() / "memory"
        self.drafts_root = self.user_skills_root / "drafts"
        self.versions_root = self.user_skills_root / ".versions"

    def overview(self) -> dict[str, Any]:
        loader = SkillLoader(self.skills_root, additional_roots=[self.user_skills_root])
        runtime_skills = [self._runtime_skill_summary(skill) for skill in loader.load_skills()]
        vendor_packs = self._vendor_pack_summaries()
        candidates = self._candidate_payload().get("candidates", [])
        drafts = self._draft_summaries()
        return {
            "ok": True,
            "runtime_skills": runtime_skills,
            "vendor_packs": vendor_packs,
            "candidates": candidates if isinstance(candidates, list) else [],
            "drafts": drafts,
            "errors": loader.errors,
            "counts": {
                "runtime_skills": len(runtime_skills),
                "vendor_packs": len(vendor_packs),
                "candidates": len(candidates) if isinstance(candidates, list) else 0,
                "drafts": len(drafts),
            },
        }

    def generate_draft(self, task_type: str) -> dict[str, Any]:
        normalized = self._safe_name(task_type, "task_type")
        payload = self._candidate_payload()
        candidates = payload.get("candidates") if isinstance(payload.get("candidates"), list) else []
        candidate = next((item for item in candidates if item.get("task_type") == normalized), None)
        if not isinstance(candidate, dict):
            return {"ok": False, "error": "Skill 候选不存在"}
        if candidate.get("status") != "candidate":
            return {"ok": False, "error": "候选尚未达到可生成 Skill 的条件"}
        workflow = self._workflow_for_candidate(candidate)
        path = SkillBuilder(self.drafts_root).write_draft(candidate, workflow)
        return {"ok": True, "draft": self._draft_summary(path)}

    def activate_draft(self, task_type: str) -> dict[str, Any]:
        normalized = self._safe_name(task_type, "task_type")
        draft_path = self.drafts_root / f"{normalized}.md"
        if not draft_path.is_file() or draft_path.is_symlink():
            return {"ok": False, "error": "Skill 草稿不存在"}
        content = draft_path.read_text(encoding="utf-8")
        content = self._set_frontmatter_value(content, "enabled", "true")
        target = self.user_skills_root / f"{normalized}.md"
        if target.exists():
            current = SkillLoader(self.user_skills_root)._read_skill(target)
            self._backup(target, str(current["id"]))
            content = self._set_frontmatter_value(content, "version", str(int(current["version"]) + 1))
        self._write_and_validate(target, content)
        self._update_candidate_status(normalized, "active")
        return {"ok": True, "skill": self._runtime_skill_summary(SkillLoader(self.user_skills_root)._read_skill(target))}

    def set_enabled(self, skill_id: str, enabled: bool) -> dict[str, Any]:
        normalized_id = self._safe_name(skill_id, "skill_id")
        skill = self._find_skill(normalized_id)
        if skill is None:
            return {"ok": False, "error": "Skill 不存在"}
        source = Path(str(skill["source_path"]))
        target = self.user_skills_root / f"{self._safe_name(str(skill['task_type']), 'task_type')}.md"
        if target.exists():
            self._backup(target, normalized_id)
        else:
            self._backup(source, normalized_id)
        content = source.read_text(encoding="utf-8")
        content = self._set_frontmatter_value(content, "enabled", "true" if enabled else "false")
        content = self._set_frontmatter_value(content, "version", str(int(skill.get("version") or 1) + 1))
        self._write_and_validate(target, content)
        updated = SkillLoader(self.user_skills_root)._read_skill(target)
        return {"ok": True, "skill": self._runtime_skill_summary(updated)}

    def rollback(self, skill_id: str) -> dict[str, Any]:
        normalized_id = self._safe_name(skill_id, "skill_id")
        skill = self._find_skill(normalized_id)
        if skill is None:
            return {"ok": False, "error": "Skill 不存在"}
        target = self.user_skills_root / f"{self._safe_name(str(skill['task_type']), 'task_type')}.md"
        versions = sorted((self.versions_root / normalized_id).glob("*.md"), reverse=True)
        if not versions:
            return {"ok": False, "error": "没有可回滚的 Skill 版本"}
        self._write_and_validate(target, versions[0].read_text(encoding="utf-8"))
        versions[0].unlink()
        restored = SkillLoader(self.user_skills_root)._read_skill(target)
        return {"ok": True, "skill": self._runtime_skill_summary(restored)}

    def _runtime_skill_summary(self, skill: dict[str, Any]) -> dict[str, Any]:
        workflow = skill.get("workflow") if isinstance(skill.get("workflow"), list) else []
        trigger_keywords = skill.get("trigger_keywords") if isinstance(skill.get("trigger_keywords"), list) else []
        source = Path(str(skill.get("source_path") or ""))
        skill_id = str(skill.get("id") or "")
        return {
            "id": skill_id,
            "name": skill.get("name"),
            "task_type": skill.get("task_type"),
            "enabled": skill.get("enabled", True),
            "priority": skill.get("priority", 0),
            "version": skill.get("version", 1),
            "source_path": str(source),
            "origin": "user" if self._is_within(source, self.user_skills_root) else "builtin",
            "can_rollback": any((self.versions_root / skill_id).glob("*.md")),
            "trigger_keywords": trigger_keywords,
            "workflow": workflow,
        }

    def _find_skill(self, skill_id: str) -> dict[str, Any] | None:
        return next(
            (
                skill
                for skill in SkillLoader(self.skills_root, additional_roots=[self.user_skills_root]).load_skills()
                if str(skill.get("id") or "") == skill_id
            ),
            None,
        )

    def _workflow_for_candidate(self, candidate: dict[str, Any]) -> list[str]:
        task_id = str(candidate.get("latest_task_id") or "")
        checkpoint_path = self.memory_root / "checkpoints" / f"{task_id}.json"
        if checkpoint_path.is_file() and not checkpoint_path.is_symlink():
            try:
                payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
                steps = payload.get("plan", {}).get("steps", [])
                goals = [str(step.get("goal") or "").strip() for step in steps if isinstance(step, dict)]
                if any(goals):
                    return [goal for goal in goals if goal]
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                pass
        task_type = str(candidate.get("task_type") or "")
        return list(DEFAULT_WORKFLOWS.get(task_type, ["理解任务目标", "执行并校验结果", "生成最终输出"]))

    def _draft_summaries(self) -> list[dict[str, Any]]:
        if not self.drafts_root.exists():
            return []
        return [self._draft_summary(path) for path in sorted(self.drafts_root.glob("*.md")) if not path.is_symlink()]

    @staticmethod
    def _draft_summary(path: Path) -> dict[str, Any]:
        return {"task_type": path.stem, "path": str(path), "content": path.read_text(encoding="utf-8")}

    def _candidate_payload(self) -> dict[str, Any]:
        path = self.memory_root / "skill_candidates.json"
        if not path.exists():
            return {"version": 1, "candidates": []}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {"version": 1, "candidates": []}
        return payload if isinstance(payload, dict) else {"version": 1, "candidates": []}

    def _update_candidate_status(self, task_type: str, status: str) -> None:
        payload = self._candidate_payload()
        candidates = payload.get("candidates") if isinstance(payload.get("candidates"), list) else []
        for candidate in candidates:
            if isinstance(candidate, dict) and candidate.get("task_type") == task_type:
                candidate["status"] = status
                candidate["updated_at"] = datetime.now().isoformat(timespec="seconds")
        path = self.memory_root / "skill_candidates.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _backup(self, path: Path, skill_id: str) -> None:
        backup_root = self.versions_root / self._safe_name(skill_id, "skill_id")
        backup_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        shutil.copy2(path, backup_root / f"{stamp}.md")

    def _write_and_validate(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(content, encoding="utf-8")
        SkillLoader(path.parent)._read_skill(temp)
        temp.replace(path)

    @staticmethod
    def _set_frontmatter_value(content: str, key: str, value: str) -> str:
        pattern = re.compile(rf"(?m)^{re.escape(key)}:\s*.*$")
        replacement = f"{key}: {value}"
        if pattern.search(content):
            return pattern.sub(replacement, content, count=1)
        lines = content.splitlines()
        lines.insert(1, replacement)
        return "\n".join(lines) + ("\n" if content.endswith("\n") else "")

    @staticmethod
    def _safe_name(value: str, label: str) -> str:
        normalized = str(value or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]+", normalized):
            raise ValueError(f"{label} 无效")
        return normalized

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except ValueError:
            return False

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
                    "skills": [str(skill_file.parent.name) for skill_file in skill_files],
                }
            )
        return packs

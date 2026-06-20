# UTA V0.8 Skill Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `v0.8-skill-runtime`, where local Markdown Skills can be built as drafts, loaded at runtime, matched to parsed tasks, and injected into the Planner workflow.

**Architecture:** Add two focused modules: `core.skill_loader` reads official `skills/*.md` files and returns a JSON-serializable matched skill, while `core.skill_builder` writes human-reviewable draft skills under `skills/drafts/`. `main.run_task()` performs Skill matching after TaskParser and before the loop; `core.loop` passes `state.matched_skill` into `Planner`, and Planner uses the Skill workflow when available.

**Tech Stack:** Python 3.12, pathlib, dataclasses already in `core.state`, handwritten front matter parser, pytest, existing CLI and JSON state/log outputs.

---

## File Structure

- Create `core/skill_loader.py`: parse local Markdown Skill files, expose `SkillLoader.load_skills()` and `SkillLoader.match(task)`.
- Create `core/skill_builder.py`: create human-reviewable Skill draft Markdown from `memory/skill_candidates.json` candidate records.
- Create `tests/test_skill_loader.py`: loader parsing, matching, disabled-skill, priority, and invalid-file behavior.
- Create `tests/test_skill_builder.py`: draft generation and draft write behavior.
- Modify `core/planner.py`: accept `matched_skill` and use its `workflow` before fallback task-type goals.
- Modify `core/loop.py`: pass `state.matched_skill` into `Planner.create_plan()`.
- Modify `main.py`: wire `SkillLoader` into `run_task()`, add `skill_loader` injection, and log matched skill id.
- Modify `tests/test_planner.py`: assert Planner uses Skill workflow.
- Modify `tests/test_main.py`: assert injected/default Skill loading writes `state.matched_skill`; allow disabling Skill loading.
- Create `skills/summarize_article.md`: official text summary Skill.
- Create `skills/analyze_table.md`: official table analysis Skill.
- Create `skills/drafts/.gitkeep`: keep draft directory in Git without loading drafts as official Skills.
- Modify `README.md`: document v0.8 Skill format and usage.
- Modify `CHANGELOG.md`: add v0.8 line.
- Modify `examples/expected_output_examples.md`: add Skill runtime example.

---

### Task 1: SkillLoader Markdown Parsing and Matching

**Files:**
- Create: `core/skill_loader.py`
- Create: `tests/test_skill_loader.py`

- [ ] **Step 1: Write failing SkillLoader tests**

Create `tests/test_skill_loader.py`:

```python
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
```

- [ ] **Step 2: Run red SkillLoader tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_skill_loader.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'core.skill_loader'`.

- [ ] **Step 3: Implement SkillLoader**

Create `core/skill_loader.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.state import Task


REQUIRED_FIELDS = ("id", "name", "task_type", "workflow")


class SkillLoader:
    def __init__(self, skills_root: Path | str = "skills"):
        self.skills_root = Path(skills_root)
        self.errors: list[dict[str, str]] = []

    def load_skills(self) -> list[dict[str, Any]]:
        self.errors = []
        if not self.skills_root.exists():
            return []

        skills: list[dict[str, Any]] = []
        for path in sorted(self.skills_root.glob("*.md")):
            try:
                skills.append(self._load_skill(path))
            except ValueError as error:
                self.errors.append({"path": str(path), "error": str(error)})
        return skills

    def match(self, task: Task) -> dict[str, Any] | None:
        matches = []
        searchable_text = f"{task.user_input}\n{task.intent}".lower()
        for skill in self.load_skills():
            if not skill.get("enabled", True):
                continue
            if skill.get("task_type") != task.task_type:
                continue
            keywords = skill.get("trigger_keywords", [])
            if keywords and not any(str(keyword).lower() in searchable_text for keyword in keywords):
                continue
            matches.append(skill)

        if not matches:
            return None

        return sorted(
            matches,
            key=lambda skill: (-int(skill.get("priority", 0)), str(skill.get("id", ""))),
        )[0]

    def _load_skill(self, path: Path) -> dict[str, Any]:
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            raise ValueError("missing front matter")

        parts = text.split("---", 2)
        if len(parts) < 3:
            raise ValueError("missing closing front matter")

        data = self._parse_front_matter(parts[1])
        for field in REQUIRED_FIELDS:
            if field not in data:
                raise ValueError(f"missing required field: {field}")

        workflow = data["workflow"]
        if not isinstance(workflow, list) or not workflow:
            raise ValueError("workflow must be a non-empty list")

        skill = {
            "id": str(data["id"]),
            "name": str(data["name"]),
            "version": int(data.get("version", 1)),
            "enabled": bool(data.get("enabled", True)),
            "task_type": str(data["task_type"]),
            "priority": int(data.get("priority", 0)),
            "trigger_keywords": [str(item) for item in data.get("trigger_keywords", [])],
            "workflow": [str(item) for item in workflow],
            "source_path": str(path),
        }
        return skill

    def _parse_front_matter(self, front_matter: str) -> dict[str, Any]:
        data: dict[str, Any] = {}
        current_list_key: str | None = None

        for raw_line in front_matter.splitlines():
            if not raw_line.strip():
                continue

            if raw_line.startswith("  - "):
                if current_list_key is None:
                    raise ValueError("list item without list key")
                data.setdefault(current_list_key, []).append(raw_line[4:].strip())
                continue

            if raw_line.startswith(" "):
                raise ValueError(f"unsupported indentation: {raw_line}")

            if ":" not in raw_line:
                raise ValueError(f"invalid front matter line: {raw_line}")

            key, value = raw_line.split(":", 1)
            key = key.strip()
            value = value.strip()

            if value == "":
                data[key] = []
                current_list_key = key
            else:
                data[key] = self._parse_scalar(value)
                current_list_key = None

        return data

    def _parse_scalar(self, value: str) -> str | int | bool:
        normalized = value.strip()
        if normalized.lower() == "true":
            return True
        if normalized.lower() == "false":
            return False
        if normalized.isdigit():
            return int(normalized)
        if (
            len(normalized) >= 2
            and normalized[0] in {"'", '"'}
            and normalized[-1] == normalized[0]
        ):
            return normalized[1:-1]
        return normalized
```

- [ ] **Step 4: Run green SkillLoader tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_skill_loader.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit SkillLoader**

```bash
git add core/skill_loader.py tests/test_skill_loader.py
git commit -m "feat: add markdown skill loader"
```

---

### Task 2: SkillBuilder Draft Generation

**Files:**
- Create: `core/skill_builder.py`
- Create: `tests/test_skill_builder.py`

- [ ] **Step 1: Write failing SkillBuilder tests**

Create `tests/test_skill_builder.py`:

```python
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
```

- [ ] **Step 2: Run red SkillBuilder tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_skill_builder.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'core.skill_builder'`.

- [ ] **Step 3: Implement SkillBuilder**

Create `core/skill_builder.py`:

```python
from __future__ import annotations

from pathlib import Path


class SkillBuilder:
    def __init__(self, drafts_root: Path | str = "skills/drafts"):
        self.drafts_root = Path(drafts_root)

    def build_draft(self, candidate: dict, workflow: list[str]) -> str:
        if candidate.get("status") != "candidate":
            raise ValueError("only candidate status can be drafted")
        if not workflow:
            raise ValueError("workflow must be a non-empty list")

        task_type = str(candidate["task_type"])
        skill_id = f"{task_type}_skill"
        reason = str(candidate.get("reason", "来自 Memory 的 Skill 候选。"))
        workflow_lines = "\n".join(f"  - {step}" for step in workflow)
        keyword_lines = "\n".join(f"  - {keyword}" for keyword in self._keywords_for(task_type))

        return (
            "---\n"
            f"id: {skill_id}\n"
            f"name: {task_type} Skill 草稿\n"
            "version: 1\n"
            "enabled: false\n"
            f"task_type: {task_type}\n"
            "priority: 10\n"
            "trigger_keywords:\n"
            f"{keyword_lines}\n"
            "workflow:\n"
            f"{workflow_lines}\n"
            "---\n\n"
            f"# {task_type} Skill 草稿\n\n"
            f"来源：{reason}\n\n"
            "人工确认后，把本文件移动到 `skills/` 根目录并把 `enabled` 改为 `true`。\n"
        )

    def write_draft(self, candidate: dict, workflow: list[str]) -> Path:
        task_type = str(candidate["task_type"])
        self.drafts_root.mkdir(parents=True, exist_ok=True)
        path = self.drafts_root / f"{task_type}.md"
        path.write_text(self.build_draft(candidate, workflow), encoding="utf-8")
        return path

    def _keywords_for(self, task_type: str) -> list[str]:
        if task_type == "summarize":
            return ["总结", "摘要"]
        if task_type == "data_analysis":
            return ["分析", "表格", "csv", "excel"]
        return [task_type]
```

- [ ] **Step 4: Run green SkillBuilder tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_skill_builder.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit SkillBuilder**

```bash
git add core/skill_builder.py tests/test_skill_builder.py
git commit -m "feat: add skill draft builder"
```

---

### Task 3: Planner Skill Workflow Injection

**Files:**
- Modify: `core/planner.py`
- Modify: `core/loop.py`
- Modify: `tests/test_planner.py`

- [ ] **Step 1: Write failing Planner test**

Append to `tests/test_planner.py`:

```python
def test_planner_uses_matched_skill_workflow():
    matched_skill = {
        "id": "custom_summary",
        "workflow": ["读取客户文本", "提炼三条要点", "生成客户版报告"],
    }

    plan = Planner().create_plan(make_task("summarize"), matched_skill=matched_skill)

    assert [step.goal for step in plan.steps] == ["读取客户文本", "提炼三条要点", "生成客户版报告"]
```

- [ ] **Step 2: Run red Planner test**

Run:

```bash
.venv/bin/python -m pytest tests/test_planner.py::test_planner_uses_matched_skill_workflow -v
```

Expected: FAIL with `TypeError: Planner.create_plan() got an unexpected keyword argument 'matched_skill'`.

- [ ] **Step 3: Implement Planner workflow injection**

Replace `core/planner.py` with:

```python
from typing import Any

from core.state import Plan, PlanStep, Task


class Planner:
    def create_plan(self, task: Task, matched_skill: dict[str, Any] | None = None) -> Plan:
        goals = self._goals_from_skill(matched_skill) or self._goals_for(task.task_type)
        return Plan(
            plan_id=f"plan_{task.task_id}",
            task_id=task.task_id,
            steps=[
                PlanStep(step_id=index, goal=goal)
                for index, goal in enumerate(goals, start=1)
            ],
        )

    def _goals_from_skill(self, matched_skill: dict[str, Any] | None) -> list[str]:
        if not matched_skill:
            return []
        workflow = matched_skill.get("workflow")
        if not isinstance(workflow, list):
            return []
        return [str(goal) for goal in workflow if str(goal).strip()]

    def _goals_for(self, task_type: str) -> list[str]:
        if task_type == "summarize":
            return ["读取输入内容", "提取核心信息", "生成结构化报告"]
        if task_type == "data_analysis":
            return ["读取表格文件", "分析字段、行数、列数和缺失值", "生成表格分析报告"]
        return ["执行 V0.3 mock 工具"]
```

- [ ] **Step 4: Wire loop to pass state.matched_skill**

In `core/loop.py`, replace:

```python
    state.plan = planner.create_plan(_task_from_state(state))
```

with:

```python
    state.plan = planner.create_plan(_task_from_state(state), matched_skill=state.matched_skill)
```

- [ ] **Step 5: Run green Planner and loop tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_planner.py tests/test_loop.py -v
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit Planner injection**

```bash
git add core/planner.py core/loop.py tests/test_planner.py
git commit -m "feat: inject matched skill workflow into planner"
```

---

### Task 4: Runtime SkillLoader Integration

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main.py`

- [ ] **Step 1: Add fake loader and failing run_task tests**

In `tests/test_main.py`, add this helper after `FakeMemoryProvider`:

```python
class FakeSkillLoader:
    def __init__(self, matched_skill):
        self.matched_skill = matched_skill
        self.seen_task_types = []

    def match(self, task):
        self.seen_task_types.append(task.task_type)
        return self.matched_skill
```

Append these tests to `tests/test_main.py`:

```python
def test_run_task_saves_matched_skill_with_injected_loader(tmp_path):
    skill = {
        "id": "summarize_article",
        "name": "文本总结 Skill",
        "task_type": "summarize",
        "workflow": ["读取输入内容", "提取核心信息", "生成结构化报告"],
        "source_path": "skills/summarize_article.md",
    }
    skill_loader = FakeSkillLoader(skill)

    state = run_task(
        "帮我总结一段文本",
        output_root=tmp_path,
        task_id="task_test",
        task_parser=FakeParser(),
        tool_registry=make_static_summary_registry(),
        memory_provider=False,
        skill_loader=skill_loader,
    )

    saved = json.loads((tmp_path / "states" / "task_test_state.json").read_text(encoding="utf-8"))
    log_text = (tmp_path / "logs" / "task_test.log").read_text(encoding="utf-8")

    assert skill_loader.seen_task_types == ["summarize"]
    assert state.matched_skill["id"] == "summarize_article"
    assert saved["matched_skill"]["id"] == "summarize_article"
    assert "[SkillLoader] matched_skill = summarize_article" in log_text


def test_run_task_can_disable_skill_loader(tmp_path):
    state = run_task(
        "帮我总结一段文本",
        output_root=tmp_path,
        task_id="task_test",
        task_parser=FakeParser(),
        tool_registry=make_static_summary_registry(),
        memory_provider=False,
        skill_loader=False,
    )

    log_text = (tmp_path / "logs" / "task_test.log").read_text(encoding="utf-8")

    assert state.matched_skill is None
    assert "[SkillLoader] matched_skill = none" in log_text


def test_run_task_uses_default_skill_loader_from_cwd(tmp_path, monkeypatch):
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    (skills_root / "summarize_article.md").write_text(
        """---
id: summarize_article
name: 文本总结 Skill
version: 1
enabled: true
task_type: summarize
priority: 100
trigger_keywords:
  - 总结
workflow:
  - 读取输入内容
  - 提取核心信息
  - 生成结构化报告
---

# 文本总结 Skill
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    state = run_task(
        "帮我总结一段文本",
        output_root=tmp_path / "outputs",
        task_id="task_test",
        task_parser=FakeParser(),
        tool_registry=make_static_summary_registry(),
        memory_provider=False,
    )

    assert state.matched_skill["id"] == "summarize_article"
    assert [step.goal for step in state.plan.steps] == ["读取输入内容", "提取核心信息", "生成结构化报告"]
```

- [ ] **Step 2: Run red main Skill tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_main.py::test_run_task_saves_matched_skill_with_injected_loader tests/test_main.py::test_run_task_can_disable_skill_loader tests/test_main.py::test_run_task_uses_default_skill_loader_from_cwd -v
```

Expected: FAIL with `TypeError: run_task() got an unexpected keyword argument 'skill_loader'`.

- [ ] **Step 3: Update main imports and log output**

In `main.py`, add:

```python
from core.skill_loader import SkillLoader
```

In `build_log_lines()`, after the TaskParser lines are created, insert:

```python
    matched_skill_id = state.matched_skill.get("id") if state.matched_skill else "none"
    lines.append(f"[SkillLoader] matched_skill = {matched_skill_id}")
```

- [ ] **Step 4: Update run_task signature and SkillLoader call**

In `main.py`, change the signature to:

```python
def run_task(
    task: str,
    output_root: Path | str = "outputs",
    task_id: str | None = None,
    task_parser=None,
    tool_registry=None,
    memory_provider=None,
    skill_loader=None,
) -> AgentState:
```

Then after `apply_task_to_state(state, parsed_task)`, insert:

```python
    if skill_loader is False:
        state.matched_skill = None
    else:
        loader = skill_loader if skill_loader is not None else SkillLoader()
        state.matched_skill = loader.match(parsed_task)
```

- [ ] **Step 5: Keep non-Skill tests isolated**

In existing `run_task(...)` calls inside `tests/test_main.py` that are not testing Skill loading, pass `skill_loader=False`. The tests that should keep Skill enabled are the new injected-loader test and `test_run_task_uses_default_skill_loader_from_cwd`.

Example update:

```python
    state = run_task(
        "帮我总结一段文本",
        output_root=tmp_path,
        task_id="task_test",
        task_parser=FakeParser(),
        tool_registry=make_static_summary_registry(),
        memory_provider=False,
        skill_loader=False,
    )
```

- [ ] **Step 6: Run green main Skill tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_main.py -v
```

Expected: all `tests/test_main.py` tests pass.

- [ ] **Step 7: Commit runtime SkillLoader integration**

```bash
git add main.py tests/test_main.py
git commit -m "feat: match skills during task startup"
```

---

### Task 5: Official Example Skills

**Files:**
- Create: `skills/summarize_article.md`
- Create: `skills/analyze_table.md`
- Create: `skills/drafts/.gitkeep`
- Modify: `tests/test_skill_loader.py`

- [ ] **Step 1: Write failing official Skill files test**

Append to `tests/test_skill_loader.py`:

```python
def test_repo_includes_official_runtime_skills():
    skills = SkillLoader("skills").load_skills()
    by_id = {skill["id"]: skill for skill in skills}

    assert by_id["summarize_article"]["workflow"] == ["读取输入内容", "提取核心信息", "生成结构化报告"]
    assert by_id["analyze_table"]["workflow"] == ["读取表格文件", "分析字段、行数、列数和缺失值", "生成表格分析报告"]
```

- [ ] **Step 2: Run red official Skill files test**

Run:

```bash
.venv/bin/python -m pytest tests/test_skill_loader.py::test_repo_includes_official_runtime_skills -v
```

Expected: FAIL with `KeyError: 'summarize_article'` because the official Skill files do not exist yet.

- [ ] **Step 3: Create official summarize Skill**

Create `skills/summarize_article.md`:

```markdown
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
  - 提取
workflow:
  - 读取输入内容
  - 提取核心信息
  - 生成结构化报告
---

# 文本总结 Skill

适用于把一段中文文本整理成包含摘要、核心观点和风险点的结构化报告。
```

- [ ] **Step 4: Create official table analysis Skill**

Create `skills/analyze_table.md`:

```markdown
---
id: analyze_table
name: 表格分析 Skill
version: 1
enabled: true
task_type: data_analysis
priority: 100
trigger_keywords:
  - 分析
  - 表格
  - csv
  - excel
workflow:
  - 读取表格文件
  - 分析字段、行数、列数和缺失值
  - 生成表格分析报告
---

# 表格分析 Skill

适用于读取 CSV 或 Excel 文件，并输出字段说明、基础统计、异常数据、分类汇总、业务解释和后续建议。
```

- [ ] **Step 5: Keep drafts directory tracked**

Create `skills/drafts/.gitkeep` as an empty file. Do not put `.md` files in `skills/drafts/` for this task.

- [ ] **Step 6: Run Skill and main tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_skill_loader.py tests/test_skill_builder.py tests/test_planner.py tests/test_main.py -v
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit official example Skills**

```bash
git add skills tests/test_skill_loader.py
git commit -m "feat: add official runtime skills"
```

---

### Task 6: Documentation and Examples

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `examples/expected_output_examples.md`

- [ ] **Step 1: Update README**

In `README.md`, update the opening paragraph to mention `v0.8-skill-runtime`:

```markdown
UTA 是一个学习型 Agent 框架。当前里程碑是 `v0.8-skill-runtime`：在总结、表格分析和基础 JSON Memory 之外，新增本地 Markdown Skill 的沉淀、加载和 Planner 注入闭环。
```

Add this section after `Memory 示例`:

````markdown
## Skill 示例

UTA 会在任务开始时读取 `skills/*.md`。命中 Skill 后，`Planner` 优先使用 Skill 的 `workflow`：

```bash
.venv/bin/python main.py --task "分析 examples/orders.csv"
```

正式 Skill 文件放在：

- `skills/summarize_article.md`
- `skills/analyze_table.md`

草稿 Skill 放在 `skills/drafts/`，不会被运行时自动加载。人工确认后，把草稿移动到 `skills/` 根目录，并把 `enabled` 改为 `true`。
````

Update current status list with:

```markdown
- `v0.8-skill-runtime`: 新增 `SkillLoader` 和 `SkillBuilder`，支持本地 Markdown Skill 的加载、候选草稿生成和 Planner workflow 注入。
```

- [ ] **Step 2: Update CHANGELOG**

Add under `Unreleased`:

```markdown
- Add `v0.8-skill-runtime` with Markdown Skill loading, draft building, and Planner workflow injection.
```

- [ ] **Step 3: Update expected output examples**

Append to `examples/expected_output_examples.md`:

````markdown
## V0.8 Skill Runtime

`outputs/logs/<task_id>.log` includes the matched Skill:

```text
[SkillLoader] matched_skill = analyze_table
[Planner] created 3 steps
[Loop] step 1 started: 读取表格文件
```

`outputs/states/<task_id>_state.json` includes:

```json
"matched_skill": {
  "id": "analyze_table",
  "name": "表格分析 Skill",
  "task_type": "data_analysis"
}
```
````

- [ ] **Step 4: Run docs-adjacent tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_skill_loader.py tests/test_skill_builder.py tests/test_main.py -v
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit documentation**

```bash
git add README.md CHANGELOG.md examples/expected_output_examples.md
git commit -m "docs: document skill runtime flow"
```

---

### Task 7: Full Verification and v0.8 Tag

**Files:**
- No source changes expected.

- [ ] **Step 1: Run full tests**

Run:

```bash
.venv/bin/python -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 2: Run CLI smoke in an external temporary directory**

Run:

```bash
mkdir -p /private/tmp/uta-v0-8-smoke
```

Copy `examples/orders.csv` into the smoke directory:

```bash
cp examples/orders.csv /private/tmp/uta-v0-8-smoke/orders.csv
```

Run the CLI from that smoke directory:

```bash
/Users/tianjiashu/项目/.venv/bin/python /Users/tianjiashu/项目/main.py --task "分析 orders.csv"
```

Expected stdout contains:

```text
任务已完成：
## 字段说明
行数：10
```

Then inspect the generated log in the smoke directory:

```bash
/Users/tianjiashu/项目/.venv/bin/python -c "from pathlib import Path; logs=sorted(Path('/private/tmp/uta-v0-8-smoke/outputs/logs').glob('*.log'), key=lambda path: path.stat().st_mtime); print(logs[-1].read_text(encoding='utf-8'))"
```

Confirm the printed log text contains:

```text
[SkillLoader] matched_skill =
[Memory] saved = true
```

If the CLI is run from `/private/tmp/uta-v0-8-smoke` without copying `skills/`, matched skill may be `none`; this is acceptable for the smoke because it proves the default no-Skill path still works outside the repo. The repo-root tests prove official Skill matching.

- [ ] **Step 3: Run repo-root Skill CLI smoke**

Run from `/Users/tianjiashu/项目`:

```bash
.venv/bin/python main.py --task "分析 examples/orders.csv"
```

Expected stdout contains:

```text
任务已完成：
## 字段说明
行数：10
```

Inspect the latest repo-root log:

```bash
.venv/bin/python -c "from pathlib import Path; logs=sorted(Path('outputs/logs').glob('*.log'), key=lambda path: path.stat().st_mtime); print(logs[-1].read_text(encoding='utf-8'))"
```

Confirm the printed log text contains:

```text
[SkillLoader] matched_skill = analyze_table
```

This repo-root smoke updates tracked `memory/*.json`; review the diff and commit it only if the new demo memory record is intentionally part of the v0.8 handoff. Otherwise leave it unstaged and explain it in the final response.

- [ ] **Step 4: Check status and secrets**

Run:

```bash
git status --short
```

Expected: no uncommitted source/doc changes from v0.8 implementation. Existing unrelated untracked files may still appear.

Run:

```bash
git grep -n -E 'tp-[[:alnum:]]{20,}'
```

Expected: exit code 1 with no output.

- [ ] **Step 5: Tag v0.8**

Run:

```bash
git tag v0.8-skill-runtime
git tag --list "v0.8-skill-runtime"
```

Expected output:

```text
v0.8-skill-runtime
```

---

## Self-Review

- Spec coverage: Task 1 covers SkillLoader parsing and matching; Task 2 covers SkillBuilder draft generation; Task 3 covers Planner injection; Task 4 covers runtime state/log integration; Task 5 covers official Skill files; Task 6 covers docs and examples; Task 7 covers final verification and tag.
- Scope check: plan excludes TAM, semantic matching, vector retrieval, automatic Skill publishing, and Tool protocol changes.
- Type consistency: `SkillLoader.match(task)` returns `dict | None`; `AgentState.matched_skill` already accepts `dict | None`; `Planner.create_plan(task, matched_skill=None)` consumes the same shape.
- Test discipline: each production behavior starts with a failing pytest target before implementation, and each task commits only its own files.

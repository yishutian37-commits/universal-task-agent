from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any


def current_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def dataclass_to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return {key: dataclass_to_dict(item) for key, item in asdict(value).items()}
    if isinstance(value, list):
        return [dataclass_to_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: dataclass_to_dict(item) for key, item in value.items()}
    return value


@dataclass
class Task:
    task_id: str
    user_input: str
    task_type: str
    intent: str
    input_type: str
    expected_output: str
    constraints: list[str] = field(default_factory=list)
    missing_info: list[str] = field(default_factory=list)


@dataclass
class PlanStep:
    step_id: int
    goal: str
    status: str = "pending"
    max_retries: int = 2


@dataclass
class Plan:
    plan_id: str
    task_id: str
    steps: list[PlanStep]
    status: str = "pending"


@dataclass
class Action:
    action_id: str
    step_id: int
    tool_name: str
    action_name: str
    params: dict[str, Any]
    reason: str


@dataclass
class ToolResult:
    success: bool
    tool_name: str
    action_name: str
    result: dict[str, Any]
    error: str | None = None


@dataclass
class CheckResult:
    passed: bool
    failed_reasons: list[str]
    suggested_fix: list[str]
    score: float | None = None


@dataclass
class Feedback:
    failure_type: str
    root_cause: str
    repair_strategy: str
    need_replan: bool = False
    need_user_input: bool = False


@dataclass
class AgentState:
    task_id: str
    user_input: str
    task_type: str = "unknown"
    intent: str = ""
    status: str = "initialized"
    current_step_id: int = 0
    max_replans: int = 1
    plan: Plan | None = None
    matched_skill: dict[str, Any] | None = None
    current_action: Action | None = None
    results: list[ToolResult] = field(default_factory=list)
    checks: list[CheckResult] = field(default_factory=list)
    feedbacks: list[Feedback] = field(default_factory=list)
    final_output: str | None = None
    created_at: str = field(default_factory=current_timestamp)
    updated_at: str = field(default_factory=current_timestamp)

    def touch(self) -> None:
        self.updated_at = current_timestamp()

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    def save_json(self, output_dir: Path | str) -> Path:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        file_path = output_path / f"{self.task_id}_state.json"
        file_path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return file_path

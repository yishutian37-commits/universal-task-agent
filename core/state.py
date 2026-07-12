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


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


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
    step_id: int | None = None


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
    execution_input: str | None = None
    conversation_id: str | None = None
    workspace_path: str | None = None
    task_type: str = "unknown"
    intent: str = ""
    status: str = "initialized"
    current_step_id: int = 0
    max_replans: int = 1
    replan_count: int = 0
    replan_events: list[dict[str, Any]] = field(default_factory=list)
    plan: Plan | None = None
    matched_skill: dict[str, Any] | None = None
    current_action: Action | None = None
    results: list[ToolResult] = field(default_factory=list)
    checks: list[CheckResult] = field(default_factory=list)
    feedbacks: list[Feedback] = field(default_factory=list)
    final_output: str | None = None
    memory_saved: bool = False
    created_at: str = field(default_factory=current_timestamp)
    updated_at: str = field(default_factory=current_timestamp)

    def touch(self) -> None:
        self.updated_at = current_timestamp()

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AgentState":
        state = cls(
            task_id=str(payload.get("task_id") or ""),
            user_input=str(payload.get("user_input") or ""),
            execution_input=payload.get("execution_input"),
            conversation_id=payload.get("conversation_id"),
            workspace_path=payload.get("workspace_path"),
            task_type=str(payload.get("task_type") or "unknown"),
            intent=str(payload.get("intent") or ""),
            status=str(payload.get("status") or "initialized"),
            current_step_id=int(payload.get("current_step_id") or 0),
            max_replans=int(payload.get("max_replans") or 1),
            replan_count=int(payload.get("replan_count") or 0),
            replan_events=_list_of_dicts(payload.get("replan_events")),
            final_output=payload.get("final_output"),
            memory_saved=bool(payload.get("memory_saved") or False),
            created_at=str(payload.get("created_at") or current_timestamp()),
            updated_at=str(payload.get("updated_at") or current_timestamp()),
        )
        plan_payload = payload.get("plan")
        if isinstance(plan_payload, dict):
            state.plan = Plan(
                plan_id=str(plan_payload.get("plan_id") or ""),
                task_id=str(plan_payload.get("task_id") or state.task_id),
                steps=[
                    PlanStep(
                        step_id=int(step.get("step_id") or 0),
                        goal=str(step.get("goal") or ""),
                        status=str(step.get("status") or "pending"),
                        max_retries=int(step.get("max_retries") or 2),
                    )
                    for step in _list_of_dicts(plan_payload.get("steps"))
                ],
                status=str(plan_payload.get("status") or "pending"),
            )
        action_payload = payload.get("current_action")
        if isinstance(action_payload, dict):
            state.current_action = Action(
                action_id=str(action_payload.get("action_id") or ""),
                step_id=int(action_payload.get("step_id") or 0),
                tool_name=str(action_payload.get("tool_name") or ""),
                action_name=str(action_payload.get("action_name") or ""),
                params=dict(action_payload.get("params") or {}),
                reason=str(action_payload.get("reason") or ""),
            )
        state.matched_skill = payload.get("matched_skill") if isinstance(payload.get("matched_skill"), dict) else None
        state.results = [
            ToolResult(
                success=bool(item.get("success") or False),
                tool_name=str(item.get("tool_name") or ""),
                action_name=str(item.get("action_name") or ""),
                result=dict(item.get("result") or {}),
                error=item.get("error"),
                step_id=item.get("step_id"),
            )
            for item in _list_of_dicts(payload.get("results"))
        ]
        state.checks = [
            CheckResult(
                passed=bool(item.get("passed") or False),
                failed_reasons=list(item.get("failed_reasons") or []),
                suggested_fix=list(item.get("suggested_fix") or []),
                score=item.get("score"),
            )
            for item in _list_of_dicts(payload.get("checks"))
        ]
        state.feedbacks = [
            Feedback(
                failure_type=str(item.get("failure_type") or ""),
                root_cause=str(item.get("root_cause") or ""),
                repair_strategy=str(item.get("repair_strategy") or ""),
                need_replan=bool(item.get("need_replan") or False),
                need_user_input=bool(item.get("need_user_input") or False),
            )
            for item in _list_of_dicts(payload.get("feedbacks"))
        ]
        return state

    def save_json(self, output_dir: Path | str) -> Path:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        file_path = output_path / f"{self.task_id}_state.json"
        file_path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return file_path

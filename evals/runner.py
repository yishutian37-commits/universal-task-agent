from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from core.planner import Planner
from core.router import Router
from core.state import AgentState
from core.task_parser import TaskParser
from desktop.message_router import MessageRouter


DEFAULT_CASES_PATH = Path(__file__).parent / "cases" / "core_scenarios.json"


class OfflineClient:
    def chat_json(self, *_args, **_kwargs):
        raise RuntimeError("offline evaluation")


def load_cases(path: Path | str | None = None) -> list[dict[str, Any]]:
    source = Path(path) if path is not None else DEFAULT_CASES_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("评测集必须是 JSON 数组")
    return [item for item in payload if isinstance(item, dict)]


def evaluate_cases(cases: list[dict[str, Any]], *, live_model: bool = False) -> dict[str, Any]:
    client = _live_client() if live_model else OfflineClient()
    results = [_evaluate_case(case, client) for case in cases]
    passed = sum(1 for result in results if result["passed"])
    return {
        "mode": "live-model" if live_model else "offline",
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "pass_rate": round(passed / len(results), 4) if results else 0.0,
        "results": results,
    }


def _evaluate_case(case: dict[str, Any], client) -> dict[str, Any]:
    case_id = str(case.get("id") or "unnamed")
    user_input = str(case.get("input") or "")
    expected = case.get("expect") if isinstance(case.get("expect"), dict) else {}
    actual: dict[str, Any] = {}
    failures: list[dict[str, Any]] = []
    try:
        decision = MessageRouter().route(user_input, context="", client=client)
        actual["message_kind"] = decision.kind
        if decision.kind == "task" or any(key in expected for key in ("task_type", "plan_steps", "first_tool")):
            task = TaskParser(client).parse(f"task_eval_{case_id}", user_input)
            plan = Planner().create_plan(task)
            state = AgentState(
                task_id=task.task_id,
                user_input=task.user_input,
                execution_input=task.user_input,
                task_type=task.task_type,
                intent=task.intent,
                plan=plan,
            )
            actual["task_type"] = task.task_type
            actual["plan_steps"] = len(plan.steps)
            if plan.steps:
                actual["first_tool"] = Router().choose_tool(state, plan.steps[0]).tool_name
    except Exception as exc:
        failures.append({"field": "execution", "expected": "no error", "actual": str(exc)})

    for field, expected_value in expected.items():
        if actual.get(field) != expected_value:
            failures.append({"field": field, "expected": expected_value, "actual": actual.get(field)})
    return {
        "id": case_id,
        "input": user_input,
        "passed": not failures,
        "expected": expected,
        "actual": actual,
        "failures": failures,
    }


def _live_client():
    from llm.llm_client import LLMClient

    return LLMClient.from_config()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="运行 UTA 中文核心任务评测集")
    parser.add_argument("--cases", default=str(DEFAULT_CASES_PATH), help="评测集 JSON 路径")
    parser.add_argument("--live-model", action="store_true", help="使用当前配置的真实模型进行路由与解析")
    parser.add_argument("--json", action="store_true", help="输出完整 JSON 报告")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = evaluate_cases(load_cases(args.cases), live_model=args.live_model)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"UTA 核心评测：{report['passed']}/{report['total']} 通过，失败 {report['failed']} 项")
        for result in report["results"]:
            marker = "通过" if result["passed"] else "失败"
            print(f"[{marker}] {result['id']}: {result['input']}")
            for failure in result["failures"]:
                print(f"  - {failure['field']}: 期望 {failure['expected']}，实际 {failure['actual']}")
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from core.interaction import InteractionDecision
from core.loop import run_minimal_loop
from core.planner import Planner
from core.router import Router
from core.state import AgentState, Plan, PlanStep, Task, ToolResult
from core.task_parser import TaskParser
from desktop.message_router import MessageRouter
from tools.base_tool import BaseTool
from tools.langchain_common_tools import ShellLangChainTool


DEFAULT_CASES_PATH = Path(__file__).parent / "cases" / "core_scenarios.json"


class OfflineClient:
    def chat_json(self, *_args, **_kwargs):
        raise RuntimeError("offline evaluation")


class StaticJsonClient:
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload

    def chat_json(self, *_args, **_kwargs):
        return self.payload


class EvalTool(BaseTool):
    description = "Offline evaluation tool"

    def __init__(self, name: str):
        self.name = name
        self.calls = 0
        self.actions: list[str] = []

    def run(self, action_name, params):
        del params
        self.calls += 1
        self.actions.append(str(action_name or ""))
        report = "## 摘要\n已完成。\n## 核心观点\n流程正常。\n## 风险点\n暂无。"
        return {"message": report, "summary_markdown": report, "report_markdown": report}


class ImmediateInteraction:
    def __init__(self, decision: InteractionDecision):
        self.decision = decision
        self.requests: list[dict[str, Any]] = []

    def request(self, kind, payload, **kwargs):
        self.requests.append({"kind": kind, "payload": payload, **kwargs})
        return self.decision


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
        scenario = str(case.get("scenario") or "routing")
        if scenario == "routing":
            actual.update(_evaluate_routing_case(case_id, user_input, expected, client))
        else:
            actual.update(_evaluate_agent_loop_case(scenario, case_id, user_input, case))
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


def _evaluate_routing_case(case_id: str, user_input: str, expected: dict[str, Any], client) -> dict[str, Any]:
    actual: dict[str, Any] = {}
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
    return actual


def _evaluate_agent_loop_case(
    scenario: str,
    case_id: str,
    user_input: str,
    case: dict[str, Any],
) -> dict[str, Any]:
    tool_names = [str(name) for name in case.get("tools") or []]
    registry = {name: EvalTool(name) for name in tool_names}
    payload = case.get("model_payload") if isinstance(case.get("model_payload"), dict) else {}
    client = StaticJsonClient(payload)
    catalog = [
        {
            "name": name,
            "description": registry[name].description,
            "default_action": "read" if name == "file_tool" else "generate" if name == "report_tool" else "process",
            "requires_authorization": False,
        }
        for name in tool_names
    ]
    task = Task(
        task_id=f"task_eval_{case_id}",
        user_input=user_input,
        task_type="complex_task" if scenario == "plan_rejected" else "summarize",
        intent=scenario,
        input_type="text",
        expected_output="report",
    )

    if scenario == "structured_plan":
        plan = Planner(llm_client=client, tool_catalog=catalog).create_plan(task)
        return {
            "plan_source": plan.source,
            "plan_steps": len(plan.steps),
            "first_tool_hint": plan.steps[0].tool_hint if plan.steps else None,
        }
    if scenario == "dynamic_tool_route":
        state = AgentState(task_id=task.task_id, user_input=user_input, task_type="summarize")
        action = Router(llm_client=client, tool_registry=registry).choose_tool(
            state,
            PlanStep(step_id=1, goal="整理为报告"),
        )
        return {"selected_tool": action.tool_name, "selected_action": action.action_name}
    if scenario == "failure_replan":
        existing = Plan(
            plan_id=f"plan_{task.task_id}",
            task_id=task.task_id,
            steps=[
                PlanStep(step_id=1, goal="读取输入", status="completed"),
                PlanStep(step_id=2, goal="提取核心信息", status="failed"),
            ],
        )
        plan = Planner(llm_client=client, tool_catalog=catalog).create_plan(
            task,
            failure_context={
                "failed_step_id": 2,
                "failed_goal": "提取核心信息",
                "root_cause": "缺少风险点",
                "repair_strategy": "补齐风险点",
            },
            existing_plan=existing,
        )
        return {
            "plan_source": plan.source,
            "preserved_completed_steps": sum(step.status == "completed" for step in plan.steps),
            "resume_step_id": next((step.step_id for step in plan.steps if step.status != "completed"), None),
        }
    if scenario == "invalid_action_contract":
        state = AgentState(
            task_id=task.task_id,
            user_input=user_input,
            task_type="summarize",
        )
        action = Router(llm_client=client, tool_registry=registry).choose_tool(
            state,
            PlanStep(step_id=1, goal="把结论整理为报告"),
        )
        tool = registry.get(action.tool_name)
        if tool is not None:
            tool.run(action.action_name, action.params)
        return {
            "selected_tool": action.tool_name,
            "selected_action": action.action_name,
            "invalid_action_executed": any(
                "publish" in item.actions for item in registry.values()
            ),
            "tool_runs": sum(item.calls for item in registry.values()),
        }
    if scenario == "failed_success_criteria":
        state = AgentState(
            task_id=task.task_id,
            user_input=user_input,
            task_type="summarize",
            max_replans=0,
            plan=Plan(
                plan_id=f"plan_{task.task_id}",
                task_id=task.task_id,
                steps=[
                    PlanStep(
                        step_id=1,
                        goal="生成结论",
                        max_retries=0,
                        tool_hint="report_tool",
                        action_hint="generate",
                        success_criteria=["结果包含来源"],
                    )
                ],
            ),
        )
        state = run_minimal_loop(state, tool_registry=registry)
        return {
            "status": state.status,
            "criterion_status": state.criterion_results[-1].status,
            "tool_runs": sum(item.calls for item in registry.values()),
        }
    if scenario == "edited_plan_rebinding":
        state = AgentState(
            task_id=task.task_id,
            user_input=user_input,
            task_type="complex_task",
            plan=Plan(
                plan_id=f"plan_{task.task_id}",
                task_id=task.task_id,
                requires_confirmation=True,
                steps=[
                    PlanStep(
                        step_id=1,
                        goal="读取输入文件",
                        tool_hint="file_tool",
                        action_hint="read",
                    )
                ],
            ),
        )
        interaction = ImmediateInteraction(
            InteractionDecision(
                "eval_edit_plan",
                True,
                "accepted",
                steps=["提取核心信息"],
            )
        )
        state = run_minimal_loop(
            state,
            tool_registry=registry,
            interaction_manager=interaction,
        )
        return {
            "status": state.status,
            "plan_source": state.plan.source,
            "selected_tool": state.results[-1].tool_name if state.results else None,
            "file_runs": registry["file_tool"].calls,
            "text_runs": registry["text_tool"].calls,
        }
    if scenario == "interaction_restart":
        state = AgentState(
            task_id=task.task_id,
            user_input=user_input,
            task_type="complex_task",
            status="waiting_user",
            plan=Plan(
                plan_id=f"plan_{task.task_id}",
                task_id=task.task_id,
                status="running",
                requires_confirmation=True,
                steps=[
                    PlanStep(step_id=1, goal="已完成步骤", status="completed"),
                    PlanStep(
                        step_id=2,
                        goal="提取核心信息",
                        tool_hint="text_tool",
                        action_hint="process",
                    ),
                ],
            ),
        )
        state.results.append(
            ToolResult(True, "file_tool", "read", {"message": "已完成"}, step_id=1)
        )
        state.pending_interaction = {
            "request_id": "eval_restart_stable",
            "task_id": state.task_id,
            "kind": "plan_confirmation",
            "payload": {
                "title": "确认执行计划",
                "question": "请确认继续",
                "steps": [
                    {"step_id": step.step_id, "goal": step.goal}
                    for step in state.plan.steps
                ],
            },
            "status": "pending",
            "created_at": "2026-07-15T08:00:00",
        }
        interaction = ImmediateInteraction(
            InteractionDecision("eval_restart_stable", True, "accepted")
        )
        state = run_minimal_loop(
            state,
            tool_registry=registry,
            interaction_manager=interaction,
        )
        return {
            "status": state.status,
            "replayed_request_id": interaction.requests[0].get("request_id"),
            "completed_prefix": sum(
                result.step_id == 1 for result in state.results
            ),
            "tool_runs": registry["text_tool"].calls,
        }
    if scenario == "waiting_user":
        state = AgentState(
            task_id=task.task_id,
            user_input=user_input,
            task_type="summarize",
            intent="summarize",
            missing_info=["需要总结的文本"],
        )
        tools = {name: EvalTool(name) for name in ("file_tool", "text_tool", "report_tool")}
        decision = InteractionDecision("eval_wait", True, "accepted", "需要总结的内容")
        state = run_minimal_loop(state, tool_registry=tools, interaction_manager=ImmediateInteraction(decision))
        return {
            "status": state.status,
            "interaction_status": state.interaction_history[-1]["status"],
            "missing_info_count": len(state.missing_info),
        }
    if scenario == "plan_rejected":
        state = AgentState(
            task_id=task.task_id,
            user_input=user_input,
            task_type="complex_task",
            intent="execute_complex_task",
        )
        text_tool = EvalTool("text_tool")
        decision = InteractionDecision("eval_reject", False, "rejected", "取消")
        state = run_minimal_loop(
            state,
            tool_registry={"text_tool": text_tool},
            interaction_manager=ImmediateInteraction(decision),
        )
        return {
            "status": state.status,
            "interaction_status": state.interaction_history[-1]["status"],
            "tool_runs": text_tool.calls,
        }
    if scenario == "authorization_rejected":
        class RejectAuthorization:
            def request(self, *_args, **_kwargs):
                return SimpleNamespace(approved=False, reason="用户拒绝授权", approved_by="")

        command_executed = False

        def command_runner(*_args, **_kwargs):
            nonlocal command_executed
            command_executed = True
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        tool = ShellLangChainTool(
            authorization_manager=RejectAuthorization(),
            enabled=True,
            allowed_roots=[Path("/tmp")],
            command_runner=command_runner,
        )
        status = "approved"
        try:
            tool.invoke({"command": "echo hello", "cwd": "/tmp"})
        except PermissionError:
            status = "rejected"
        return {"authorization_status": status, "command_executed": command_executed}
    raise ValueError(f"未知评测场景：{scenario}")


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

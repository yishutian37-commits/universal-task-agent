import re
import json
from dataclasses import replace
from typing import Any

from core.state import Plan, PlanStep, Task
from core.tool_catalog import get_action_contract, validate_action_params


class Planner:
    def __init__(self, llm_client=None, tool_catalog: list[dict[str, Any]] | None = None):
        self.llm_client = llm_client
        self.tool_catalog = list(tool_catalog or [])

    def create_plan(
        self,
        task: Task,
        matched_skill: dict[str, Any] | None = None,
        failure_context: dict[str, Any] | None = None,
        existing_plan: Plan | None = None,
    ) -> Plan:
        if failure_context is not None:
            model_replan = self._create_model_plan(
                task,
                failure_context=failure_context,
                existing_plan=existing_plan,
            )
            if model_replan is not None:
                return model_replan
            return self._fallback_replan(task, failure_context, existing_plan)

        skill_goals = self._goals_from_skill(matched_skill)
        if skill_goals:
            return self._plan_from_goals(task, skill_goals, source="skill")

        model_plan = self._create_model_plan(task)
        if model_plan is not None:
            return model_plan

        return self._plan_from_goals(task, self._goals_for_task(task), source="template")

    def _plan_from_goals(self, task: Task, goals: list[str], source: str) -> Plan:
        return Plan(
            plan_id=f"plan_{task.task_id}",
            task_id=task.task_id,
            steps=[
                PlanStep(step_id=index, goal=goal, max_retries=self._max_retries_for_task(task.task_type))
                for index, goal in enumerate(goals, start=1)
            ],
            source=source,
            requires_confirmation=task.task_type == "complex_task",
        )

    def _create_model_plan(
        self,
        task: Task,
        failure_context: dict[str, Any] | None = None,
        existing_plan: Plan | None = None,
    ) -> Plan | None:
        chat_json = getattr(self.llm_client, "chat_json", None)
        if not callable(chat_json):
            return None
        try:
            payload = chat_json(
                self._system_prompt(),
                self._user_prompt(task, failure_context=failure_context, existing_plan=existing_plan),
                schema=self._response_schema(),
            )
            return self._validate_model_plan(
                task,
                payload,
                failure_context=failure_context,
                existing_plan=existing_plan,
            )
        except Exception:
            return None

    def _validate_model_plan(
        self,
        task: Task,
        payload: Any,
        failure_context: dict[str, Any] | None = None,
        existing_plan: Plan | None = None,
    ) -> Plan | None:
        if not isinstance(payload, dict):
            return None
        raw_steps = payload.get("steps")
        completed_prefix = self._completed_prefix(existing_plan, failure_context)
        if (
            not isinstance(raw_steps, list)
            or not raw_steps
            or len(completed_prefix) + len(raw_steps) > 8
        ):
            return None

        catalog_by_name = {
            str(item.get("name")): item
            for item in self.tool_catalog
            if isinstance(item, dict) and item.get("name")
        }
        steps: list[PlanStep] = list(completed_prefix)
        start_index = len(completed_prefix) + 1
        for index, raw_step in enumerate(raw_steps, start=start_index):
            if not isinstance(raw_step, dict):
                return None
            goal = raw_step.get("goal")
            if not isinstance(goal, str) or not goal.strip():
                return None

            tool_hint = raw_step.get("tool_hint")
            if tool_hint in (None, ""):
                tool_hint = None
            elif not isinstance(tool_hint, str) or tool_hint not in catalog_by_name:
                return None

            action_hint = raw_step.get("action_hint")
            if action_hint in (None, ""):
                action_hint = None
            elif not isinstance(action_hint, str):
                return None

            inputs = raw_step.get("inputs") or {}
            if not isinstance(inputs, dict):
                return None
            action_contract = None
            if tool_hint is not None:
                catalog_item = catalog_by_name[tool_hint]
                effective_action = action_hint or str(catalog_item.get("default_action") or "")
                action_contract = get_action_contract(catalog_item, effective_action)
                if action_contract is None or not validate_action_params(
                    action_contract.get("parameter_schema"),
                    inputs,
                ):
                    return None
            elif action_hint is not None:
                return None
            depends_on = raw_step.get("depends_on") or []
            if not isinstance(depends_on, list) or any(
                not isinstance(item, int) or isinstance(item, bool) or item < 1 or item >= index
                for item in depends_on
            ):
                return None
            success_criteria = raw_step.get("success_criteria") or []
            if not isinstance(success_criteria, list) or any(
                not isinstance(item, str) or not item.strip() for item in success_criteria
            ):
                return None

            catalog_requires_auth = bool(
                action_contract and action_contract.get("requires_authorization")
            )
            steps.append(
                PlanStep(
                    step_id=index,
                    goal=goal.strip(),
                    max_retries=self._max_retries_for_task(task.task_type),
                    tool_hint=tool_hint,
                    action_hint=action_hint.strip() if isinstance(action_hint, str) else None,
                    inputs=dict(inputs),
                    depends_on=list(depends_on),
                    success_criteria=[item.strip() for item in success_criteria],
                    requires_authorization=(
                        catalog_requires_auth or bool(raw_step.get("requires_authorization"))
                    ),
                )
            )

        requires_confirmation = (
            bool(payload.get("requires_confirmation"))
            or task.task_type == "complex_task"
            or any(step.requires_authorization for step in steps)
        )
        reason = payload.get("reason")
        return Plan(
            plan_id=(
                f"plan_{task.task_id}_replan"
                if failure_context is not None
                else f"plan_{task.task_id}"
            ),
            task_id=task.task_id,
            steps=steps,
            source="replan" if failure_context is not None else "model",
            requires_confirmation=requires_confirmation,
            reason=reason.strip() if isinstance(reason, str) else "",
        )

    @staticmethod
    def _system_prompt() -> str:
        return (
            "你是 UTA 的任务 Planner。只返回 JSON，不要输出解释。"
            "将任务拆成 1 到 8 个可执行步骤，只能使用工具目录中的名称。"
            "不确定工具时将 tool_hint 设为 null，不得虚构工具。"
        )

    def _user_prompt(
        self,
        task: Task,
        failure_context: dict[str, Any] | None = None,
        existing_plan: Plan | None = None,
    ) -> str:
        prompt = (
            "请根据任务与工具目录生成结构化计划。\n"
            "返回字段：steps、requires_confirmation、reason。\n"
            "steps 每项字段：goal、tool_hint、action_hint、inputs、"
            "depends_on、success_criteria、requires_authorization。\n"
            f"任务：{task.user_input}\n"
            f"任务类型：{task.task_type}\n"
            f"意图：{task.intent}\n"
            f"约束：{json.dumps(task.constraints, ensure_ascii=False)}\n"
            f"缺失信息：{json.dumps(task.missing_info, ensure_ascii=False)}\n"
            f"工具目录：{json.dumps(self.tool_catalog, ensure_ascii=False)}"
        )
        if failure_context is None:
            return prompt
        existing_steps = [
            {"step_id": step.step_id, "goal": step.goal, "status": step.status}
            for step in existing_plan.steps
        ] if existing_plan is not None else []
        return (
            prompt
            + "\n这是失败后的重新规划。只返回失败步骤及其后的新步骤，"
            "不要重复已完成步骤。\n"
            f"原计划：{json.dumps(existing_steps, ensure_ascii=False)}\n"
            f"失败上下文：{json.dumps(failure_context, ensure_ascii=False)}"
        )

    def _completed_prefix(
        self,
        existing_plan: Plan | None,
        failure_context: dict[str, Any] | None,
    ) -> list[PlanStep]:
        if existing_plan is None or failure_context is None:
            return []
        failed_step_id = int(failure_context.get("failed_step_id") or 1)
        return [
            replace(step, status="completed")
            for step in existing_plan.steps
            if step.step_id < failed_step_id and step.status == "completed"
        ]

    def _fallback_replan(
        self,
        task: Task,
        failure_context: dict[str, Any],
        existing_plan: Plan | None,
    ) -> Plan:
        base_plan = existing_plan or self._plan_from_goals(
            task,
            self._goals_for_task(task),
            source="template",
        )
        failed_step_id = int(failure_context.get("failed_step_id") or 1)
        repair_strategy = str(failure_context.get("repair_strategy") or "根据失败原因调整执行方式")
        steps: list[PlanStep] = []
        for step in base_plan.steps:
            status = "completed" if step.step_id < failed_step_id and step.status == "completed" else "pending"
            goal = step.goal
            if step.step_id == failed_step_id:
                goal = f"{goal}（修复：{repair_strategy}）"
            steps.append(replace(step, goal=goal, status=status))
        return Plan(
            plan_id=f"plan_{task.task_id}_replan",
            task_id=task.task_id,
            steps=steps,
            status="pending",
            source="replan",
            requires_confirmation=base_plan.requires_confirmation,
            reason=f"根据失败原因重新规划：{repair_strategy}",
        )

    @staticmethod
    def _response_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["steps", "requires_confirmation"],
            "properties": {
                "steps": {"type": "array", "minItems": 1, "maxItems": 8},
                "requires_confirmation": {"type": "boolean"},
                "reason": {"type": "string"},
            },
        }

    def _goals_from_skill(self, matched_skill: dict[str, Any] | None) -> list[str]:
        if not matched_skill:
            return []
        workflow = matched_skill.get("workflow")
        if not isinstance(workflow, list):
            return []
        return [goal for goal in workflow if isinstance(goal, str) and goal.strip()]

    def _goals_for_task(self, task: Task) -> list[str]:
        if task.task_type == "complex_task":
            return self._complex_task_goals(task.user_input)
        return self._goals_for(task.task_type)

    def _goals_for(self, task_type: str) -> list[str]:
        if task_type == "summarize":
            return ["读取输入内容", "提取核心信息", "生成结构化报告"]
        if task_type == "data_analysis":
            return ["读取表格文件", "分析字段、行数、列数和缺失值", "生成表格分析报告"]
        if task_type == "research":
            return ["搜索相关资料", "生成带来源的调研报告"]
        if task_type == "code_reading":
            return ["扫描 UTA 任务执行链路代码", "生成代码阅读报告"]
        if task_type == "geo_analysis":
            return ["读取 GEO 规则包并生成问题矩阵", "生成 GEO 分析报告"]
        if task_type == "history_query":
            return ["读取历史任务记录"]
        if task_type == "langchain_tool":
            return ["调用 LangChain 工具处理请求"]
        return ["当前任务类型不受支持，停止执行并说明能力边界"]

    def _max_retries_for_task(self, task_type: str) -> int:
        if task_type == "unknown":
            return 0
        return 2

    def _complex_task_goals(self, user_input: str) -> list[str]:
        goals = self._numbered_goals(user_input) or self._connector_goals(user_input)
        if goals:
            return goals[:8]
        return ["分析复杂任务目标", "执行主要任务步骤", "汇总复杂任务结果"]

    def _numbered_goals(self, user_input: str) -> list[str]:
        task_text = self._task_list_text(user_input)
        pattern = re.compile(r"(?:\[(\d+)\]|（(\d+)）|\((\d+)\)|(?<![\d.])(\d{1,2})[.、](?!\d))\s*")
        matches = list(pattern.finditer(task_text))
        if not matches:
            return []

        goals = []
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(task_text)
            goal = self._clean_complex_goal(task_text[start:end])
            if goal:
                goals.append(goal)
        return goals

    def _connector_goals(self, user_input: str) -> list[str]:
        text = self._task_list_text(user_input)
        if "：" in text:
            text = text.split("：", 1)[1]
        elif ":" in text:
            text = text.split(":", 1)[1]

        parts = re.split(r"(?:然后|最后|接着|再|并且|同时)", text)
        goals = [self._clean_complex_goal(part) for part in parts]
        goals = [goal for goal in goals if goal]
        if len(goals) < 2:
            return []
        return goals

    def _clean_complex_goal(self, goal: str) -> str:
        cleaned = goal.strip()
        cleaned = cleaned.strip(" \t\r\n，,。；;、：:")
        cleaned = re.sub(r"^(请|先|然后|最后|接着|再|并且|同时|第\d+步)\s*", "", cleaned)
        return cleaned.strip(" \t\r\n，,。；;、：:")

    def _task_list_text(self, user_input: str) -> str:
        cues = [
            "你可以让 Agent 做这几个任务",
            "让 Agent 做这几个任务",
            "做这几个任务",
            "执行这几个任务",
            "完成这几个任务",
            "任务清单",
            "任务列表",
        ]
        for cue in cues:
            index = user_input.find(cue)
            if index >= 0:
                return user_input[index + len(cue) :]
        return user_input

import re
from typing import Any

from core.state import Plan, PlanStep, Task


class Planner:
    def create_plan(self, task: Task, matched_skill: dict[str, Any] | None = None) -> Plan:
        goals = self._goals_from_skill(matched_skill) or self._goals_for_task(task)
        return Plan(
            plan_id=f"plan_{task.task_id}",
            task_id=task.task_id,
            steps=[
                PlanStep(step_id=index, goal=goal, max_retries=self._max_retries_for_task(task.task_type))
                for index, goal in enumerate(goals, start=1)
            ],
        )

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

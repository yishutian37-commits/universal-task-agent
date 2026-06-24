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
        return [goal for goal in workflow if isinstance(goal, str) and goal.strip()]

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
        return ["执行 V0.3 mock 工具"]

from core.state import Plan, PlanStep, Task


class Planner:
    def create_plan(self, task: Task) -> Plan:
        goals = self._goals_for(task.task_type)
        return Plan(
            plan_id=f"plan_{task.task_id}",
            task_id=task.task_id,
            steps=[
                PlanStep(step_id=index, goal=goal)
                for index, goal in enumerate(goals, start=1)
            ],
        )

    def _goals_for(self, task_type: str) -> list[str]:
        if task_type == "summarize":
            return ["读取输入内容", "提取核心信息", "生成结构化报告"]
        if task_type == "data_analysis":
            return ["读取表格文件", "分析字段、行数、列数和缺失值", "生成表格分析报告"]
        return ["执行 V0.3 mock 工具"]

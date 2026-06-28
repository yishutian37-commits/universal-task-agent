import json
from datetime import datetime

import main
from core.state import Feedback, Task
from main import build_log_lines, create_initial_state, run_task
from tools.base_tool import BaseTool
from tools.history_tool import HistoryTool


VALID_SUMMARY_REPORT = "## 摘要\n库存接口已完成联调。\n## 核心观点\n流程清晰。\n## 风险点\n原文未提供明确风险。"


class FakeParser:
    def __init__(self, task_type="summarize", intent="summarize_article"):
        self.task_type = task_type
        self.intent = intent

    def parse(self, task_id, user_input):
        return Task(
            task_id=task_id,
            user_input=user_input,
            task_type=self.task_type,
            intent=self.intent,
            input_type="text",
            expected_output="summary_report",
        )


class StaticSummaryTool(BaseTool):
    name = "static_summary_tool"
    description = "test tool"

    def __init__(self, message):
        self.message = message

    def run(self, action_name, params):
        if action_name == "read":
            return {
                "message": "已读取文本内容",
                "content": "会议记录：库存接口已完成联调。",
            }
        if action_name == "process":
            return {"message": self.message, "summary_markdown": self.message}
        return {"message": self.message, "report_markdown": self.message}


class StepEchoTool(BaseTool):
    name = "step_echo_tool"
    description = "echoes each step goal for complex task tests"

    def run(self, action_name, params):
        del action_name
        goal = params.get("goal", "")
        return {"message": f"结果：{goal}", "report_markdown": f"结果：{goal}"}


class FencedMarkdownTool(BaseTool):
    name = "fenced_markdown_tool"
    description = "returns markdown wrapped in a markdown code fence"

    def run(self, action_name, params):
        del action_name, params
        return {
            "message": "```markdown\n# 文章逻辑结构分析\n\n1. 现象描述\n2. 核心原因\n```"
        }


def make_static_summary_registry(summary=VALID_SUMMARY_REPORT):
    return {
        "file_tool": StaticSummaryTool("file"),
        "text_tool": StaticSummaryTool(summary),
        "report_tool": StaticSummaryTool(summary),
    }


class FakeMemoryProvider:
    def __init__(self):
        self.saved_task_ids = []

    def save_task(self, state):
        self.saved_task_ids.append(state.task_id)

    def load_context(self):
        return {}


class FakeSkillLoader:
    def __init__(self, matched_skill):
        self.matched_skill = matched_skill
        self.seen_task_types = []

    def match(self, task):
        self.seen_task_types.append(task.task_type)
        return self.matched_skill


def test_generate_task_id_uses_microseconds_to_avoid_same_second_collisions(monkeypatch):
    class FakeDateTime:
        values = iter(
            [
                datetime(2026, 6, 22, 1, 2, 3, 123456),
                datetime(2026, 6, 22, 1, 2, 3, 123457),
            ]
        )

        @classmethod
        def now(cls):
            return next(cls.values)

    monkeypatch.setattr(main, "datetime", FakeDateTime)

    first = main.generate_task_id()
    second = main.generate_task_id()

    assert first != second
    assert first == "task_20260622_010203_123456"
    assert second == "task_20260622_010203_123457"


def test_create_initial_state_starts_unknown_before_parser():
    state = create_initial_state("task_test", "帮我分析 CSV")

    assert state.task_id == "task_test"
    assert state.task_type == "unknown"
    assert state.intent == ""


def test_run_task_writes_state_and_log(tmp_path):
    state = run_task(
        "帮我总结一段文本",
        output_root=tmp_path,
        task_id="task_test",
        task_parser=FakeParser(),
        tool_registry=make_static_summary_registry(),
        memory_provider=False,
        skill_loader=False,
    )

    state_path = tmp_path / "states" / "task_test_state.json"
    log_path = tmp_path / "logs" / "task_test.log"

    assert state.status == "completed"
    assert state.final_output == VALID_SUMMARY_REPORT
    assert state_path.exists()
    assert log_path.exists()

    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["status"] == "completed"
    assert saved["final_output"] == VALID_SUMMARY_REPORT
    assert saved["task_type"] == "summarize"
    assert saved["intent"] == "summarize_article"
    assert len(saved["plan"]["steps"]) == 3

    log_text = log_path.read_text(encoding="utf-8")
    assert "[Planner] created 3 steps" in log_text
    assert "[Router] selected tool = file_tool" in log_text


def test_run_task_emits_progress_events(tmp_path):
    events = []

    state = run_task(
        "帮我总结一段文本",
        output_root=tmp_path,
        task_id="task_test",
        task_parser=FakeParser(),
        tool_registry=make_static_summary_registry(),
        memory_provider=False,
        skill_loader=False,
        on_progress=events.append,
    )

    assert state.status == "completed"
    assert [event["task_id"] for event in events] == ["task_test"] * len(events)
    event_types = [event["type"] for event in events]
    assert event_types[:4] == [
        "task_received",
        "parsed",
        "skill_matched",
        "plan_created",
    ]
    assert "memory_saved" in event_types
    assert event_types[-1] == "task_completed"
    completed = events[-1]
    assert completed["data"]["status"] == "completed"
    assert completed["data"]["final_output"] == VALID_SUMMARY_REPORT


def test_run_task_outputs_real_summary_with_injected_tools(tmp_path):
    summary = VALID_SUMMARY_REPORT

    state = run_task(
        "帮我总结一段文本",
        output_root=tmp_path,
        task_id="task_test",
        task_parser=FakeParser(),
        tool_registry=make_static_summary_registry(summary),
        memory_provider=False,
        skill_loader=False,
    )

    assert state.status == "completed"
    assert state.final_output == summary


def test_run_task_keeps_complex_task_checklist_out_of_final_output(tmp_path):
    state = run_task(
        "帮我执行复杂任务：[1]分析当前项目状态 [2]列出下一步计划 [3]总结风险点",
        output_root=tmp_path,
        task_id="task_complex",
        task_parser=FakeParser(task_type="complex_task", intent="execute_complex_task"),
        tool_registry={
            "mock_tool": StaticSummaryTool("done"),
            "text_tool": StaticSummaryTool(VALID_SUMMARY_REPORT),
        },
        memory_provider=False,
        skill_loader=False,
    )

    assert state.status == "completed"
    assert state.final_output is not None
    assert "## 复杂任务执行清单" not in state.final_output
    assert "[x] 1. 分析当前项目状态" not in state.final_output
    assert "[x] 2. 列出下一步计划" not in state.final_output
    assert "[x] 3. 总结风险点" not in state.final_output
    assert "已完成 3/3 个步骤" not in state.final_output
    assert "## 分步结果" in state.final_output


def test_run_task_outputs_step_results_for_complex_task(tmp_path):
    state = run_task(
        "帮我执行复杂任务：[1]总结全文核心观点 [2]提炼 5 个关键结论",
        output_root=tmp_path,
        task_id="task_complex_results",
        task_parser=FakeParser(task_type="complex_task", intent="execute_complex_task"),
        tool_registry={
            "mock_tool": StepEchoTool(),
            "text_tool": StepEchoTool(),
        },
        memory_provider=False,
        skill_loader=False,
    )

    assert state.status == "completed"
    assert state.final_output is not None
    assert "## 分步结果" in state.final_output
    assert "### 1. 总结全文核心观点" in state.final_output
    assert "结果：总结全文核心观点" in state.final_output
    assert "### 2. 提炼 5 个关键结论" in state.final_output
    assert "结果：提炼 5 个关键结论" in state.final_output
    assert "## 执行结果" not in state.final_output


def test_run_task_unwraps_markdown_code_fences_in_complex_step_results(tmp_path):
    state = run_task(
        "帮我执行复杂任务：[1]找出文章的逻辑结构",
        output_root=tmp_path,
        task_id="task_complex_fence",
        task_parser=FakeParser(task_type="complex_task", intent="execute_complex_task"),
        tool_registry={
            "mock_tool": FencedMarkdownTool(),
            "text_tool": FencedMarkdownTool(),
        },
        memory_provider=False,
        skill_loader=False,
    )

    assert state.status == "completed"
    assert state.final_output is not None
    assert "```markdown" not in state.final_output
    assert "```" not in state.final_output
    assert "# 文章逻辑结构分析" in state.final_output
    assert "1. 现象描述" in state.final_output


def test_run_task_lists_previous_tasks_for_history_query(tmp_path):
    states_dir = tmp_path / "states"
    states_dir.mkdir(parents=True)
    (states_dir / "task_old_state.json").write_text(
        json.dumps(
            {
                "task_id": "task_old",
                "user_input": "帮我做 GEO 分析",
                "task_type": "geo_analysis",
                "intent": "geo_analysis",
                "status": "completed",
                "final_output": "done",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    state = run_task(
        "我之前让你进行过什么任务，给我列出来",
        output_root=tmp_path,
        task_id="task_history",
        task_parser=FakeParser(task_type="history_query", intent="list_previous_tasks"),
        tool_registry={
            "history_tool": HistoryTool(output_root=tmp_path, memory_root=tmp_path / "memory"),
        },
        memory_provider=False,
        skill_loader=False,
    )

    assert state.status == "completed"
    assert state.final_output is not None
    assert "## 历史任务" in state.final_output
    assert "帮我做 GEO 分析" in state.final_output
    assert "## 摘要" not in state.final_output


def test_run_task_writes_parser_result_to_state_and_log(tmp_path):
    state = run_task(
        "帮我分析 CSV",
        output_root=tmp_path,
        task_id="task_test",
        task_parser=FakeParser(task_type="data_analysis", intent="analyze_csv"),
        memory_provider=False,
        skill_loader=False,
    )

    state_path = tmp_path / "states" / "task_test_state.json"
    log_path = tmp_path / "logs" / "task_test.log"

    assert state.task_type == "data_analysis"
    assert state.intent == "analyze_csv"

    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["task_type"] == "data_analysis"
    assert saved["intent"] == "analyze_csv"

    log_text = log_path.read_text(encoding="utf-8")
    assert "[TaskParser] task_type = data_analysis" in log_text
    assert "[TaskParser] intent = analyze_csv" in log_text


def test_run_task_outputs_data_analysis_report(tmp_path):
    csv_path = tmp_path / "orders.csv"
    csv_path.write_text(
        "order_id,warehouse,quantity\n"
        "1,上海仓,10\n"
        "2,北京仓,\n"
        "3,上海仓,12\n",
        encoding="utf-8",
    )

    state = run_task(
        f"分析 {csv_path}",
        output_root=tmp_path,
        task_id="task_test",
        task_parser=FakeParser(task_type="data_analysis", intent="analyze_table"),
        memory_provider=False,
        skill_loader=False,
    )

    assert state.status == "completed"
    assert "## 字段说明" in state.final_output
    assert "行数：3" in state.final_output
    assert (tmp_path / "states" / "task_test_state.json").exists()


def test_run_task_saves_memory_with_injected_provider(tmp_path):
    memory_provider = FakeMemoryProvider()

    state = run_task(
        "帮我总结一段文本",
        output_root=tmp_path,
        task_id="task_test",
        task_parser=FakeParser(),
        tool_registry=make_static_summary_registry(),
        memory_provider=memory_provider,
        skill_loader=False,
    )

    saved = json.loads((tmp_path / "states" / "task_test_state.json").read_text(encoding="utf-8"))
    log_text = (tmp_path / "logs" / "task_test.log").read_text(encoding="utf-8")

    assert state.memory_saved is True
    assert memory_provider.saved_task_ids == ["task_test"]
    assert saved["memory_saved"] is True
    assert "[Memory] saved = true" in log_text


def test_run_task_can_disable_memory(tmp_path):
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

    assert state.memory_saved is False
    assert "[Memory] saved = false" in log_text


def test_run_task_uses_default_json_memory_provider(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    state = run_task(
        "帮我总结一段文本",
        output_root=tmp_path / "outputs",
        task_id="task_test",
        task_parser=FakeParser(),
        tool_registry=make_static_summary_registry(),
        skill_loader=False,
    )

    history = json.loads((tmp_path / "memory" / "task_history.json").read_text(encoding="utf-8"))

    assert state.memory_saved is True
    assert history["tasks"][0]["task_id"] == "task_test"


def test_log_lines_include_reflection_feedback():
    state = create_initial_state("task_test", "帮我总结")
    state.feedbacks.append(
        Feedback(
            failure_type="incomplete_output",
            root_cause="缺少必要小节：风险点",
            repair_strategy="补齐风险点小节",
        )
    )

    log_text = "\n".join(build_log_lines(state))

    assert "[Reflection] failure_type = incomplete_output" in log_text
    assert "[Reflection] repair_strategy = 补齐风险点小节" in log_text


def test_build_log_lines_includes_replan_events():
    state = create_initial_state("task_test", "测试")
    state.task_type = "summarize"
    state.replan_count = 1
    state.replan_events.append(
        {
            "failed_step_id": 2,
            "failed_goal": "提取核心信息",
            "resume_step_id": 2,
            "root_cause": "缺少必要小节：风险点",
        }
    )

    lines = build_log_lines(state)

    assert "[Replan] count = 1" in lines
    assert "[Replan] failed_step = 2, resume_step = 2" in lines


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


def test_run_task_outputs_research_report_with_fixture_search(tmp_path, monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDER", "fixture")

    state = run_task(
        "调研 UTA Agent 框架下一步路线",
        output_root=tmp_path,
        task_id="task_test",
        memory_provider=False,
        skill_loader=False,
    )

    state_path = tmp_path / "states" / "task_test_state.json"
    log_path = tmp_path / "logs" / "task_test.log"

    assert state.status == "completed"
    assert state.task_type == "research"
    assert "## 结论" in state.final_output
    assert "## 来源" in state.final_output
    assert state_path.exists()
    assert log_path.exists()

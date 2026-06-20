import json

from core.state import Feedback, Task
from main import build_log_lines, create_initial_state, run_task
from tools.base_tool import BaseTool


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


def make_static_summary_registry(summary=VALID_SUMMARY_REPORT):
    return {
        "file_tool": StaticSummaryTool("file"),
        "text_tool": StaticSummaryTool(summary),
        "report_tool": StaticSummaryTool(summary),
    }


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


def test_run_task_outputs_real_summary_with_injected_tools(tmp_path):
    summary = VALID_SUMMARY_REPORT

    state = run_task(
        "帮我总结一段文本",
        output_root=tmp_path,
        task_id="task_test",
        task_parser=FakeParser(),
        tool_registry=make_static_summary_registry(summary),
    )

    assert state.status == "completed"
    assert state.final_output == summary


def test_run_task_writes_parser_result_to_state_and_log(tmp_path):
    state = run_task(
        "帮我分析 CSV",
        output_root=tmp_path,
        task_id="task_test",
        task_parser=FakeParser(task_type="data_analysis", intent="analyze_csv"),
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
    )

    assert state.status == "completed"
    assert "## 字段说明" in state.final_output
    assert "行数：3" in state.final_output
    assert (tmp_path / "states" / "task_test_state.json").exists()


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

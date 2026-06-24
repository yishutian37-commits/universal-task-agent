from core.task_parser import TaskParser
from llm.llm_client import LLMClientError


class FakeClient:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error

    def chat_json(self, system_prompt, user_prompt, schema=None):
        if self.error:
            raise self.error
        return self.payload


def test_parser_returns_summarize_task():
    parser = TaskParser(
        FakeClient(
            {
                "task_type": "summarize",
                "intent": "summarize_article",
                "input_type": "text",
                "expected_output": "summary_report",
            }
        )
    )

    task = parser.parse("task_1", "帮我总结这段文本")

    assert task.task_id == "task_1"
    assert task.user_input == "帮我总结这段文本"
    assert task.task_type == "summarize"
    assert task.intent == "summarize_article"
    assert task.input_type == "text"
    assert task.expected_output == "summary_report"


def test_parser_returns_data_analysis_task():
    parser = TaskParser(
        FakeClient(
            {
                "task_type": "data_analysis",
                "intent": "analyze_csv",
                "input_type": "file",
                "expected_output": "analysis_report",
            }
        )
    )

    task = parser.parse("task_1", "帮我分析 CSV")

    assert task.task_type == "data_analysis"
    assert task.intent == "analyze_csv"


def test_parser_normalizes_unknown_task_type():
    parser = TaskParser(FakeClient({"task_type": "bogus_type"}))

    task = parser.parse("task_1", "帮我调研")

    assert task.task_type == "unknown"
    assert task.intent == "unknown"


def test_parser_falls_back_when_llm_fails():
    parser = TaskParser(FakeClient(error=LLMClientError("boom")))

    task = parser.parse("task_1", "随便做点什么")

    assert task.task_type == "unknown"
    assert task.intent == "parse_failed"
    assert task.input_type == "unknown"
    assert task.expected_output == "unknown"
    assert task.missing_info == ["task_type"]


def test_parser_fallback_detects_csv_data_analysis_when_llm_fails():
    parser = TaskParser(FakeClient(error=LLMClientError("boom")))

    task = parser.parse("task_1", "分析 examples/orders.csv")

    assert task.task_type == "data_analysis"
    assert task.intent == "analyze_table"
    assert task.input_type == "file"
    assert task.expected_output == "analysis_report"
    assert task.missing_info == []


def test_parser_fills_missing_fields():
    parser = TaskParser(FakeClient({"task_type": "summarize"}))

    task = parser.parse("task_1", "帮我总结")

    assert task.intent == "summarize"
    assert task.input_type == "unknown"
    assert task.expected_output == "unknown"
    assert task.constraints == []
    assert task.missing_info == []


def test_parser_normalizes_non_list_fields():
    parser = TaskParser(
        FakeClient(
            {
                "task_type": "summarize",
                "constraints": "short",
                "missing_info": "file",
            }
        )
    )

    task = parser.parse("task_1", "帮我总结")

    assert task.constraints == []
    assert task.missing_info == []


class FailingLLMClient:
    def chat_json(self, system_prompt, user_prompt, schema=None):
        raise RuntimeError("LLM unavailable")


def test_task_parser_fallback_detects_research_when_llm_fails():
    parser = TaskParser(llm_client=FailingLLMClient())

    task = parser.parse("task_test", "请帮我调研 UTA Agent 框架下一步路线")

    assert task.task_type == "research"
    assert task.intent == "research_topic"
    assert task.input_type == "text"
    assert task.expected_output == "research_report"


def test_task_parser_fallback_detects_weather_research_when_llm_fails():
    parser = TaskParser(llm_client=FailingLLMClient())

    task = parser.parse("task_test", "包头今日天气状况")

    assert task.task_type == "research"
    assert task.intent == "research_topic"
    assert task.input_type == "text"
    assert task.expected_output == "research_report"


def test_task_parser_fallback_detects_code_reading_when_llm_fails():
    parser = TaskParser(llm_client=FailingLLMClient())

    task = parser.parse("task_test", "阅读 UTA 代码，说明一次任务从输入到输出怎么跑")

    assert task.task_type == "code_reading"
    assert task.intent == "read_task_flow"
    assert task.input_type == "repository"
    assert task.expected_output == "code_reading_report"


def test_task_parser_system_prompt_allows_code_reading():
    assert "code_reading" in TaskParser._system_prompt()

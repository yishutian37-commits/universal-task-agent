from core.task_parser import TaskParser
from llm.llm_client import LLMClientError
import pytest


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


def test_parser_dangerous_tool_detection_uses_current_input_not_conversation_history():
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
    contextual_input = "\n\n".join(
        [
            "以下是同一对话前文。\n- 用户：帮我在桌面创建一个叫一个的文件夹",
            "当前用户输入：\n帮我总结这段文本",
        ]
    )

    task = parser.parse("task_current", contextual_input)

    assert task.task_type == "summarize"
    assert task.user_input == "帮我总结这段文本"


@pytest.mark.parametrize("user_input", ["当前工作区有哪些文件", "读取 README.md 的内容"])
def test_parser_routes_workspace_file_requests_to_tool_task(user_input):
    parser = TaskParser(FakeClient(error=LLMClientError("offline")))

    task = parser.parse("task_workspace", user_input)

    assert task.task_type == "langchain_tool"


def test_parser_routes_workspace_folder_summary_to_summary_flow():
    parser = TaskParser(FakeClient(error=LLMClientError("offline")))

    task = parser.parse(
        "task_workspace_summary",
        "读取下这个文件夹的内容，总结一下这是在干什么，不要修改",
    )

    assert task.task_type == "summarize"
    assert task.intent == "summarize_workspace"
    assert task.input_type == "directory"


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


def test_parser_returns_history_query_task():
    parser = TaskParser(
        FakeClient(
            {
                "task_type": "history_query",
                "intent": "list_previous_tasks",
                "input_type": "memory",
                "expected_output": "history_task_list",
            }
        )
    )

    task = parser.parse("task_1", "我之前让你进行过什么任务，给我列出来")

    assert task.task_type == "history_query"
    assert task.intent == "list_previous_tasks"
    assert task.input_type == "memory"
    assert task.expected_output == "history_task_list"


def test_parser_overrides_llm_summary_for_obvious_history_query():
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

    task = parser.parse("task_1", "我之前让你进行过什么任务，给我列出来")

    assert task.task_type == "history_query"
    assert task.intent == "list_previous_tasks"
    assert task.input_type == "memory"
    assert task.expected_output == "history_task_list"


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


def test_task_parser_fallback_detects_geo_analysis_when_llm_fails():
    parser = TaskParser(llm_client=FailingLLMClient())

    task = parser.parse("task_test", "帮我做 GEO 分析，生成问题矩阵和平台合规检查")

    assert task.task_type == "geo_analysis"
    assert task.intent == "geo_analysis"
    assert task.input_type == "text"
    assert task.expected_output == "geo_report"


def test_task_parser_system_prompt_allows_geo_analysis():
    assert "geo_analysis" in TaskParser._system_prompt()


def test_task_parser_fallback_detects_langchain_tool_task_when_llm_fails():
    parser = TaskParser(llm_client=FailingLLMClient())

    task = parser.parse("task_test", "用 LangChain 工具回显 hello")

    assert task.task_type == "langchain_tool"
    assert task.intent == "invoke_langchain_tool"
    assert task.input_type == "text"
    assert task.expected_output == "tool_result"


def test_parser_overrides_llm_unknown_for_obvious_langchain_tool_task():
    parser = TaskParser(
        FakeClient(
            {
                "task_type": "unknown",
                "intent": "unknown",
                "input_type": "unknown",
                "expected_output": "unknown",
            }
        )
    )

    task = parser.parse("task_test", "用 LangChain 工具回显 hello")

    assert task.task_type == "langchain_tool"
    assert task.intent == "invoke_langchain_tool"


@pytest.mark.parametrize(
    "user_input",
    [
        "计算 2 + 3 * 4",
        "现在几点",
        "格式化 JSON：{\"a\": 1}",
        "HTTP GET https://example.com",
        "用 LangChain 工具搜索 UTA Agent",
        "用 LangChain 天气工具查询包头天气",
        "执行 shell 命令 echo hello",
        "写入文件 /tmp/uta-note.txt 内容 hello",
        "运行 Python 代码 result = 1 + 2",
        "删除文件 /tmp/uta-note.txt",
        "删除本地文件 /tmp/uta-note.txt",
        "帮我在桌面创建一个名叫测试的文件夹",
    ],
)
def test_task_parser_fallback_detects_common_langchain_tool_tasks_when_llm_fails(user_input):
    parser = TaskParser(llm_client=FailingLLMClient())

    task = parser.parse("task_test", user_input)

    assert task.task_type == "langchain_tool"
    assert task.intent == "invoke_langchain_tool"


def test_task_parser_fallback_detects_history_query_when_llm_fails():
    parser = TaskParser(llm_client=FailingLLMClient())

    task = parser.parse("task_test", "我之前让你进行过什么任务，给我列出来")

    assert task.task_type == "history_query"
    assert task.intent == "list_previous_tasks"
    assert task.input_type == "memory"
    assert task.expected_output == "history_task_list"


def test_task_parser_system_prompt_allows_history_query():
    assert "history_query" in TaskParser._system_prompt()


def test_task_parser_fallback_detects_complex_task_when_user_requests_steps():
    parser = TaskParser(llm_client=FailingLLMClient())

    task = parser.parse("task_test", "请分步骤执行：先分析项目，然后列出计划，最后总结风险")

    assert task.task_type == "complex_task"
    assert task.intent == "execute_complex_task"
    assert task.input_type == "text"
    assert task.expected_output == "step_checklist"


def test_task_parser_fallback_detects_complex_task_with_numbered_steps():
    parser = TaskParser(llm_client=FailingLLMClient())

    task = parser.parse("task_test", "帮我执行复杂任务：[1]分析项目 [2]列出计划 [3]总结风险")

    assert task.task_type == "complex_task"
    assert task.intent == "execute_complex_task"
    assert task.input_type == "text"
    assert task.expected_output == "step_checklist"


def test_task_parser_overrides_summary_when_input_contains_agent_task_list():
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

    task = parser.parse(
        "task_test",
        "帮我总结一段文本：这里是一篇文章。\n\n"
        "你可以让 Agent 做这几个任务：\n"
        "1. 总结全文核心观点\n"
        "2. 提炼 5 个关键结论\n"
        "3. 找出文章的逻辑结构",
    )

    assert task.task_type == "complex_task"
    assert task.intent == "execute_complex_task"
    assert task.expected_output == "step_checklist"


def test_task_parser_prefers_agent_task_list_over_article_code_keywords():
    parser = TaskParser(llm_client=FailingLLMClient())

    task = parser.parse(
        "task_test",
        "帮我总结一段文本：文章讨论代码阅读能力、调用链理解能力和 Debug 能力。\n\n"
        "你可以让 Agent 做这几个任务：\n"
        "1. 总结全文核心观点\n"
        "2. 提炼 5 个关键结论\n"
        "3. 改写成适合小白看的版本",
    )

    assert task.task_type == "complex_task"
    assert task.intent == "execute_complex_task"


def test_task_parser_system_prompt_allows_complex_task():
    assert "complex_task" in TaskParser._system_prompt()

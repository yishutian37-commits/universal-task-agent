import json
from datetime import datetime
from pathlib import Path

import main
from core.state import AgentState, Plan, PlanStep, Task, ToolResult
from main import create_initial_state, run_task
from tools.base_tool import BaseTool
from tools.authorization import AuthorizationDecision
from tools.langchain_adapter import LangChainToolAdapter
from tools.langchain_common_tools import DirectoryCreateLangChainTool, FileDeleteLangChainTool, PythonReplLangChainTool
from tools.history_tool import HistoryTool
from tools.registry import build_tool_registry


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


class CapturingMemoryProvider:
    def __init__(self):
        self.saved_user_inputs = []

    def save_task(self, state):
        self.saved_user_inputs.append(state.user_input)

    def load_context(self):
        return {}


class CapturingCheckpointStore:
    def __init__(self, loaded_state=None):
        self.loaded_state = loaded_state
        self.saved_states = []
        self.loaded_task_ids = []

    def save(self, state):
        self.saved_states.append(state.to_dict())

    def load(self, task_id):
        self.loaded_task_ids.append(task_id)
        return self.loaded_state


class CapturingParser:
    def __init__(self):
        self.seen_user_inputs = []

    def parse(self, task_id, user_input):
        self.seen_user_inputs.append(user_input)
        return Task(
            task_id=task_id,
            user_input=user_input,
            task_type="summarize",
            intent="contextual_task",
            input_type="text",
            expected_output="summary_report",
        )


class CapturingTool(BaseTool):
    name = "capturing_tool"
    description = "captures user_input"

    def __init__(self):
        self.seen_user_inputs = []

    def run(self, action_name, params):
        self.seen_user_inputs.append(params.get("user_input"))
        if action_name == "read":
            return {"message": "已读取文本内容", "content": "会议记录：库存接口已完成联调。"}
        return {"message": VALID_SUMMARY_REPORT, "summary_markdown": VALID_SUMMARY_REPORT, "report_markdown": VALID_SUMMARY_REPORT}


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


def test_run_task_separates_saved_user_input_from_contextual_execution_input():
    raw_input = "帮我总结刚才提到的项目"
    contextual_input = "以下是同一对话前文：项目叫 UTA。\n\n当前用户输入：\n帮我总结刚才提到的项目"
    parser = CapturingParser()
    tool = CapturingTool()
    memory_provider = CapturingMemoryProvider()

    state = run_task(
        contextual_input,
        task_id="task_context",
        display_user_input=raw_input,
        task_parser=parser,
        tool_registry={"file_tool": tool, "text_tool": tool, "report_tool": tool},
        memory_provider=memory_provider,
        skill_loader=False,
    )

    assert state.user_input == raw_input
    assert state.execution_input == contextual_input
    assert parser.seen_user_inputs == [contextual_input]
    assert tool.seen_user_inputs == [contextual_input, contextual_input, contextual_input]
    assert memory_provider.saved_user_inputs == [raw_input]


def test_run_task_saves_checkpoints_during_execution():
    checkpoint_store = CapturingCheckpointStore()

    state = run_task(
        "帮我总结一段文本",
        task_id="task_checkpoint",
        task_parser=FakeParser(),
        tool_registry=make_static_summary_registry(),
        memory_provider=False,
        skill_loader=False,
        checkpoint_store=checkpoint_store,
    )

    assert state.status == "completed"
    assert checkpoint_store.saved_states
    assert checkpoint_store.saved_states[0]["task_id"] == "task_checkpoint"
    assert checkpoint_store.saved_states[-1]["status"] == "completed"
    assert checkpoint_store.saved_states[-1]["final_output"] == VALID_SUMMARY_REPORT


def test_run_task_executes_safe_langchain_tool_demo():
    state = run_task(
        "用 LangChain 工具回显 hello",
        task_id="task_langchain_demo",
        task_parser=FakeParser(task_type="langchain_tool", intent="invoke_langchain_tool"),
        memory_provider=False,
        skill_loader=False,
    )

    assert state.status == "completed"
    assert state.results[-1].tool_name == "langchain_echo_tool"
    assert state.results[-1].result["output"] == {"echo": {"query": "用 LangChain 工具回显 hello"}}
    assert "hello" in state.final_output


def test_run_task_executes_safe_langchain_calculator_tool():
    state = run_task(
        "计算 2 + 3 * 4",
        task_id="task_langchain_calculator",
        task_parser=FakeParser(task_type="langchain_tool", intent="invoke_langchain_tool"),
        memory_provider=False,
        skill_loader=False,
    )

    assert state.status == "completed"
    assert state.results[-1].tool_name == "langchain_calculator_tool"
    assert state.results[-1].result["output"]["result"] == 14
    assert "14" in state.final_output


class ApprovingAuthorizationManager:
    def __init__(self):
        self.requests = []

    def request(self, operation, timeout=None):
        self.requests.append((operation, timeout))
        return AuthorizationDecision(
            request_id="auth_test",
            approved=True,
            status="approved",
            approved_by="tester",
        )


def test_run_task_executes_authorized_file_write_tool(tmp_path):
    target = tmp_path / "note.txt"
    auth = ApprovingAuthorizationManager()

    state = run_task(
        f"写入文件 {target} 内容 hello",
        task_id="task_authorized_file_write",
        task_parser=FakeParser(task_type="langchain_tool", intent="invoke_langchain_tool"),
        tool_registry=build_tool_registry(
            enable_dangerous_tools=True,
            authorization_manager=auth,
            dangerous_allowed_roots=[tmp_path],
        ),
        memory_provider=False,
        skill_loader=False,
    )

    assert state.status == "completed"
    assert state.results[-1].tool_name == "langchain_file_write_tool"
    assert target.read_text(encoding="utf-8") == "hello"
    assert auth.requests[0][0]["tool_name"] == "langchain_file_write_tool"


def test_run_task_executes_authorized_directory_create_tool(tmp_path):
    auth = ApprovingAuthorizationManager()

    state = run_task(
        "帮我在桌面创建一个名叫测试的文件夹",
        task_id="task_authorized_directory_create",
        task_parser=FakeParser(task_type="langchain_tool", intent="invoke_langchain_tool"),
        tool_registry={
            "langchain_directory_create_tool": LangChainToolAdapter(
                DirectoryCreateLangChainTool(
                    authorization_manager=auth,
                    enabled=True,
                    allowed_roots=[tmp_path],
                    desktop_root=tmp_path,
                )
            )
        },
        memory_provider=False,
        skill_loader=False,
    )

    assert state.status == "completed"
    assert state.results[-1].tool_name == "langchain_directory_create_tool"
    assert (tmp_path / "测试").is_dir()
    assert auth.requests[0][0]["tool_name"] == "langchain_directory_create_tool"


def test_run_task_dangerous_tool_uses_display_input_instead_of_conversation_history(tmp_path):
    auth = ApprovingAuthorizationManager()
    current_input = "帮我在桌面创建一个叫测试的文件夹"
    execution_input = "前文：帮我在桌面创建一个叫一个的文件夹\n\n当前用户输入：\n" + current_input

    state = run_task(
        execution_input,
        display_user_input=current_input,
        task_id="task_current_input_parser",
        task_parser=FakeParser(task_type="langchain_tool", intent="invoke_langchain_tool"),
        tool_registry={
            "langchain_directory_create_tool": LangChainToolAdapter(
                DirectoryCreateLangChainTool(
                    authorization_manager=auth,
                    enabled=True,
                    allowed_roots=[tmp_path],
                    desktop_root=tmp_path,
                )
            )
        },
        memory_provider=False,
        skill_loader=False,
    )

    assert state.status == "completed"
    assert (tmp_path / "测试").is_dir()
    assert not (tmp_path / "一个").exists()


def test_run_task_executes_authorized_python_repl_tool(tmp_path):
    auth = ApprovingAuthorizationManager()

    state = run_task(
        "运行 Python 代码 result = 1 + 2",
        task_id="task_authorized_python_repl",
        task_parser=FakeParser(task_type="langchain_tool", intent="invoke_langchain_tool"),
        tool_registry={
            "langchain_python_repl_tool": LangChainToolAdapter(
                PythonReplLangChainTool(
                    authorization_manager=auth,
                    enabled=True,
                    allowed_roots=[tmp_path],
                )
            )
        },
        memory_provider=False,
        skill_loader=False,
    )

    assert state.status == "completed"
    assert state.results[-1].tool_name == "langchain_python_repl_tool"
    assert state.results[-1].result["output"]["result_repr"] == "3"
    assert auth.requests[0][0]["tool_name"] == "langchain_python_repl_tool"


def test_run_task_executes_authorized_file_delete_tool(tmp_path):
    target = tmp_path / "old.txt"
    target.write_text("old", encoding="utf-8")
    trash = tmp_path / "trash"
    auth = ApprovingAuthorizationManager()

    state = run_task(
        f"删除文件 {target}",
        task_id="task_authorized_file_delete",
        task_parser=FakeParser(task_type="langchain_tool", intent="invoke_langchain_tool"),
        tool_registry={
            "langchain_file_delete_tool": LangChainToolAdapter(
                FileDeleteLangChainTool(
                    authorization_manager=auth,
                    enabled=True,
                    allowed_roots=[tmp_path],
                    trash_root=trash,
                )
            )
        },
        memory_provider=False,
        skill_loader=False,
    )

    assert state.status == "completed"
    assert state.results[-1].tool_name == "langchain_file_delete_tool"
    assert not target.exists()
    assert Path(state.results[-1].result["output"]["trash_path"]).read_text(encoding="utf-8") == "old"
    assert auth.requests[0][0]["tool_name"] == "langchain_file_delete_tool"


def test_run_task_resumes_from_checkpoint_without_reparsing():
    parser = CapturingParser()
    loaded_state = AgentState(
        task_id="task_resume",
        user_input="帮我总结",
        task_type="summarize",
        intent="summarize_article",
        status="running",
        current_step_id=2,
    )
    loaded_state.plan = Plan(
        plan_id="plan_task_resume",
        task_id="task_resume",
        steps=[
            PlanStep(step_id=1, goal="读取输入内容", status="completed"),
            PlanStep(step_id=2, goal="提取核心信息", status="running"),
            PlanStep(step_id=3, goal="生成结构化报告", status="pending"),
        ],
        status="running",
    )
    loaded_state.results.append(
        ToolResult(
            success=True,
            tool_name="file_tool",
            action_name="read",
            result={"message": "file"},
            step_id=1,
        )
    )
    checkpoint_store = CapturingCheckpointStore(loaded_state=loaded_state)

    state = run_task(
        "不会使用这个输入",
        task_id="task_resume",
        task_parser=parser,
        tool_registry=make_static_summary_registry(),
        memory_provider=False,
        skill_loader=False,
        checkpoint_store=checkpoint_store,
        resume_from_checkpoint=True,
    )

    assert state.status == "completed"
    assert parser.seen_user_inputs == []
    assert checkpoint_store.loaded_task_ids == ["task_resume"]
    assert state.results[0].tool_name == "file_tool"


def test_create_initial_state_starts_unknown_before_parser():
    state = create_initial_state(
        "task_test",
        "帮我分析 CSV",
        conversation_id="conv_20260708_120000_000001",
        workspace_path="/tmp/workspace",
    )

    assert state.task_id == "task_test"
    assert state.task_type == "unknown"
    assert state.intent == ""
    assert state.conversation_id == "conv_20260708_120000_000001"
    assert state.workspace_path == "/tmp/workspace"


def test_run_task_completes_with_summary():
    state = run_task(
        "帮我总结一段文本",
        task_id="task_test",
        task_parser=FakeParser(),
        tool_registry=make_static_summary_registry(),
        memory_provider=False,
        skill_loader=False,
    )

    assert state.status == "completed"
    assert state.final_output == VALID_SUMMARY_REPORT
    assert state.task_type == "summarize"
    assert state.intent == "summarize_article"
    assert len(state.plan.steps) == 3


def test_run_task_emits_progress_events():
    events = []

    state = run_task(
        "帮我总结一段文本",
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


def test_run_task_outputs_real_summary_with_injected_tools():
    summary = VALID_SUMMARY_REPORT

    state = run_task(
        "帮我总结一段文本",
        task_id="task_test",
        task_parser=FakeParser(),
        tool_registry=make_static_summary_registry(summary),
        memory_provider=False,
        skill_loader=False,
    )

    assert state.status == "completed"
    assert state.final_output == summary


def test_run_task_keeps_complex_task_checklist_out_of_final_output():
    state = run_task(
        "帮我执行复杂任务：[1]分析当前项目状态 [2]列出下一步计划 [3]总结风险点",
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


def test_run_task_outputs_step_results_for_complex_task():
    state = run_task(
        "帮我执行复杂任务：[1]总结全文核心观点 [2]提炼 5 个关键结论",
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


def test_run_task_unwraps_markdown_code_fences_in_complex_step_results():
    state = run_task(
        "帮我执行复杂任务：[1]找出文章的逻辑结构",
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
    memory_root = tmp_path / "memory"
    memory_root.mkdir(parents=True)
    (memory_root / "task_history.json").write_text(
        json.dumps(
            {
                "version": 1,
                "tasks": [
                    {
                        "task_id": "task_old",
                        "user_input": "帮我做 GEO 分析",
                        "task_type": "geo_analysis",
                        "intent": "geo_analysis",
                        "status": "completed",
                        "final_output": "done",
                        "final_output_preview": "done",
                        "updated_at": "2026-06-25 08:00:00",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    state = run_task(
        "我之前让你进行过什么任务，给我列出来",
        task_id="task_history",
        task_parser=FakeParser(task_type="history_query", intent="list_previous_tasks"),
        tool_registry={
            "history_tool": HistoryTool(memory_root=memory_root),
        },
        memory_provider=False,
        skill_loader=False,
    )

    assert state.status == "completed"
    assert state.final_output is not None
    assert "## 历史任务" in state.final_output
    assert "帮我做 GEO 分析" in state.final_output
    assert "## 摘要" not in state.final_output


def test_run_task_carries_parser_result_into_state():
    state = run_task(
        "帮我分析 CSV",
        task_id="task_test",
        task_parser=FakeParser(task_type="data_analysis", intent="analyze_csv"),
        memory_provider=False,
        skill_loader=False,
    )

    assert state.task_type == "data_analysis"
    assert state.intent == "analyze_csv"


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
        task_id="task_test",
        task_parser=FakeParser(task_type="data_analysis", intent="analyze_table"),
        memory_provider=False,
        skill_loader=False,
    )

    assert state.status == "completed"
    assert "## 字段说明" in state.final_output
    assert "行数：3" in state.final_output


def test_run_task_saves_memory_with_injected_provider():
    memory_provider = FakeMemoryProvider()

    state = run_task(
        "帮我总结一段文本",
        task_id="task_test",
        task_parser=FakeParser(),
        tool_registry=make_static_summary_registry(),
        memory_provider=memory_provider,
        skill_loader=False,
    )

    assert state.memory_saved is True
    assert memory_provider.saved_task_ids == ["task_test"]


def test_run_task_can_disable_memory():
    state = run_task(
        "帮我总结一段文本",
        task_id="task_test",
        task_parser=FakeParser(),
        tool_registry=make_static_summary_registry(),
        memory_provider=False,
        skill_loader=False,
    )

    assert state.memory_saved is False


def test_run_task_uses_default_json_memory_provider(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    state = run_task(
        "帮我总结一段文本",
        task_id="task_test",
        task_parser=FakeParser(),
        tool_registry=make_static_summary_registry(),
        skill_loader=False,
    )

    history = json.loads((tmp_path / "memory" / "task_history.json").read_text(encoding="utf-8"))

    assert state.memory_saved is True
    assert history["tasks"][0]["task_id"] == "task_test"


def test_default_memory_stores_full_final_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    state = run_task(
        "帮我总结一段文本",
        task_id="task_test",
        task_parser=FakeParser(),
        tool_registry=make_static_summary_registry(),
        skill_loader=False,
    )

    history = json.loads((tmp_path / "memory" / "task_history.json").read_text(encoding="utf-8"))
    record = history["tasks"][0]

    assert record["final_output"] == state.final_output
    assert record["final_output_preview"]


def test_run_task_saves_matched_skill_with_injected_loader():
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
        task_id="task_test",
        task_parser=FakeParser(),
        tool_registry=make_static_summary_registry(),
        memory_provider=False,
        skill_loader=skill_loader,
    )

    assert skill_loader.seen_task_types == ["summarize"]
    assert state.matched_skill["id"] == "summarize_article"


def test_run_task_can_disable_skill_loader():
    state = run_task(
        "帮我总结一段文本",
        task_id="task_test",
        task_parser=FakeParser(),
        tool_registry=make_static_summary_registry(),
        memory_provider=False,
        skill_loader=False,
    )

    assert state.matched_skill is None


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
        task_id="task_test",
        task_parser=FakeParser(),
        tool_registry=make_static_summary_registry(),
        memory_provider=False,
    )

    assert state.matched_skill["id"] == "summarize_article"
    assert [step.goal for step in state.plan.steps] == ["读取输入内容", "提取核心信息", "生成结构化报告"]


def test_run_task_outputs_research_report_with_fixture_search(tmp_path, monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDER", "fixture")
    monkeypatch.chdir(tmp_path)

    state = run_task(
        "调研 UTA Agent 框架下一步路线",
        task_id="task_test",
        memory_provider=False,
        skill_loader=False,
    )

    assert state.status == "completed"
    assert state.task_type == "research"
    assert "## 结论" in state.final_output
    assert "## 来源" in state.final_output

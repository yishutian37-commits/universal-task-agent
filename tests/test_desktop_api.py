import json
from datetime import datetime

import desktop.runner as runner_module
from desktop.api import DesktopAPI, _build_conversation_context
from desktop.conversation_store import ConversationStore
from desktop.memory_store import MemoryStore
from desktop.settings_store import SettingsStore


class FakeRunner:
    def __init__(self):
        self.window = None
        self.started_inputs = []
        self.started_display_inputs = []
        self.started_contexts = []
        self.cancelled_task_ids = []
        self.authorization_manager = FakeAuthorizationManager()

    def bind_window(self, window):
        self.window = window

    def start(
        self,
        user_input,
        *,
        display_user_input=None,
        conversation_id=None,
        workspace_path=None,
    ):
        self.started_inputs.append(user_input)
        self.started_display_inputs.append(display_user_input)
        self.started_contexts.append(
            {"conversation_id": conversation_id, "workspace_path": workspace_path}
        )
        return "task_fake"

    def get_result(self, task_id):
        return {"status": "completed", "task_id": task_id, "final_output": "done"}

    def cancel(self, task_id):
        self.cancelled_task_ids.append(task_id)
        return {"ok": False, "error": "当前版本暂不支持取消"}

    def resume(self, task_id):
        return {"ok": True, "task_id": task_id, "status": "running"}


class FakeAuthorizationManager:
    def __init__(self):
        self.approved = []
        self.rejected = []

    def approve(self, request_id, approved_by="user"):
        self.approved.append((request_id, approved_by))
        return {"ok": True, "request_id": request_id, "status": "approved"}

    def reject(self, request_id, reason=""):
        self.rejected.append((request_id, reason))
        return {"ok": True, "request_id": request_id, "status": "rejected"}


class FakeDialogWindow:
    def __init__(self, selected_paths=None):
        self.selected_paths = selected_paths
        self.calls = []

    def create_file_dialog(self, dialog_type, **kwargs):
        self.calls.append((dialog_type, kwargs))
        return self.selected_paths


class FakeEventWindow:
    def __init__(self):
        self.scripts = []

    def evaluate_js(self, script):
        self.scripts.append(script)


class FakeHistoryStore:
    def __init__(self):
        self.listed = False
        self.requested_task_ids = []

    def list_runs(self):
        self.listed = True
        return {
            "ok": True,
            "runs": [
                {
                    "task_id": "task_fake",
                    "status": "completed",
                    "task_type": "summarize",
                    "intent": "总结",
                    "updated_at": "2026-06-21T01:00:00",
                    "modified_at": "2026-06-21T01:00:00+00:00",
                    "preview": "done",
                }
            ],
        }

    def get_run(self, task_id):
        self.requested_task_ids.append(task_id)
        if task_id == "task_fake":
            return {
                "ok": True,
                "task_id": task_id,
                "state": {"task_id": task_id, "status": "completed"},
                "final_output": "done",
            }
        return {"ok": False, "error": "任务不存在"}


class FakeMemoryStore:
    def __init__(self):
        self.called = False
        self.merged_candidates = []
        self.merge_conversation_id = None

    def overview(self):
        self.called = True
        return {
            "ok": True,
            "task_history": [],
            "lessons": [],
            "negative_rules": [],
            "skill_candidates": [],
            "user_profile": {},
            "counts": {
                "tasks": 0,
                "lessons": 0,
                "negative_rules": 0,
                "skill_candidates": 0,
            },
        }

    def merge_long_term_candidates(self, candidates, *, conversation_id, now=None):
        self.merged_candidates.extend(candidates)
        self.merge_conversation_id = conversation_id
        return {"ok": True, "long_term_memory": {"version": 1, "facts": self.merged_candidates}}


class FakeChatClient:
    def __init__(self, response="我的建议是先从一个小项目开始。"):
        self.calls = []
        self.response = response

    def chat(self, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        if isinstance(self.response, list):
            return self.response.pop(0)
        return self.response


class FakeStructuredChatClient:
    def __init__(self, route_payload, chat_response="不应再次调用普通聊天"):
        self.route_payload = route_payload
        self.chat_response = chat_response
        self.structured_calls = []
        self.chat_calls = []

    def chat_json(self, system_prompt, user_prompt, schema=None):
        self.structured_calls.append((system_prompt, user_prompt, schema))
        return dict(self.route_payload)

    def chat(self, system_prompt, user_prompt):
        self.chat_calls.append((system_prompt, user_prompt))
        return self.chat_response


class FakeStreamingStructuredChatClient(FakeStructuredChatClient):
    def __init__(self, route_payload, chunks):
        super().__init__(route_payload)
        self.chunks = list(chunks)
        self.stream_calls = []

    def chat_stream(self, system_prompt, user_prompt):
        self.stream_calls.append((system_prompt, user_prompt))
        yield from self.chunks


def test_desktop_runner_generate_task_id_uses_microseconds_to_avoid_same_second_collisions(monkeypatch):
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

    monkeypatch.setattr(runner_module, "datetime", FakeDateTime)

    first = runner_module._generate_task_id()
    second = runner_module._generate_task_id()

    assert first != second
    assert first == "task_20260622_010203_123456"
    assert second == "task_20260622_010203_123457"


def test_desktop_runner_registers_code_tool():
    registry = runner_module.build_tool_registry()

    assert "code_tool" in registry


def test_desktop_runner_registers_geo_tool():
    registry = runner_module.build_tool_registry()

    assert "geo_tool" in registry


def test_desktop_runner_registers_history_tool():
    registry = runner_module.build_tool_registry()

    assert "history_tool" in registry


def test_desktop_api_saves_settings_and_hides_key(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    api = DesktopAPI(settings_store=SettingsStore(), runner=FakeRunner())

    result = api.save_settings(
        {
            "llm_base_url": "https://token-plan-cn.xiaomimimo.com/v1/chat/completions",
            "llm_model": "mimo-v2.5-pro",
            "llm_api_key": "secret-key",
            "llm_ssl_verify": False,
        }
    )

    assert result == {"ok": True}
    settings = api.get_settings()
    assert settings["has_api_key"] is True
    assert settings["llm_model"] == "mimo-v2.5-pro"
    assert "llm_api_key" not in settings


def test_desktop_api_loads_summary_example(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    api = DesktopAPI(settings_store=SettingsStore(), runner=FakeRunner())

    example = api.load_example("summarize")

    assert example["ok"] is True
    assert "总结" in example["input"]
    assert example["title"] == "文本总结示例"


def test_desktop_api_refuses_task_without_key(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    api = DesktopAPI(settings_store=SettingsStore(), runner=runner)

    result = api.run_task("帮我总结一段文本")

    assert result["ok"] is False
    assert "Key" in result["error"]
    assert runner.started_inputs == []


def test_desktop_api_starts_runner_when_key_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    api = DesktopAPI(settings_store=SettingsStore(), runner=runner)
    api.save_settings({"llm_api_key": "secret-key", "workspace_path": str(tmp_path)})

    result = api.run_task("帮我总结一段文本")

    assert result == {"ok": True, "task_id": "task_fake"}
    assert runner.started_inputs == ["帮我总结一段文本"]


def test_desktop_api_refuses_dangerous_task_when_tools_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    api = DesktopAPI(settings_store=SettingsStore(), runner=runner)
    api.save_settings({"llm_api_key": "secret-key"})

    result = api.run_task("写入文件 /tmp/uta-note.txt 内容 hello")

    assert result["ok"] is False
    assert result["reason"] == "dangerous_tools_disabled"
    assert result["open_settings"] is True
    assert "工具授权" in result["error"]
    assert runner.started_inputs == []


def test_desktop_api_starts_dangerous_task_when_tools_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    api = DesktopAPI(settings_store=SettingsStore(), runner=runner)
    api.save_settings(
        {
            "llm_api_key": "secret-key",
            "dangerous_tools_enabled": True,
            "workspace_path": str(tmp_path),
        }
    )

    result = api.run_task("写入文件 /tmp/uta-note.txt 内容 hello")

    assert result == {"ok": True, "task_id": "task_fake"}
    assert runner.started_inputs == ["写入文件 /tmp/uta-note.txt 内容 hello"]


def test_desktop_api_requires_desktop_access_for_desktop_directory_task(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    api = DesktopAPI(settings_store=SettingsStore(), runner=runner)
    api.save_settings({"llm_api_key": "secret-key", "dangerous_tools_enabled": True})

    result = api.run_task("帮我在桌面创建一个名叫测试的文件夹")

    assert result["ok"] is False
    assert result["reason"] == "desktop_access_disabled"
    assert result["open_settings"] is True
    assert runner.started_inputs == []


def test_desktop_api_starts_desktop_directory_task_when_access_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    api = DesktopAPI(settings_store=SettingsStore(), runner=runner)
    api.save_settings(
        {
            "llm_api_key": "secret-key",
            "dangerous_tools_enabled": True,
            "desktop_access_enabled": True,
            "workspace_path": str(tmp_path),
        }
    )

    result = api.run_task("帮我在桌面创建一个名叫测试的文件夹")

    assert result == {"ok": True, "task_id": "task_fake"}
    assert runner.started_inputs == ["帮我在桌面创建一个名叫测试的文件夹"]


def test_desktop_api_exposes_result_and_cancel(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    api = DesktopAPI(settings_store=SettingsStore(), runner=runner)

    assert api.get_result("task_fake")["final_output"] == "done"
    assert api.cancel_task("task_fake")["ok"] is False
    assert runner.cancelled_task_ids == ["task_fake"]


def test_desktop_api_authorizes_and_rejects_operations(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    api = DesktopAPI(settings_store=SettingsStore(), runner=runner)

    approved = api.authorize_operation("auth_1")
    rejected = api.reject_authorization("auth_2", "不允许")

    assert approved == {"ok": True, "request_id": "auth_1", "status": "approved"}
    assert rejected == {"ok": True, "request_id": "auth_2", "status": "rejected"}
    assert runner.authorization_manager.approved == [("auth_1", "user")]
    assert runner.authorization_manager.rejected == [("auth_2", "不允许")]


def test_desktop_api_resumes_task_from_checkpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    api = DesktopAPI(settings_store=SettingsStore(), runner=runner)

    result = api.resume_task("task_resume")

    assert result == {"ok": True, "task_id": "task_resume", "status": "running"}


def test_desktop_api_lists_history_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    history_store = FakeHistoryStore()
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=FakeRunner(),
        history_store=history_store,
    )

    result = api.list_runs()

    assert result["ok"] is True
    assert result["runs"][0]["task_id"] == "task_fake"
    assert history_store.listed is True


def test_desktop_api_gets_history_run_detail(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    history_store = FakeHistoryStore()
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=FakeRunner(),
        history_store=history_store,
    )

    result = api.get_run("task_fake")

    assert result["ok"] is True
    assert result["final_output"] == "done"
    assert history_store.requested_task_ids == ["task_fake"]


def test_desktop_api_reports_missing_history_run(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=FakeRunner(),
        history_store=FakeHistoryStore(),
    )

    result = api.get_run("task_missing")

    assert result == {"ok": False, "error": "任务不存在"}


def test_desktop_api_gets_memory_overview(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    memory_store = FakeMemoryStore()
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=FakeRunner(),
        memory_store=memory_store,
    )

    result = api.get_memory_overview()

    assert result["ok"] is True
    assert memory_store.called is True


def test_desktop_api_exposes_runtime_skills_and_vendor_packs(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    skills_root = tmp_path / "skills"
    vendor_root = skills_root / "vendor" / "geo-agent-marketing-optimized"
    vendor_root.mkdir(parents=True)
    (vendor_root / "README.md").write_text("# GEO Agent\n", encoding="utf-8")
    (skills_root / "geo_analysis.md").write_text(
        "\n".join(
            [
                "---",
                "id: geo_analysis",
                "name: GEO 分析",
                "task_type: geo_analysis",
                "enabled: true",
                "priority: 120",
                "trigger_keywords:",
                "  - GEO",
                "workflow:",
                "  - 读取 GEO 规则包并生成问题矩阵",
                "  - 生成 GEO 分析报告",
                "---",
            ]
        ),
        encoding="utf-8",
    )

    api = DesktopAPI(settings_store=SettingsStore(), runner=FakeRunner(), skills_root=skills_root)

    result = api.get_skill_overview()

    assert result["ok"] is True
    assert result["counts"] == {"runtime_skills": 1, "vendor_packs": 1}
    assert result["runtime_skills"][0]["id"] == "geo_analysis"
    assert result["runtime_skills"][0]["task_type"] == "geo_analysis"
    assert result["runtime_skills"][0]["enabled"] is True
    assert result["vendor_packs"][0]["name"] == "geo-agent-marketing-optimized"
    assert result["vendor_packs"][0]["has_readme"] is True


def test_desktop_api_creates_and_lists_conversations(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=FakeRunner(),
        conversation_store=ConversationStore(tmp_path / "conversations"),
    )

    created = api.new_conversation()
    listed = api.list_conversations()

    assert created["ok"] is True
    assert listed["ok"] is True
    assert listed["conversations"][0]["conversation_id"] == created["conversation"]["conversation_id"]


def test_desktop_api_deletes_conversation(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    conversation_store = ConversationStore(tmp_path / "conversations")
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=FakeRunner(),
        conversation_store=conversation_store,
    )
    conversation_id = api.new_conversation()["conversation"]["conversation_id"]

    result = api.delete_conversation(conversation_id)

    assert result == {"ok": True, "conversation_id": conversation_id}
    assert api.get_conversation(conversation_id) == {"ok": False, "error": "会话不存在"}


def test_desktop_api_selects_and_persists_workspace_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    api = DesktopAPI(settings_store=SettingsStore(), runner=FakeRunner())
    window = FakeDialogWindow([str(workspace)])
    api.bind_window(window)

    result = api.select_workspace()

    assert result == {"ok": True, "workspace_path": str(workspace.resolve())}
    assert api.get_settings()["workspace_path"] == str(workspace.resolve())
    assert window.calls


def test_desktop_api_workspace_selection_cancel_keeps_existing_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    settings_store = SettingsStore()
    settings_store.save({"workspace_path": str(workspace)})
    api = DesktopAPI(settings_store=settings_store, runner=FakeRunner())
    api.bind_window(FakeDialogWindow(None))

    result = api.select_workspace()

    assert result == {"ok": False, "cancelled": True, "workspace_path": str(workspace.resolve())}
    assert api.get_settings()["workspace_path"] == str(workspace.resolve())


def test_desktop_api_selects_multiple_supported_knowledge_files(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    markdown = workspace / "notes.md"
    text_file = workspace / "facts.txt"
    markdown.write_text("notes", encoding="utf-8")
    text_file.write_text("facts", encoding="utf-8")
    settings_store = SettingsStore()
    settings_store.save({"workspace_path": str(workspace)})
    api = DesktopAPI(settings_store=settings_store, runner=FakeRunner())
    window = FakeDialogWindow([str(markdown), str(text_file)])
    api.bind_window(window)

    result = api.select_knowledge_files()

    assert result == {"ok": True, "paths": [str(markdown.resolve()), str(text_file.resolve())]}
    assert window.calls[0][1]["allow_multiple"] is True
    assert window.calls[0][1]["directory"] == str(workspace.resolve())
    assert "*.md;*.txt" in window.calls[0][1]["file_types"][0]


def test_desktop_api_selects_knowledge_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    folder = tmp_path / "knowledge"
    folder.mkdir()
    api = DesktopAPI(settings_store=SettingsStore(), runner=FakeRunner())
    window = FakeDialogWindow([str(folder)])
    api.bind_window(window)

    result = api.select_knowledge_folder()

    assert result == {"ok": True, "paths": [str(folder.resolve())]}
    assert window.calls[0][1]["allow_multiple"] is False


def test_desktop_api_knowledge_picker_cancel_is_not_an_error(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    api = DesktopAPI(settings_store=SettingsStore(), runner=FakeRunner())
    api.bind_window(FakeDialogWindow(None))

    assert api.select_knowledge_files() == {"ok": False, "cancelled": True, "paths": []}
    assert api.select_knowledge_folder() == {"ok": False, "cancelled": True, "paths": []}


def test_desktop_api_marks_only_agent_tasks_as_requiring_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    api = DesktopAPI(settings_store=SettingsStore(), runner=FakeRunner())

    chat = api.get_message_requirements("你好")
    task = api.get_message_requirements("帮我总结一段文本")

    assert chat["workspace_required"] is False
    assert task == {
        "ok": True,
        "route_kind": "task",
        "workspace_required": True,
        "workspace_path": "",
    }


def test_desktop_api_refuses_agent_task_until_workspace_is_selected(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=runner,
        conversation_store=ConversationStore(tmp_path / "conversations"),
    )
    api.save_settings({"llm_api_key": "secret-key"})

    result = api.run_chat_message("", "帮我总结一段文本")

    assert result["ok"] is False
    assert result["reason"] == "workspace_required"
    assert result["open_workspace"] is True
    assert runner.started_inputs == []


def test_desktop_api_run_chat_message_refuses_without_key(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=runner,
        conversation_store=ConversationStore(tmp_path / "conversations"),
    )

    result = api.run_chat_message("", "帮我总结")

    assert result["ok"] is False
    assert "Key" in result["error"]
    assert runner.started_inputs == []


def test_desktop_api_capability_question_requires_model_when_no_key(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    conversation_store = ConversationStore(tmp_path / "conversations")
    api = DesktopAPI(settings_store=SettingsStore(), runner=runner, conversation_store=conversation_store)

    result = api.run_chat_message("", "你能干什么")

    assert result["ok"] is False
    assert "Key" in result["error"]
    assert runner.started_inputs == []


def test_desktop_api_greeting_uses_llm_when_key_is_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    chat_client = FakeChatClient("你好，我会先理解你的问题，再决定聊天还是执行任务。")
    conversation_store = ConversationStore(tmp_path / "conversations")
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=runner,
        conversation_store=conversation_store,
        chat_client=chat_client,
    )
    api.save_settings({"llm_api_key": "secret-key"})

    result = api.run_chat_message("", "你好")
    conversation = conversation_store.get_conversation(result["conversation_id"])["conversation"]

    assert result["ok"] is True
    assert result["direct"] is True
    assert result["category"] == "general_chat"
    assert result["task_id"] is None
    assert result["message"] == "你好，我会先理解你的问题，再决定聊天还是执行任务。"
    assert runner.started_inputs == []
    assert len(chat_client.calls) == 1
    assert "你好" in chat_client.calls[0][1]
    assert conversation["messages"][1]["content"] == "你好，我会先理解你的问题，再决定聊天还是执行任务。"


def test_desktop_api_capability_question_uses_llm_when_key_is_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    chat_client = FakeChatClient("我可以聊天，也可以把明确任务拆解执行。")
    conversation_store = ConversationStore(tmp_path / "conversations")
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=runner,
        conversation_store=conversation_store,
        chat_client=chat_client,
    )
    api.save_settings({"llm_api_key": "secret-key"})

    result = api.run_chat_message("", "你能干什么")
    conversation = conversation_store.get_conversation(result["conversation_id"])["conversation"]

    assert result["ok"] is True
    assert result["direct"] is True
    assert result["category"] == "general_chat"
    assert result["task_id"] is None
    assert result["message"] == "我可以聊天，也可以把明确任务拆解执行。"
    assert runner.started_inputs == []
    assert len(chat_client.calls) == 1
    assert "你能干什么" in chat_client.calls[0][1]
    assert conversation["messages"][1]["content"] == "我可以聊天，也可以把明确任务拆解执行。"


def test_desktop_api_general_chat_prompt_declares_authorized_local_tool_boundary(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    chat_client = FakeChatClient("我不能直接操作你的本地电脑。")
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=FakeRunner(),
        conversation_store=ConversationStore(tmp_path / "conversations"),
        chat_client=chat_client,
    )
    api.save_settings({"llm_api_key": "secret-key"})

    result = api.run_chat_message("", "你能帮我操作本地电脑整理桌面吗？")

    assert result["ok"] is True
    system_prompt = chat_client.calls[0][0]
    assert "受控的本地文件操作" in system_prompt
    assert "每次操作前手动授权" in system_prompt
    assert "授权目录" in system_prompt
    assert "不能控制鼠标" in system_prompt
    assert "不能打开或控制其他本地应用" in system_prompt


def test_desktop_api_general_chat_prompt_includes_selected_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    chat_client = FakeChatClient("当前在 workspace 工作区。")
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=FakeRunner(),
        conversation_store=ConversationStore(tmp_path / "conversations"),
        chat_client=chat_client,
    )
    api.save_settings({"llm_api_key": "secret-key", "workspace_path": str(workspace)})

    result = api.run_chat_message("", "你现在在哪个文件夹工作？")

    assert result["ok"] is True
    assert f"当前工作区：{workspace.resolve()}" in chat_client.calls[0][0]


def test_desktop_api_general_chat_uses_llm_without_starting_runner(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    chat_client = FakeChatClient()
    conversation_store = ConversationStore(tmp_path / "conversations")
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=runner,
        conversation_store=conversation_store,
        chat_client=chat_client,
    )
    api.save_settings({"llm_api_key": "secret-key"})

    result = api.run_chat_message("", "我想学习 AI，你建议从哪里开始？")
    conversation = conversation_store.get_conversation(result["conversation_id"])["conversation"]

    assert result["ok"] is True
    assert result["direct"] is True
    assert result["category"] == "general_chat"
    assert result["task_id"] is None
    assert result["message"] == "我的建议是先从一个小项目开始。"
    assert runner.started_inputs == []
    assert "学习型 Agent" in chat_client.calls[0][0]
    assert "我想学习 AI" in chat_client.calls[0][1]
    assert conversation["messages"][1]["content"] == "我的建议是先从一个小项目开始。"


def test_desktop_api_uses_model_route_for_ambiguous_task(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    client = FakeStructuredChatClient(
        {"kind": "task", "reason": "需要处理工作区材料", "confidence": 0.9, "reply": ""}
    )
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=runner,
        conversation_store=ConversationStore(tmp_path / "conversations"),
        chat_client=client,
    )
    api.save_settings({"llm_api_key": "secret-key", "workspace_path": str(tmp_path)})

    result = api.run_chat_message("", "把这些材料处理一下")

    assert result["ok"] is True
    assert result["task_id"] == "task_fake"
    assert result["route"]["source"] == "model"
    assert runner.started_display_inputs == ["把这些材料处理一下"]
    assert len(client.structured_calls) == 1
    assert client.chat_calls == []


def test_desktop_api_reuses_model_route_reply_for_general_chat(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    client = FakeStructuredChatClient(
        {"kind": "chat", "reason": "创意讨论", "confidence": 0.87, "reply": "可以叫星河计划。"}
    )
    conversation_store = ConversationStore(tmp_path / "conversations")
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=runner,
        conversation_store=conversation_store,
        chat_client=client,
    )
    api.save_settings({"llm_api_key": "secret-key"})

    result = api.run_chat_message("", "帮我想一个项目名字")
    conversation = conversation_store.get_conversation(result["conversation_id"])["conversation"]

    assert result["ok"] is True
    assert result["direct"] is True
    assert result["message"] == "可以叫星河计划。"
    assert result["route"]["kind"] == "chat"
    assert len(client.structured_calls) == 1
    assert client.chat_calls == []
    assert runner.started_inputs == []
    assert conversation["messages"][1]["content"] == "可以叫星河计划。"


def test_desktop_api_streams_general_chat_through_versioned_desktop_events(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    client = FakeStreamingStructuredChatClient(
        {"kind": "chat", "reason": "普通问答", "confidence": 0.92, "reply": "完整备用回复"},
        ["你", "好", "。"],
    )
    window = FakeEventWindow()
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=FakeRunner(),
        conversation_store=ConversationStore(tmp_path / "conversations"),
        chat_client=client,
    )
    api.bind_window(window)
    api.save_settings({"llm_api_key": "secret-key"})

    result = api.run_chat_message("", "你好", "request_1")
    events = [
        json.loads(script.split("window.onDesktopEvent(", 1)[1].rsplit(");", 1)[0])
        for script in window.scripts
        if "window.onDesktopEvent(" in script
    ]

    assert result["ok"] is True
    assert result["message"] == "你好。"
    assert len(client.structured_calls) == 1
    assert len(client.stream_calls) == 1
    assert client.chat_calls == []
    assert [event["type"] for event in events] == [
        "assistant_started",
        "assistant_delta",
        "assistant_delta",
        "assistant_delta",
        "assistant_completed",
    ]
    assert all(event["version"] == 1 for event in events)
    assert all(event["conversation_id"] == result["conversation_id"] for event in events)
    assert [event["data"].get("delta") for event in events[1:4]] == ["你", "好", "。"]
    assert all(event["data"]["request_id"] == "request_1" for event in events)


def test_desktop_api_safety_overrides_model_chat_for_file_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    client = FakeStructuredChatClient(
        {"kind": "chat", "reason": "可以直接回答", "confidence": 0.99, "reply": "已经删除。"}
    )
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=runner,
        conversation_store=ConversationStore(tmp_path / "conversations"),
        chat_client=client,
    )
    api.save_settings(
        {
            "llm_api_key": "secret-key",
            "workspace_path": str(tmp_path),
            "dangerous_tools_enabled": True,
        }
    )

    result = api.run_chat_message("", "删除文件 notes.txt")

    assert result["ok"] is True
    assert result["route"]["source"] == "safety"
    assert runner.started_display_inputs == ["删除文件 notes.txt"]
    assert client.chat_calls == []


def test_desktop_api_general_chat_includes_same_conversation_context(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    chat_client = FakeChatClient("你刚才说你叫天甲树，正在做 UTA 桌面端。")
    conversation_store = ConversationStore(tmp_path / "conversations")
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=runner,
        conversation_store=conversation_store,
        chat_client=chat_client,
    )
    api.save_settings({"llm_api_key": "secret-key"})
    conversation_id = conversation_store.new_conversation()["conversation"]["conversation_id"]
    conversation_store.append_message(conversation_id, role="user", content="我叫天甲树，正在做 UTA 桌面端。")
    conversation_store.append_message(conversation_id, role="assistant", content="记住了。")

    result = api.run_chat_message(conversation_id, "我刚才说我叫什么？")

    assert result["ok"] is True
    assert runner.started_inputs == []
    assert "同一对话前文" in chat_client.calls[0][1]
    assert "我叫天甲树，正在做 UTA 桌面端。" in chat_client.calls[0][1]
    assert "记住了。" in chat_client.calls[0][1]
    assert "我刚才说我叫什么？" in chat_client.calls[0][1]


def test_desktop_api_general_chat_includes_long_term_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    memory_store = MemoryStore(tmp_path / "memory")
    memory_store.merge_long_term_candidates(
        [
            {
                "kind": "preference",
                "content": "用户明确要求始终使用中文回复。",
                "confidence": 0.95,
                "source_message_ids": ["msg_1"],
            }
        ],
        conversation_id="conv_20260701_120000_000000",
    )
    chat_client = FakeChatClient("好的，我会继续使用中文。")
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=FakeRunner(),
        memory_store=memory_store,
        conversation_store=ConversationStore(tmp_path / "conversations"),
        chat_client=chat_client,
    )
    api.save_settings({"llm_api_key": "secret-key"})

    result = api.run_chat_message("", "继续聊刚才的话题")

    assert result["ok"] is True
    assert "长期记忆" in chat_client.calls[0][1]
    assert "用户明确要求始终使用中文回复。" in chat_client.calls[0][1]


def test_desktop_api_contextual_greeting_uses_llm_with_same_conversation_context(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    chat_client = FakeChatClient("你刚才说你叫天甲树。")
    conversation_store = ConversationStore(tmp_path / "conversations")
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=runner,
        conversation_store=conversation_store,
        chat_client=chat_client,
    )
    api.save_settings({"llm_api_key": "secret-key"})
    conversation_id = conversation_store.new_conversation()["conversation"]["conversation_id"]
    conversation_store.append_message(conversation_id, role="user", content="我叫天甲树。")
    conversation_store.append_message(conversation_id, role="assistant", content="好的，我记住了。")

    result = api.run_chat_message(conversation_id, "你好，你记得我刚才说我叫什么吗？")

    assert result["ok"] is True
    assert result["category"] == "general_chat"
    assert result["message"] == "你刚才说你叫天甲树。"
    assert runner.started_inputs == []
    assert "同一对话前文" in chat_client.calls[0][1]
    assert "我叫天甲树。" in chat_client.calls[0][1]


def test_desktop_api_general_chat_requires_key_without_starting_runner(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=runner,
        conversation_store=ConversationStore(tmp_path / "conversations"),
        chat_client=FakeChatClient(),
    )

    result = api.run_chat_message("", "我想学习 AI，你建议从哪里开始？")

    assert result["ok"] is False
    assert "API Key" in result["error"]
    assert runner.started_inputs == []


def test_desktop_api_run_chat_message_starts_runner_and_records_messages(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    conversation_store = ConversationStore(tmp_path / "conversations")
    api = DesktopAPI(settings_store=SettingsStore(), runner=runner, conversation_store=conversation_store)
    api.save_settings({"llm_api_key": "secret-key", "workspace_path": str(tmp_path)})

    result = api.run_chat_message("", "帮我总结")
    conversation = conversation_store.get_conversation(result["conversation_id"])["conversation"]

    assert result["ok"] is True
    assert result["task_id"] == "task_fake"
    assert len(runner.started_inputs) == 1
    assert f"当前工作区：{tmp_path.resolve()}" in runner.started_inputs[0]
    assert runner.started_inputs[0].endswith("帮我总结")
    assert [message["role"] for message in conversation["messages"]] == ["user", "assistant"]
    assert conversation["messages"][1]["status"] == "running"
    assert runner.started_contexts == [
        {
            "conversation_id": result["conversation_id"],
            "workspace_path": str(tmp_path.resolve()),
        }
    ]


def test_desktop_api_run_chat_message_refuses_dangerous_task_when_tools_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    conversation_store = ConversationStore(tmp_path / "conversations")
    api = DesktopAPI(settings_store=SettingsStore(), runner=runner, conversation_store=conversation_store)
    api.save_settings({"llm_api_key": "secret-key"})

    result = api.run_chat_message("", "写入文件 /tmp/uta-note.txt 内容 hello")

    assert result["ok"] is False
    assert result["reason"] == "dangerous_tools_disabled"
    assert result["open_settings"] is True
    assert "工具授权" in result["error"]
    assert runner.started_inputs == []


def test_desktop_api_run_chat_message_starts_dangerous_task_when_tools_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    conversation_store = ConversationStore(tmp_path / "conversations")
    api = DesktopAPI(settings_store=SettingsStore(), runner=runner, conversation_store=conversation_store)
    api.save_settings(
        {
            "llm_api_key": "secret-key",
            "dangerous_tools_enabled": True,
            "workspace_path": str(tmp_path),
        }
    )

    result = api.run_chat_message("", "写入文件 /tmp/uta-note.txt 内容 hello")

    assert result["ok"] is True
    assert result["task_id"] == "task_fake"
    assert runner.started_display_inputs == ["写入文件 /tmp/uta-note.txt 内容 hello"]


def test_desktop_api_run_chat_message_requires_desktop_access_for_directory_task(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    conversation_store = ConversationStore(tmp_path / "conversations")
    api = DesktopAPI(settings_store=SettingsStore(), runner=runner, conversation_store=conversation_store)
    api.save_settings({"llm_api_key": "secret-key", "dangerous_tools_enabled": True})

    result = api.run_chat_message("", "帮我在桌面创建一个名叫测试的文件夹")

    assert result["ok"] is False
    assert result["reason"] == "desktop_access_disabled"
    assert result["open_settings"] is True
    assert runner.started_inputs == []


def test_desktop_api_run_chat_message_starts_desktop_directory_task_when_access_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    conversation_store = ConversationStore(tmp_path / "conversations")
    api = DesktopAPI(settings_store=SettingsStore(), runner=runner, conversation_store=conversation_store)
    api.save_settings(
        {
            "llm_api_key": "secret-key",
            "dangerous_tools_enabled": True,
            "desktop_access_enabled": True,
            "workspace_path": str(tmp_path),
        }
    )

    result = api.run_chat_message("", "帮我在桌面创建一个名叫测试的文件夹")

    assert result["ok"] is True
    assert result["task_id"] == "task_fake"
    assert runner.started_display_inputs == ["帮我在桌面创建一个名叫测试的文件夹"]


def test_desktop_api_task_includes_same_conversation_context_without_polluting_saved_message(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    conversation_store = ConversationStore(tmp_path / "conversations")
    api = DesktopAPI(settings_store=SettingsStore(), runner=runner, conversation_store=conversation_store)
    api.save_settings({"llm_api_key": "secret-key", "workspace_path": str(tmp_path)})
    conversation_id = conversation_store.new_conversation()["conversation"]["conversation_id"]
    conversation_store.append_message(conversation_id, role="user", content="这次项目叫 UTA 桌面端记忆修复。")
    conversation_store.append_message(conversation_id, role="assistant", content="我会围绕这个项目继续。")

    result = api.run_chat_message(conversation_id, "帮我总结刚才提到的项目")
    conversation = conversation_store.get_conversation(conversation_id)["conversation"]

    assert result["ok"] is True
    assert len(runner.started_inputs) == 1
    assert "同一对话前文" in runner.started_inputs[0]
    assert f"当前工作区：{tmp_path.resolve()}" in runner.started_inputs[0]
    assert "这次项目叫 UTA 桌面端记忆修复。" in runner.started_inputs[0]
    assert "帮我总结刚才提到的项目" in runner.started_inputs[0]
    assert runner.started_display_inputs == ["帮我总结刚才提到的项目"]
    assert conversation["messages"][-2]["role"] == "user"
    assert conversation["messages"][-2]["content"] == "帮我总结刚才提到的项目"


def test_desktop_api_task_includes_long_term_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    memory_store = MemoryStore(tmp_path / "memory")
    memory_store.merge_long_term_candidates(
        [
            {
                "kind": "project",
                "content": "当前项目是 UTA Desktop。",
                "confidence": 0.9,
                "source_message_ids": [],
            }
        ],
        conversation_id="conv_20260701_120000_000000",
    )
    runner = FakeRunner()
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=runner,
        memory_store=memory_store,
        conversation_store=ConversationStore(tmp_path / "conversations"),
    )
    api.save_settings({"llm_api_key": "secret-key", "workspace_path": str(tmp_path)})

    result = api.run_chat_message("", "帮我总结当前项目")

    assert result["ok"] is True
    assert "长期记忆" in runner.started_inputs[0]
    assert "当前项目是 UTA Desktop。" in runner.started_inputs[0]


def test_desktop_api_sync_chat_result_updates_assistant_message(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    conversation_store = ConversationStore(tmp_path / "conversations")
    api = DesktopAPI(settings_store=SettingsStore(), runner=runner, conversation_store=conversation_store)
    api.save_settings({"llm_api_key": "secret-key", "workspace_path": str(tmp_path)})
    started = api.run_chat_message("", "帮我总结")

    synced = api.sync_chat_result(started["conversation_id"], started["task_id"])
    conversation = conversation_store.get_conversation(started["conversation_id"])["conversation"]

    assert synced["ok"] is True
    assistant = conversation["messages"][1]
    assert assistant["content"] == "done"
    assert assistant["status"] == "completed"


def test_desktop_api_compresses_conversation_and_merges_long_term_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    conversation_store = ConversationStore(tmp_path / "conversations")
    memory_store = FakeMemoryStore()
    chat_client = FakeChatClient(
        json.dumps(
            {
                "short_term_summary": "用户正在改造 UTA 的记忆系统。",
                "long_term_candidates": [
                    {
                        "kind": "preference",
                        "content": "用户明确要求使用中文回复。",
                        "confidence": 0.95,
                        "source_message_ids": ["msg_missing"],
                    }
                ],
                "open_questions": ["是否默认开启自动压缩？"],
            },
            ensure_ascii=False,
        )
    )
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=FakeRunner(),
        memory_store=memory_store,
        conversation_store=conversation_store,
        chat_client=chat_client,
    )
    api.save_settings({"llm_api_key": "secret-key"})
    conversation_id = conversation_store.new_conversation()["conversation"]["conversation_id"]
    conversation_store.append_message(conversation_id, role="user", content="我希望你以后都用中文。")
    conversation_store.append_message(conversation_id, role="assistant", content="好的。")

    result = api.compress_conversation(conversation_id)
    conversation = conversation_store.get_conversation(conversation_id)["conversation"]

    assert result["ok"] is True
    assert result["compressed"] is True
    assert result["compressed_until_index"] == 2
    assert conversation["short_term"]["summary"] == "用户正在改造 UTA 的记忆系统。"
    assert conversation["short_term"]["compressed_until_index"] == 2
    assert conversation["compression"]["runs"][0]["message_count"] == 2
    assert memory_store.merge_conversation_id == conversation_id
    assert memory_store.merged_candidates[0]["content"] == "用户明确要求使用中文回复。"
    assert memory_store.merged_candidates[1]["kind"] == "open_question"
    assert "只输出 JSON" in chat_client.calls[0][0]


def test_desktop_api_archives_old_messages_after_compression(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    conversation_store = ConversationStore(tmp_path / "conversations")
    memory_store = FakeMemoryStore()
    chat_client = FakeChatClient(
        json.dumps(
            {
                "short_term_summary": "用户正在连续测试会话归档。",
                "long_term_candidates": [],
                "open_questions": [],
            },
            ensure_ascii=False,
        )
    )
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=FakeRunner(),
        memory_store=memory_store,
        conversation_store=conversation_store,
        chat_client=chat_client,
    )
    api.save_settings({"llm_api_key": "secret-key"})
    conversation_id = conversation_store.new_conversation()["conversation"]["conversation_id"]
    conversation_store.update_memory_state(
        conversation_id,
        short_term={
            "summary": "",
            "compressed_until_index": 0,
            "recent_message_limit": 2,
            "token_estimate": 0,
            "updated_at": "",
        },
        compression={"last_compressed_at": "", "last_trigger_tokens": 0, "runs": []},
    )
    for index in range(6):
        role = "user" if index % 2 == 0 else "assistant"
        conversation_store.append_message(conversation_id, role=role, content=f"message-{index}")

    result = api.compress_conversation(conversation_id)
    conversation = conversation_store.get_conversation(conversation_id)["conversation"]
    archive_path = tmp_path / "conversations" / "archives" / f"{conversation_id}.json"
    archive_payload = json.loads(archive_path.read_text(encoding="utf-8"))

    assert result["ok"] is True
    assert result["compressed"] is True
    assert [message["content"] for message in conversation["messages"]] == ["message-4", "message-5"]
    assert conversation["short_term"]["compressed_until_index"] == 2
    assert archive_payload["conversation_id"] == conversation_id
    assert len(archive_payload["chunks"]) == 1
    assert [message["content"] for message in archive_payload["chunks"][0]["messages"]] == [
        "message-0",
        "message-1",
        "message-2",
        "message-3",
    ]
    assert conversation["compression"]["runs"][0]["archived_message_count"] == 4
    context = _build_conversation_context(conversation)
    assert "message-4" in context
    assert "message-5" in context


def test_desktop_api_skips_compression_when_no_new_messages(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    conversation_store = ConversationStore(tmp_path / "conversations")
    chat_client = FakeChatClient("{}")
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=FakeRunner(),
        memory_store=FakeMemoryStore(),
        conversation_store=conversation_store,
        chat_client=chat_client,
    )
    api.save_settings({"llm_api_key": "secret-key"})
    conversation_id = conversation_store.new_conversation()["conversation"]["conversation_id"]

    result = api.compress_conversation(conversation_id)

    assert result == {
        "ok": True,
        "compressed": False,
        "conversation_id": conversation_id,
        "message": "没有新的会话消息需要压缩",
    }
    assert chat_client.calls == []


def test_desktop_api_auto_compresses_after_completed_chat_when_threshold_is_reached(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    conversation_store = ConversationStore(tmp_path / "conversations")
    memory_store = FakeMemoryStore()
    chat_client = FakeChatClient(
        [
            "普通聊天回复",
            json.dumps(
                {
                    "short_term_summary": "用户正在讨论 AI 应用学习。",
                    "long_term_candidates": [
                        {
                            "kind": "work_habit",
                            "content": "用户希望先评估方案，再按建议执行。",
                            "confidence": 0.9,
                            "source_message_ids": [],
                        }
                    ],
                    "open_questions": [],
                },
                ensure_ascii=False,
            ),
        ]
    )
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=FakeRunner(),
        memory_store=memory_store,
        conversation_store=conversation_store,
        chat_client=chat_client,
    )
    api.save_settings(
        {
            "llm_api_key": "secret-key",
            "memory_context_window_tokens": 20,
            "memory_compression_trigger_ratio": 0.5,
        }
    )

    result = api.run_chat_message("", "我想学习 AI 应用开发，请根据我的情况给一点建议，内容稍微长一点方便触发记忆压缩。")
    conversation = conversation_store.get_conversation(result["conversation_id"])["conversation"]

    assert result["ok"] is True
    assert result["message"] == "普通聊天回复"
    assert result["compression"]["compressed"] is True
    assert conversation["short_term"]["summary"] == "用户正在讨论 AI 应用学习。"
    assert conversation["short_term"]["compressed_until_index"] == 2
    assert memory_store.merged_candidates[0]["kind"] == "work_habit"
    assert len(chat_client.calls) == 2


def test_desktop_api_auto_compresses_when_message_limit_is_reached(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    conversation_store = ConversationStore(tmp_path / "conversations")
    memory_store = FakeMemoryStore()
    chat_client = FakeChatClient(
        [
            "我可以聊天，也可以把明确任务拆解执行。",
            json.dumps(
                {
                    "short_term_summary": "用户询问 UTA 能力。",
                    "long_term_candidates": [],
                    "open_questions": [],
                },
                ensure_ascii=False,
            ),
        ]
    )
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=FakeRunner(),
        memory_store=memory_store,
        conversation_store=conversation_store,
        chat_client=chat_client,
    )
    api.save_settings(
        {
            "llm_api_key": "secret-key",
            "memory_context_window_tokens": 400_000,
            "memory_compression_trigger_ratio": 0.7,
            "memory_compression_cap_tokens": 250_000,
            "memory_compression_message_limit": 2,
        }
    )

    result = api.run_chat_message("", "你能干什么")
    conversation = conversation_store.get_conversation(result["conversation_id"])["conversation"]

    assert result["ok"] is True
    assert result["compression"]["compressed"] is True
    assert result["message"] == "我可以聊天，也可以把明确任务拆解执行。"
    assert conversation["short_term"]["summary"] == "用户询问 UTA 能力。"
    assert conversation["short_term"]["compressed_until_index"] == 2
    assert result["compression"]["reason"] == "message_limit"


def test_desktop_api_auto_compression_failure_does_not_fail_chat(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    conversation_store = ConversationStore(tmp_path / "conversations")
    chat_client = FakeChatClient(["普通聊天回复", "这不是 JSON"])
    api = DesktopAPI(
        settings_store=SettingsStore(),
        runner=FakeRunner(),
        memory_store=FakeMemoryStore(),
        conversation_store=conversation_store,
        chat_client=chat_client,
    )
    api.save_settings(
        {
            "llm_api_key": "secret-key",
            "memory_context_window_tokens": 20,
            "memory_compression_trigger_ratio": 0.5,
        }
    )

    result = api.run_chat_message("", "我想学习 AI 应用开发，请根据我的情况给一点建议，内容稍微长一点方便触发记忆压缩。")
    conversation = conversation_store.get_conversation(result["conversation_id"])["conversation"]

    assert result["ok"] is True
    assert result["message"] == "普通聊天回复"
    assert result["compression"]["ok"] is True
    assert result["compression"]["compressed"] is False
    assert "必须是 JSON" in result["compression"]["error"]
    assert conversation["compression"]["runs"][0]["status"] == "failed"

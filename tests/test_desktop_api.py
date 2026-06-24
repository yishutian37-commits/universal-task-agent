from datetime import datetime

import desktop.runner as runner_module
from desktop.api import DesktopAPI
from desktop.settings_store import SettingsStore


class FakeRunner:
    def __init__(self):
        self.window = None
        self.started_inputs = []
        self.cancelled_task_ids = []

    def bind_window(self, window):
        self.window = window

    def start(self, user_input):
        self.started_inputs.append(user_input)
        return "task_fake"

    def get_result(self, task_id):
        return {"status": "completed", "task_id": task_id, "final_output": "done"}

    def cancel(self, task_id):
        self.cancelled_task_ids.append(task_id)
        return {"ok": False, "error": "当前版本暂不支持取消"}


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
                "log": "[Main] task received\n",
                "final_output": "done",
            }
        return {"ok": False, "error": "任务不存在"}


class FakeMemoryStore:
    def __init__(self):
        self.called = False

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
    api.save_settings({"llm_api_key": "secret-key"})

    result = api.run_task("帮我总结一段文本")

    assert result == {"ok": True, "task_id": "task_fake"}
    assert runner.started_inputs == ["帮我总结一段文本"]


def test_desktop_api_exposes_result_and_cancel(tmp_path, monkeypatch):
    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    runner = FakeRunner()
    api = DesktopAPI(settings_store=SettingsStore(), runner=runner)

    assert api.get_result("task_fake")["final_output"] == "done"
    assert api.cancel_task("task_fake")["ok"] is False
    assert runner.cancelled_task_ids == ["task_fake"]


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
    assert result["log"] == "[Main] task received\n"
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

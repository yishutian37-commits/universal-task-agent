import json
import os
import time

from desktop.history_store import HistoryStore


def write_state(root, task_id, payload):
    states = root / "states"
    states.mkdir(parents=True, exist_ok=True)
    path = states / f"{task_id}_state.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def write_log(root, task_id, text):
    logs = root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    path = logs / f"{task_id}.log"
    path.write_text(text, encoding="utf-8")
    return path


def test_history_store_lists_runs_newest_first_with_compact_summaries(tmp_path):
    old_path = write_state(
        tmp_path,
        "task_old",
        {
            "task_id": "task_old",
            "status": "completed",
            "task_type": "summarize",
            "intent": "旧任务",
            "updated_at": "2026-06-21T01:00:00",
            "final_output": "旧输出",
            "results": [{"large": "payload"}],
        },
    )
    new_path = write_state(
        tmp_path,
        "task_new",
        {
            "task_id": "state_task_id_should_not_win",
            "status": "failed",
            "task_type": "data_analysis",
            "intent": "新任务",
            "updated_at": "2026-06-21T02:00:00",
            "final_output": "新输出" * 80,
        },
    )
    now = time.time()
    os.utime(old_path, (now - 60, now - 60))
    os.utime(new_path, (now, now))

    result = HistoryStore(tmp_path).list_runs()

    assert [run["task_id"] for run in result["runs"]] == ["task_new", "task_old"]
    assert result["runs"][0]["status"] == "failed"
    assert result["runs"][0]["task_type"] == "data_analysis"
    assert result["runs"][0]["intent"] == "新任务"
    assert result["runs"][0]["updated_at"] == "2026-06-21T02:00:00"
    assert result["runs"][0]["modified_at"]
    assert result["runs"][0]["preview"].startswith("新输出")
    assert len(result["runs"][0]["preview"]) <= 123
    assert "state" not in result["runs"][0]
    old_run = next(run for run in result["runs"] if run["task_id"] == "task_old")
    assert "results" not in old_run


def test_history_store_get_run_returns_state_final_output_and_log(tmp_path):
    write_state(
        tmp_path,
        "task_1",
        {
            "task_id": "task_1",
            "status": "completed",
            "task_type": "summarize",
            "intent": "总结",
            "final_output": "## 摘要\n完成",
        },
    )
    write_log(tmp_path, "task_1", "[Main] task received\n")

    result = HistoryStore(tmp_path).get_run("task_1")

    assert result["ok"] is True
    assert result["task_id"] == "task_1"
    assert result["state"]["status"] == "completed"
    assert result["final_output"] == "## 摘要\n完成"
    assert result["log"] == "[Main] task received\n"


def test_history_store_get_run_succeeds_when_log_is_missing(tmp_path):
    write_state(tmp_path, "task_1", {"task_id": "task_1", "final_output": "done"})

    result = HistoryStore(tmp_path).get_run("task_1")

    assert result["ok"] is True
    assert result["log"] == ""


def test_history_store_get_run_ignores_log_symlink_escaping_logs(tmp_path):
    write_state(tmp_path, "task_1", {"task_id": "task_1", "final_output": "done"})
    outside_log = tmp_path / "outside.log"
    outside_log.write_text("secret log", encoding="utf-8")
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "task_1.log").symlink_to(outside_log)

    result = HistoryStore(tmp_path).get_run("task_1")

    assert result["ok"] is True
    assert result["log"] == ""


def test_history_store_skips_invalid_json_in_list_but_reports_selected_error(tmp_path):
    write_state(tmp_path, "task_good", {"task_id": "task_good", "final_output": "done"})
    bad_path = tmp_path / "states" / "task_bad_state.json"
    bad_path.write_text("{bad json", encoding="utf-8")

    listed = HistoryStore(tmp_path).list_runs()
    selected = HistoryStore(tmp_path).get_run("task_bad")

    assert [run["task_id"] for run in listed["runs"]] == ["task_good"]
    assert selected["ok"] is False
    assert "state JSON 无效" in selected["error"]


def test_history_store_skips_undecodable_state_in_list_but_reports_selected_error(tmp_path):
    write_state(tmp_path, "task_good", {"task_id": "task_good", "final_output": "done"})
    bad_path = tmp_path / "states" / "task_bad_state.json"
    bad_path.write_bytes(b"\xff\xfe\x80")

    listed = HistoryStore(tmp_path).list_runs()
    selected = HistoryStore(tmp_path).get_run("task_bad")

    assert [run["task_id"] for run in listed["runs"]] == ["task_good"]
    assert selected["ok"] is False
    assert "state JSON 无效" in selected["error"]


def test_history_store_list_runs_skips_state_symlink_escaping_states(tmp_path):
    write_state(tmp_path, "task_good", {"task_id": "task_good", "final_output": "done"})
    outside_state = tmp_path / "outside_state.json"
    outside_state.write_text(
        json.dumps({"task_id": "task_escape", "final_output": "secret"}),
        encoding="utf-8",
    )
    (tmp_path / "states" / "task_escape_state.json").symlink_to(outside_state)

    result = HistoryStore(tmp_path).list_runs()

    assert [run["task_id"] for run in result["runs"]] == ["task_good"]


def test_history_store_rejects_unknown_or_unsafe_task_ids(tmp_path):
    store = HistoryStore(tmp_path)

    assert store.get_run("task_missing") == {"ok": False, "error": "任务不存在"}
    unsafe = store.get_run("../task_missing")

    assert unsafe["ok"] is False
    assert unsafe["error"] == "任务不存在"

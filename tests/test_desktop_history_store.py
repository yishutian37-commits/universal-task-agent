import json

from core.history_store import HistoryStore as CoreHistoryStore
from desktop.history_store import HistoryStore


def write_task_history(memory_root, tasks):
    memory_root.mkdir(parents=True, exist_ok=True)
    (memory_root / "task_history.json").write_text(
        json.dumps({"version": 1, "tasks": tasks}, ensure_ascii=False),
        encoding="utf-8",
    )


def test_history_store_lists_runs_newest_first(tmp_path):
    # task_history.json 按写入时间追加，倒序展示（新在前）
    write_task_history(
        tmp_path,
        [
            {
                "task_id": "task_old",
                "status": "completed",
                "task_type": "summarize",
                "intent": "旧任务",
                "final_output": "旧输出",
                "final_output_preview": "旧输出",
                "updated_at": "2026-06-21 01:00:00",
            },
            {
                "task_id": "task_new",
                "status": "failed",
                "task_type": "data_analysis",
                "intent": "新任务",
                "final_output": "新输出" * 80,
                "final_output_preview": "新输出" * 80,
                "updated_at": "2026-06-21 02:00:00",
            },
        ],
    )

    result = HistoryStore(tmp_path).list_runs()

    assert [run["task_id"] for run in result["runs"]] == ["task_new", "task_old"]
    assert result["runs"][0]["status"] == "failed"
    assert result["runs"][0]["task_type"] == "data_analysis"
    assert result["runs"][0]["intent"] == "新任务"
    assert result["runs"][0]["updated_at"] == "2026-06-21 02:00:00"
    assert result["runs"][0]["preview"].startswith("新输出")
    assert len(result["runs"][0]["preview"]) <= 123
    # 列表只返回摘要，不含完整 state
    assert "state" not in result["runs"][0]


def test_history_store_get_run_returns_state_view_and_final_output(tmp_path):
    write_task_history(
        tmp_path,
        [
            {
                "task_id": "task_1",
                "user_input": "帮我总结",
                "task_type": "summarize",
                "intent": "总结",
                "status": "completed",
                "final_output": "## 摘要\n完成",
                "final_output_preview": "## 摘要\n完成",
                "result_count": 3,
                "check_count": 3,
                "feedback_count": 0,
                "updated_at": "2026-06-25 08:00:00",
            }
        ],
    )

    result = HistoryStore(tmp_path).get_run("task_1")

    assert result["ok"] is True
    assert result["task_id"] == "task_1"
    assert result["state"]["status"] == "completed"
    assert result["state"]["task_type"] == "summarize"
    assert result["state"]["result_count"] == 3
    assert result["final_output"] == "## 摘要\n完成"


def test_history_store_get_run_can_read_archived_task(tmp_path):
    write_task_history(tmp_path, [{"task_id": "task_recent", "final_output": "recent"}])
    archive_root = tmp_path / "archives"
    write_task_history(
        archive_root,
        [
            {
                "task_id": "task_archived",
                "user_input": "旧任务",
                "task_type": "summarize",
                "intent": "归档任务",
                "status": "completed",
                "final_output": "archived output",
                "final_output_preview": "archived output",
                "updated_at": "2026-07-01T08:00:00",
            }
        ],
    )
    (archive_root / "task_history.json").rename(archive_root / "task_history_2026-07.json")

    result = HistoryStore(tmp_path).get_run("task_archived")

    assert result["ok"] is True
    assert result["task_id"] == "task_archived"
    assert result["final_output"] == "archived output"
    assert result["state"]["intent"] == "归档任务"


def test_history_store_lists_empty_when_no_history_file(tmp_path):
    result = HistoryStore(tmp_path).list_runs()

    assert result["ok"] is True
    assert result["runs"] == []


def test_history_store_reports_unreadable_history(tmp_path):
    (tmp_path).mkdir(parents=True, exist_ok=True)
    (tmp_path / "task_history.json").write_text("{bad json", encoding="utf-8")

    listed = HistoryStore(tmp_path).list_runs()
    selected = HistoryStore(tmp_path).get_run("task_1")

    assert listed["ok"] is False
    assert selected["ok"] is False
    assert "不可读" in selected["error"]


def test_history_store_rejects_unknown_or_unsafe_task_ids(tmp_path):
    write_task_history(tmp_path, [{"task_id": "task_1", "final_output": "done"}])

    store = HistoryStore(tmp_path)

    assert store.get_run("task_missing") == {"ok": False, "error": "任务不存在"}
    unsafe = store.get_run("../task_missing")

    assert unsafe["ok"] is False
    assert unsafe["error"] == "任务不存在"


def test_desktop_history_store_uses_core_history_store():
    from desktop.history_store import HistoryStore

    assert HistoryStore is CoreHistoryStore

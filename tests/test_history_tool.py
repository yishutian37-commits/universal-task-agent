import json

from tools.history_tool import HistoryTool


def write_state(root, task_id, user_input, task_type="summarize", status="completed"):
    states_dir = root / "states"
    states_dir.mkdir(parents=True, exist_ok=True)
    (states_dir / f"{task_id}_state.json").write_text(
        json.dumps(
            {
                "task_id": task_id,
                "user_input": user_input,
                "task_type": task_type,
                "intent": "test",
                "status": status,
                "final_output": "done",
                "updated_at": "2026-06-25 08:00:00",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_history_tool_lists_previous_tasks_from_state_history(tmp_path):
    output_root = tmp_path / "outputs"
    memory_root = tmp_path / "memory"
    write_state(output_root, "task_1", "帮我总结一段文本", "summarize")
    write_state(output_root, "task_2", "帮我做 GEO 分析", "geo_analysis")

    result = HistoryTool(output_root=output_root, memory_root=memory_root).run(
        "list",
        {"user_input": "我之前让你进行过什么任务，给我列出来"},
    )

    assert result["history_query"] is True
    assert "## 历史任务" in result["message"]
    assert "帮我总结一段文本" in result["message"]
    assert "帮我做 GEO 分析" in result["message"]
    assert "summarize" in result["message"]
    assert "geo_analysis" in result["message"]


def test_history_tool_falls_back_to_json_memory_task_history(tmp_path):
    output_root = tmp_path / "outputs"
    memory_root = tmp_path / "memory"
    memory_root.mkdir()
    (memory_root / "task_history.json").write_text(
        json.dumps(
            {
                "version": 1,
                "tasks": [
                    {
                        "task_id": "task_memory",
                        "user_input": "分析 examples/orders.csv",
                        "task_type": "data_analysis",
                        "status": "completed",
                        "updated_at": "2026-06-25 09:00:00",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = HistoryTool(output_root=output_root, memory_root=memory_root).run("list", {})

    assert "分析 examples/orders.csv" in result["message"]
    assert "data_analysis" in result["message"]


def test_history_tool_reports_empty_history(tmp_path):
    result = HistoryTool(output_root=tmp_path / "outputs", memory_root=tmp_path / "memory").run("list", {})

    assert "暂无历史任务记录" in result["message"]

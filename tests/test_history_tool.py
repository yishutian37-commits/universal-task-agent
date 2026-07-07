import json

from tools.history_tool import HistoryTool


def write_task_history(memory_root, tasks):
    memory_root.mkdir(parents=True, exist_ok=True)
    (memory_root / "task_history.json").write_text(
        json.dumps({"version": 1, "tasks": tasks}, ensure_ascii=False),
        encoding="utf-8",
    )


def test_history_tool_lists_previous_tasks_from_memory(tmp_path):
    memory_root = tmp_path / "memory"
    write_task_history(
        memory_root,
        [
            {
                "task_id": "task_1",
                "user_input": "帮我总结一段文本",
                "task_type": "summarize",
                "intent": "总结",
                "status": "completed",
                "final_output": "## 摘要\n完成",
                "final_output_preview": "## 摘要\n完成",
                "updated_at": "2026-06-25 08:00:00",
            },
            {
                "task_id": "task_2",
                "user_input": "帮我做 GEO 分析",
                "task_type": "geo_analysis",
                "intent": "GEO",
                "status": "completed",
                "final_output": "## GEO 报告",
                "final_output_preview": "## GEO 报告",
                "updated_at": "2026-06-25 09:00:00",
            },
        ],
    )

    result = HistoryTool(memory_root=memory_root).run(
        "list",
        {"user_input": "我之前让你进行过什么任务，给我列出来"},
    )

    assert result["history_query"] is True
    assert result["source"] == "memory"
    assert "## 历史任务" in result["message"]
    # 倒序：新任务（task_2）在前
    assert "帮我做 GEO 分析" in result["message"]
    assert "帮我总结一段文本" in result["message"]
    assert "summarize" in result["message"]
    assert "geo_analysis" in result["message"]


def test_history_tool_reports_empty_history_when_no_memory(tmp_path):
    # memory 目录不存在
    result = HistoryTool(memory_root=tmp_path / "memory").run("list", {})

    assert "暂无历史任务记录" in result["message"]
    assert result["tasks"] == []


def test_history_tool_reports_empty_history_when_empty_tasks(tmp_path):
    memory_root = tmp_path / "memory"
    write_task_history(memory_root, [])

    result = HistoryTool(memory_root=memory_root).run("list", {})

    assert "暂无历史任务记录" in result["message"]

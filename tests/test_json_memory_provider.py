import json

from core.state import AgentState, CheckResult, ToolResult
from memory_providers.json_memory_provider import JsonMemoryProvider


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def completed_state(task_id="task_1", task_type="summarize"):
    state = AgentState(
        task_id=task_id,
        user_input="帮我总结一段文本",
        task_type=task_type,
        intent=f"{task_type}_intent",
        status="completed",
        final_output="## 摘要\n" + "这是一段较长输出。" * 30,
    )
    state.results.append(
        ToolResult(
            success=True,
            tool_name="report_tool",
            action_name="generate",
            result={"message": state.final_output},
        )
    )
    state.checks.append(CheckResult(passed=True, failed_reasons=[], suggested_fix=[]))
    return state


def failed_state(task_id="task_failed", task_type="data_analysis"):
    state = AgentState(
        task_id=task_id,
        user_input="分析表格",
        task_type=task_type,
        intent="analyze_table",
        status="failed",
        final_output="缺少必要小节：基础统计",
    )
    state.checks.append(
        CheckResult(
            passed=False,
            failed_reasons=["缺少必要小节：基础统计"],
            suggested_fix=["补齐基础统计小节"],
        )
    )
    return state


def test_json_memory_provider_creates_default_store_files(tmp_path):
    memory_root = tmp_path / "memory"

    provider = JsonMemoryProvider(memory_root)
    context = provider.load_context()

    assert sorted(context.keys()) == [
        "lessons",
        "negative_rules",
        "skill_candidates",
        "task_history",
        "user_profile",
    ]
    assert read_json(memory_root / "user_profile.json") == {
        "version": 1,
        "profile": {},
        "updated_at": None,
    }
    assert read_json(memory_root / "task_history.json") == {"version": 1, "tasks": []}
    assert read_json(memory_root / "lessons.json") == {"version": 1, "lessons": []}
    assert read_json(memory_root / "negative_rules.json") == {
        "version": 1,
        "negative_rules": [],
    }
    assert read_json(memory_root / "skill_candidates.json") == {
        "version": 1,
        "candidates": [],
    }


def test_save_completed_task_writes_history_and_lesson(tmp_path):
    memory_root = tmp_path / "memory"
    provider = JsonMemoryProvider(memory_root)
    state = completed_state(task_id="task_1", task_type="summarize")

    provider.save_task(state)

    history = read_json(memory_root / "task_history.json")
    lessons = read_json(memory_root / "lessons.json")

    assert len(history["tasks"]) == 1
    task = history["tasks"][0]
    assert task["task_id"] == "task_1"
    assert task["user_input"] == state.user_input
    assert task["task_type"] == "summarize"
    assert task["intent"] == "summarize_intent"
    assert task["status"] == "completed"
    assert task["result_count"] == 1
    assert task["check_count"] == 1
    assert task["feedback_count"] == 0
    assert len(task["final_output_preview"]) <= 300

    assert len(lessons["lessons"]) == 1
    lesson = lessons["lessons"][0]
    assert lesson["lesson_id"] == "lesson_task_1"
    assert lesson["task_id"] == "task_1"
    assert lesson["task_type"] == "summarize"
    assert "读取输入 -> 处理内容 -> 生成报告" in lesson["content"]
    assert lesson["source"] == "completed_task"


def test_save_task_updates_existing_history_record(tmp_path):
    provider = JsonMemoryProvider(tmp_path / "memory")
    state = completed_state(task_id="task_same", task_type="summarize")

    provider.save_task(state)
    state.status = "failed"
    state.final_output = "第二次保存"
    provider.save_task(state)

    history = read_json(tmp_path / "memory" / "task_history.json")

    assert len(history["tasks"]) == 1
    assert history["tasks"][0]["task_id"] == "task_same"
    assert history["tasks"][0]["status"] == "failed"


def test_save_task_archives_old_history_records_when_recent_limit_is_exceeded(tmp_path):
    memory_root = tmp_path / "memory"
    provider = JsonMemoryProvider(memory_root, recent_task_limit=2)

    for index in range(4):
        state = completed_state(task_id=f"task_{index}", task_type="summarize")
        state.updated_at = f"2026-07-0{index + 1}T08:00:00"
        provider.save_task(state)

    recent_history = read_json(memory_root / "task_history.json")
    archive_history = read_json(memory_root / "archives" / "task_history_2026-07.json")

    assert [task["task_id"] for task in recent_history["tasks"]] == ["task_2", "task_3"]
    assert [task["task_id"] for task in archive_history["tasks"]] == ["task_0", "task_1"]
    assert archive_history["tasks"][0]["final_output"].startswith("## 摘要")


def test_json_memory_provider_compacts_existing_task_history_on_init(tmp_path):
    memory_root = tmp_path / "memory"
    memory_root.mkdir()
    (memory_root / "task_history.json").write_text(
        json.dumps(
            {
                "version": 1,
                "tasks": [
                    {"task_id": "task_0", "updated_at": "2026-07-01T08:00:00"},
                    {"task_id": "task_1", "updated_at": "2026-07-02T08:00:00"},
                    {"task_id": "task_2", "updated_at": "2026-07-03T08:00:00"},
                    {"task_id": "task_3", "updated_at": "2026-07-04T08:00:00"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    JsonMemoryProvider(memory_root, recent_task_limit=2)

    recent_history = read_json(memory_root / "task_history.json")
    archive_history = read_json(memory_root / "archives" / "task_history_2026-07.json")
    assert [task["task_id"] for task in recent_history["tasks"]] == ["task_2", "task_3"]
    assert [task["task_id"] for task in archive_history["tasks"]] == ["task_0", "task_1"]


def test_save_failed_task_writes_negative_rule(tmp_path):
    provider = JsonMemoryProvider(tmp_path / "memory")
    state = failed_state()

    provider.save_task(state)

    payload = read_json(tmp_path / "memory" / "negative_rules.json")

    assert len(payload["negative_rules"]) == 1
    rule = payload["negative_rules"][0]
    assert rule["rule_id"] == "negative_task_failed"
    assert rule["task_id"] == "task_failed"
    assert rule["task_type"] == "data_analysis"
    assert "缺少必要小节：基础统计" in rule["content"]
    assert rule["source"] == "failed_task"


def test_cancelled_task_is_kept_in_history_without_negative_rule(tmp_path):
    memory_root = tmp_path / "memory"
    provider = JsonMemoryProvider(memory_root)
    state = AgentState(
        task_id="task_cancelled",
        user_input="执行复杂任务",
        task_type="complex_task",
        intent="execute_complex_task",
        status="cancelled",
        final_output="用户取消了计划执行",
    )

    provider.save_task(state)

    history = read_json(memory_root / "task_history.json")
    negative_rules = read_json(memory_root / "negative_rules.json")
    assert history["tasks"][0]["status"] == "cancelled"
    assert negative_rules["negative_rules"] == []


def test_successful_tasks_update_skill_candidate(tmp_path):
    provider = JsonMemoryProvider(tmp_path / "memory")

    provider.save_task(completed_state(task_id="task_1", task_type="summarize"))
    provider.save_task(completed_state(task_id="task_2", task_type="summarize"))
    provider.save_task(completed_state(task_id="task_3", task_type="summarize"))

    payload = read_json(tmp_path / "memory" / "skill_candidates.json")

    assert len(payload["candidates"]) == 1
    candidate = payload["candidates"][0]
    assert candidate["task_type"] == "summarize"
    assert candidate["success_count"] == 3
    assert candidate["latest_task_id"] == "task_3"
    assert candidate["status"] == "candidate"
    assert "summarize 已成功执行 3 次" in candidate["reason"]

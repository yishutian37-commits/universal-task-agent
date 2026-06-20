import json

from main import create_initial_state, run_task


def test_create_initial_state_uses_v0_1_fixed_summary_task_type():
    state = create_initial_state("task_test", "帮我总结一段文本")

    assert state.task_id == "task_test"
    assert state.task_type == "summarize"
    assert state.intent == "v0.1 hard-coded summarize skeleton"


def test_run_task_writes_state_and_log(tmp_path):
    state = run_task("帮我总结一段文本", output_root=tmp_path, task_id="task_test")

    state_path = tmp_path / "states" / "task_test_state.json"
    log_path = tmp_path / "logs" / "task_test.log"

    assert state.status == "completed"
    assert state.final_output == "mock result"
    assert state_path.exists()
    assert log_path.exists()

    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["status"] == "completed"
    assert saved["final_output"] == "mock result"
    assert "[Loop] step 1 started" in log_path.read_text(encoding="utf-8")

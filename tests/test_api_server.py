from __future__ import annotations

import json
import warnings

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated.*",
)

from fastapi.testclient import TestClient

import config
from api.server import app


def test_api_health_returns_ok():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_api_runs_research_task_with_fixture_search(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SEARCH_PROVIDER", "fixture")
    monkeypatch.setattr(config, "LLM_API_KEY", "")
    client = TestClient(app)

    response = client.post(
        "/v1/tasks/run",
        json={
            "task": "调研 UTA Agent 框架下一步路线",
            "task_id": "task_api_test",
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["task_id"] == "task_api_test"
    assert payload["status"] == "completed"
    assert payload["task_type"] == "research"
    assert "## 来源" in payload["final_output"]
    assert payload["state"]["task_type"] == "research"


def test_api_lists_and_gets_runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "LLM_API_KEY", "")

    memory_root = tmp_path / "memory"
    memory_root.mkdir(parents=True)
    (memory_root / "task_history.json").write_text(
        json.dumps(
            {
                "version": 1,
                "tasks": [
                    {
                        "task_id": "task_api_test",
                        "user_input": "调研 UTA Agent",
                        "task_type": "research",
                        "intent": "research_route",
                        "status": "completed",
                        "final_output": "## 结论\n路线清晰\n## 来源\n- 来源一",
                        "final_output_preview": "## 结论\n路线清晰",
                        "updated_at": "2026-06-25 08:00:00",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    client = TestClient(app)

    listed = client.get("/v1/runs", params={"memory_root": str(memory_root)})
    detail = client.get("/v1/runs/task_api_test", params={"memory_root": str(memory_root)})

    assert listed.status_code == 200
    assert listed.json()["runs"][0]["task_id"] == "task_api_test"
    assert detail.status_code == 200
    assert detail.json()["ok"] is True
    assert detail.json()["task_id"] == "task_api_test"
    assert "## 来源" in detail.json()["final_output"]


def test_api_run_task_requires_task_field():
    client = TestClient(app)

    response = client.post("/v1/tasks/run", json={})

    assert response.status_code == 422

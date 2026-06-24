from __future__ import annotations

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
    output_root = tmp_path / "outputs"
    client = TestClient(app)

    response = client.post(
        "/v1/tasks/run",
        json={
            "task": "调研 UTA Agent 框架下一步路线",
            "task_id": "task_api_test",
            "output_root": str(output_root),
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
    assert (output_root / "states" / "task_api_test_state.json").exists()


def test_api_lists_and_gets_runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SEARCH_PROVIDER", "fixture")
    monkeypatch.setattr(config, "LLM_API_KEY", "")
    output_root = tmp_path / "outputs"
    client = TestClient(app)

    client.post(
        "/v1/tasks/run",
        json={
            "task": "调研 UTA Agent 框架下一步路线",
            "task_id": "task_api_test",
            "output_root": str(output_root),
        },
    )

    listed = client.get("/v1/runs", params={"output_root": str(output_root)})
    detail = client.get("/v1/runs/task_api_test", params={"output_root": str(output_root)})

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

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

from core.history_store import HistoryStore
from main import run_task


app = FastAPI(title="UTA API", version="1.10.5")


class RunTaskRequest(BaseModel):
    task: str
    task_id: str | None = None


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/v1/tasks/run")
def run_task_endpoint(payload: RunTaskRequest) -> dict:
    try:
        state = run_task(
            payload.task,
            task_id=payload.task_id,
            memory_provider=False,
        )
    except Exception as exc:
        return {
            "ok": False,
            "task_id": payload.task_id,
            "status": "failed",
            "task_type": "unknown",
            "final_output": str(exc),
            "state": {},
        }

    return {
        "ok": state.status == "completed",
        "task_id": state.task_id,
        "status": state.status,
        "task_type": state.task_type,
        "final_output": state.final_output,
        "state": state.to_dict(),
    }


@app.get("/v1/runs")
def list_runs(memory_root: str = "memory") -> dict:
    return HistoryStore(memory_root).list_runs()


@app.get("/v1/runs/{task_id}")
def get_run(task_id: str, memory_root: str = "memory") -> dict:
    return HistoryStore(memory_root).get_run(task_id)

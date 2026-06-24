# Mainline V1 API And Code Reading Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把已有 `v1.1-research-search-api` 和 `v1.2-code-reading-agent` 成果整理回当前 `rag-knowledge-base` 主线，使当前桌面包同时具备 UTA API、搜索/天气、RAG 和代码阅读能力。

**Architecture:** 采用“最小合并，不重构”的方式：从历史 tag 恢复 UTA 根 API 和只读 CodeTool，再接入当前 TaskParser、Planner、Router、ReportTool、Verifier、工具注册表和桌面 runner。RAG 现有 `rag.api` 保持独立，根 `api.server` 只负责 UTA 任务运行和历史记录，不与 RAG API 混在一起。

**Tech Stack:** Python 3.12、FastAPI、pytest、pywebview/PyInstaller、现有 UTA core/tool/report/verifier 架构。

---

### Task 1: 恢复 UTA FastAPI 接口

**Files:**
- Create: `api/__init__.py`
- Create: `api/server.py`
- Create: `tests/test_api_server.py`
- Modify: `desktop/build/uta_app.spec`
- Modify: `README.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Write failing API tests**

Add `tests/test_api_server.py` with:

```python
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
```

- [ ] **Step 2: Run tests to verify red**

Run: `.venv/bin/python -m pytest tests/test_api_server.py -q`

Expected: FAIL because `api.server` does not exist.

- [ ] **Step 3: Implement root UTA API**

Create `api/server.py` with health, run task, list runs, and get run endpoints. Use `run_task(..., memory_provider=False)` to keep tests deterministic and avoid writing long-term memory during API test runs.

- [ ] **Step 4: Package API module**

Add `api`, `api.server` to `desktop/build/uta_app.spec` hiddenimports so packaged app can expose/import the UTA API module.

- [ ] **Step 5: Run API tests green**

Run: `.venv/bin/python -m pytest tests/test_api_server.py -q`

Expected: PASS.

### Task 2: 合并只读代码阅读 Agent

**Files:**
- Create: `tools/code_tool.py`
- Create: `tests/test_code_tool.py`
- Modify: `core/task_parser.py`
- Modify: `core/planner.py`
- Modify: `core/router.py`
- Modify: `tools/registry.py`
- Modify: `desktop/runner.py`
- Modify: `tools/report_tool.py`
- Modify: `core/verifier.py`
- Modify: `tests/test_task_parser.py`
- Modify: `tests/test_planner.py`
- Modify: `tests/test_router.py`
- Modify: `tests/test_report_tool.py`
- Modify: `tests/test_verifier.py`
- Modify: `desktop/build/uta_app.spec`

- [ ] **Step 1: Write failing tests**

Add tests for:
- `CodeTool` scans imports/classes/functions and fails on missing/syntax-broken key files.
- `TaskParser` fallback detects “阅读 UTA 代码，说明一次任务从输入到输出怎么跑” as `code_reading`.
- `Planner` creates `["扫描 UTA 任务执行链路代码", "生成代码阅读报告"]`.
- `Router` routes code scanning goals to `code_tool`.
- `ReportTool` renders eight required code report sections.
- `Verifier` rejects code reports missing required sections or required key files.

- [ ] **Step 2: Run tests to verify red**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_code_tool.py \
  tests/test_task_parser.py \
  tests/test_planner.py \
  tests/test_router.py \
  tests/test_report_tool.py \
  tests/test_verifier.py \
  -q
```

Expected: FAIL because `tools.code_tool` and `code_reading` wiring do not exist.

- [ ] **Step 3: Implement CodeTool and runtime wiring**

Create `tools/code_tool.py` from the historical v1.2 implementation, adapted to current files. Register it in `tools/registry.py`, `desktop/runner.py`, and `desktop/build/uta_app.spec`.

- [ ] **Step 4: Implement parser/planner/router/report/verifier support**

Extend `TaskParser.ALLOWED_TASK_TYPES`, fallback detection, `Planner._goals_for`, `Router.RULES`, `ReportTool._code_report`, and `Verifier._check_code_report`.

- [ ] **Step 5: Run code-reading tests green**

Run the test command from Step 2.

Expected: PASS.

### Task 3: 文档、全量验证、桌面打包和 Git 保存

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `desktop/README.md` if the packaged desktop instructions need updating.

- [ ] **Step 1: Update docs**

Document the current mainline as integrated: UTA API, research/weather, RAG, and code reading are on the same branch. Add a code reading demo command.

- [ ] **Step 2: Run full tests**

Run: `.venv/bin/python -m pytest -q`

Expected: all tests pass.

- [ ] **Step 3: Run smoke demos**

Run:

```bash
.venv/bin/python main.py --task "阅读 UTA 代码，说明一次任务从输入到输出怎么跑" --output-root /private/tmp/uta-code-reading-smoke
.venv/bin/python -m pytest tests/test_api_server.py tests/test_rag_api.py -q
```

Expected: code reading task completes and API tests pass.

- [ ] **Step 4: Rebuild desktop app**

Run: `bash desktop/build/build_macos.sh`

Expected: `dist/UTA Desktop.app` and `dist/UTA Desktop-macos.zip` are rebuilt.

- [ ] **Step 5: Verify app bundle**

Run: `codesign --verify --deep --strict --verbose=2 "dist/UTA Desktop.app"`

Expected: exit code 0.

- [ ] **Step 6: Commit**

Run:

```bash
git add api tests tools core desktop README.md CHANGELOG.md docs/superpowers/plans/2026-06-24-mainline-v1-api-code-reading-alignment.md
git commit -m "feat: align api and code reading on mainline"
```

Expected: clean working tree after commit.

---

## Self-Review

**Spec coverage:** Covers PRD backlog items already started in repository history: V1.1 FastAPI, V1.2 code reading, desktop packaging, tests, docs, and Git save point.

**Placeholder scan:** No TBD/TODO placeholders. Each task names exact files and verification commands.

**Type consistency:** `code_reading`, `code_analysis`, `source_code_analysis`, `api.server.app`, and route paths are used consistently across tests and production wiring.

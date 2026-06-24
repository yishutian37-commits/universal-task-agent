# GEO Skill Pack Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `geo-agent-marketing-optimized-v2.1.0-geoagent.zip` 作为规则来源嫁接进 UTA，形成可运行的 `geo_analysis` 任务链路和桌面端能力。

**Architecture:** 原 zip 不作为运行时插件执行，只把 Markdown 规则包保存到 `skills/vendor/geo-agent-marketing-optimized/`。UTA 通过根 Skill `skills/geo_analysis.md`、新工具 `tools/geo_tool.py`、`ReportTool` GEO 报告和 `Verifier` 硬校验来消费这些规则。首版只接 P0：问题矩阵、内容 Brief、平台合规检查；P1/P2/P3 先作为 vendor 资料保留，不进入默认流程。

**Tech Stack:** Python 3.12、现有 UTA SkillLoader/Planner/Router/Executor/Verifier、Markdown vendor rules、pytest、PyInstaller 桌面打包。

---

### Task 1: Vendor 规则包落地和 UTA Skill 适配

**Files:**
- Create: `skills/vendor/geo-agent-marketing-optimized/`
- Create: `skills/geo_analysis.md`
- Modify: `desktop/build/uta_app.spec`
- Test: `tests/test_skill_loader.py`

- [ ] **Step 1: Add failing SkillLoader test**

验证 `SkillLoader` 可以加载 `geo_analysis.md`，task_type 为 `geo_analysis`，workflow 包含 GEO 工具步骤和报告步骤。

- [ ] **Step 2: Run red**

Run: `.venv/bin/python -m pytest tests/test_skill_loader.py -q`

Expected: FAIL because `skills/geo_analysis.md` does not exist.

- [ ] **Step 3: Extract vendor Markdown rules**

Extract zip contents into `skills/vendor/geo-agent-marketing-optimized/` without executing anything. Keep `.mcp.json` as inert metadata only.

- [ ] **Step 4: Add UTA root skill**

Create `skills/geo_analysis.md` with UTA front matter and workflow:
`读取 GEO 规则包并生成问题矩阵` → `生成 GEO 分析报告`。

- [ ] **Step 5: Run green**

Run: `.venv/bin/python -m pytest tests/test_skill_loader.py -q`

Expected: PASS.

### Task 2: GEO task type and tool chain

**Files:**
- Create: `tools/geo_tool.py`
- Create: `tests/test_geo_tool.py`
- Modify: `core/task_parser.py`
- Modify: `core/planner.py`
- Modify: `core/router.py`
- Modify: `tools/registry.py`
- Modify: `desktop/runner.py`
- Modify: `desktop/build/uta_app.spec`
- Modify: parser/planner/router/desktop tests

- [ ] **Step 1: Add failing tests**

Tests must verify:
- fallback parser detects GEO tasks;
- planner creates GEO plan;
- router routes GEO step to `geo_tool`;
- registry and desktop runner register `geo_tool`;
- `GeoTool` produces fact gaps, four-layer question matrix, content briefs, compliance checks, and vendor rule paths.

- [ ] **Step 2: Run red**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_geo_tool.py \
  tests/test_task_parser.py \
  tests/test_planner.py \
  tests/test_router.py \
  tests/test_desktop_api.py \
  -q
```

Expected: FAIL because `tools.geo_tool` and `geo_analysis` wiring do not exist.

- [ ] **Step 3: Implement `GeoTool`**

Use deterministic rule-based generation. Do not call network or LLM. Extract brand/industry/region from user input with simple markers, generate four questions, one brief, and compliance result.

- [ ] **Step 4: Wire parser/planner/router/registry/desktop**

Add `geo_analysis` to allowed task types, fallback detection, plan goals, router rule, core registry, desktop runner, and PyInstaller hiddenimports.

- [ ] **Step 5: Run green**

Run the test command from Step 2.

Expected: PASS.

### Task 3: GEO report, verifier, docs, package

**Files:**
- Modify: `tools/report_tool.py`
- Modify: `core/verifier.py`
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `desktop/README.md`
- Test: `tests/test_report_tool.py`, `tests/test_verifier.py`

- [ ] **Step 1: Add failing report/verifier tests**

Verify GEO report contains sections: 事实输入、事实缺口、问题矩阵、内容Brief、平台合规、规则来源、下一步建议. Verifier should reject reports missing required sections or missing matrix questions.

- [ ] **Step 2: Run red**

Run: `.venv/bin/python -m pytest tests/test_report_tool.py tests/test_verifier.py -q`

Expected: FAIL because GEO report and verifier branch do not exist.

- [ ] **Step 3: Implement report and verifier**

Add `ReportTool._geo_report()` and `Verifier._check_geo_report()`.

- [ ] **Step 4: Full verification**

Run:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python main.py --task "帮我做 GEO 分析：行业是本地装修，地区是包头，品牌事实：有官网、提供设计和施工服务、需要避免夸大承诺。" --output-root /private/tmp/uta-geo-smoke
```

Expected: all tests pass, smoke task completes.

- [ ] **Step 5: Desktop package and commit**

Run:

```bash
bash desktop/build/build_macos.sh
codesign --verify --deep --strict --verbose=2 "dist/UTA Desktop.app"
git add ...
git commit -m "feat: add geo skill pack adapter"
git tag v1.3-geo-skill-adapter
```

Expected: packaged app exists, zip exists, working tree clean after commit.

---

## Self-Review

**Spec coverage:** Covers vendor rule preservation, UTA skill adapter, task parser/planner/router, deterministic tool, report, verifier, docs, desktop package, and tag.

**Placeholder scan:** No TBD/TODO placeholders.

**Scope:** Focused on P0 GEO chain only. P1/P2/P3 remain stored as vendor references for later.

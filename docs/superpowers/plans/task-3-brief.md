# Task 3: 统一工具注册表

**Files:**
- Modify: `tools/registry.py`
- Modify: `desktop/runner.py`
- Test: `tests/test_desktop_api.py`（现有测试覆盖 `runner_module.build_tool_registry`）

**Interfaces:**
- `tools.registry.build_tool_registry(project_root: Path | str | None = None, skills_root: Path | str | None = None, output_root: Path | str | None = None, memory_root: Path | str | None = None) -> dict[str, BaseTool]`
- `desktop/runner.py` 不再定义 `build_tool_registry`，改为 `from tools.registry import build_tool_registry`

- [ ] **Step 1: 修改 tools/registry.py 支持参数化根目录**

当前 `tools/registry.py` 全部代码：

```python
from tools.code_tool import CodeTool
from tools.file_tool import FileTool
from tools.geo_tool import GeoTool
from tools.history_tool import HistoryTool
from tools.mock_tool import MockTool
from tools.report_tool import ReportTool
from tools.search_tool import SearchTool
from tools.table_tool import TableTool
from tools.text_tool import TextTool


def build_tool_registry():
    return {
        "mock_tool": MockTool(),
        "code_tool": CodeTool(),
        "file_tool": FileTool(),
        "geo_tool": GeoTool(),
        "history_tool": HistoryTool(),
        "text_tool": TextTool(),
        "table_tool": TableTool(),
        "report_tool": ReportTool(),
        "search_tool": SearchTool(),
    }


TOOL_REGISTRY = build_tool_registry()
```

替换为：

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from desktop.paths import resource_path, uta_home
from tools.base_tool import BaseTool
from tools.code_tool import CodeTool
from tools.file_tool import FileTool
from tools.geo_tool import GeoTool
from tools.history_tool import HistoryTool
from tools.mock_tool import MockTool
from tools.report_tool import ReportTool
from tools.search_tool import SearchTool
from tools.table_tool import TableTool
from tools.text_tool import TextTool


def build_tool_registry(
    project_root: Path | str | None = None,
    skills_root: Path | str | None = None,
    output_root: Path | str | None = None,
    memory_root: Path | str | None = None,
) -> dict[str, BaseTool]:
    """构造工具注册表。

    参数用于桌面端等需要指定资源根目录的场景；CLI/默认场景不传参即可。
    """
    if project_root is not None:
        project_root = Path(project_root)
    else:
        project_root = Path.cwd()

    if skills_root is not None:
        skills_root = Path(skills_root)
    else:
        skills_root = project_root / "skills"

    if output_root is None:
        output_root = uta_home() / "outputs"

    if memory_root is None:
        memory_root = uta_home() / "memory"

    geo_vendor_root = skills_root / "vendor" / "geo-agent-marketing-optimized"

    return {
        "mock_tool": MockTool(),
        "code_tool": CodeTool(project_root=project_root),
        "file_tool": FileTool(),
        "geo_tool": GeoTool(geo_vendor_root),
        "history_tool": HistoryTool(output_root=output_root, memory_root=memory_root),
        "text_tool": TextTool(),
        "table_tool": TableTool(),
        "report_tool": ReportTool(),
        "search_tool": SearchTool(),
    }


TOOL_REGISTRY = build_tool_registry()
```

- [ ] **Step 2: 修改 desktop/runner.py 使用统一注册表**

删除 `desktop/runner.py` 中第 18-39 行的 `build_tool_registry` 定义及对应 imports。

在文件顶部增加：

```python
from tools.registry import build_tool_registry
```

修改 `_run` 中的调用：

```python
state = run_task_func(
    user_input,
    output_root=self.output_root,
    task_id=task_id,
    tool_registry=build_tool_registry(
        project_root=resource_path("."),
        skills_root=resource_path("skills"),
        output_root=self.output_root,
        memory_root=self.memory_root,
    ),
    memory_provider=JsonMemoryProvider(self.memory_root),
    skill_loader=SkillLoader(resource_path("skills")),
    on_progress=self._emit_progress,
)
```

- [ ] **Step 3: 运行桌面相关测试**

Run: `pytest tests/test_desktop_api.py tests/test_api_server.py -q`
Expected: 全部通过。

- [ ] **Step 4: Commit**

```bash
git add tools/registry.py desktop/runner.py
git commit -m "refactor: unify tool registry in tools.registry"
```

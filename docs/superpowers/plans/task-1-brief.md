# Task 1: 增加 pyproject.toml 并统一项目配置

**Files:**
- Create: `pyproject.toml`
- Delete/Move: `pytest.ini`（配置移入 pyproject.toml）
- Modify: `requirements.txt`, `requirements-desktop.txt`
- Test: `tests/test_config.py`, 运行 `pytest tests/ -q`

**Interfaces:**
- Consumes: 当前 `requirements.txt` 中的 8 个包
- Produces: 可 `pip install -e .` 安装，保留 `pytest -m "not integration"` 行为

- [ ] **Step 1: 编写 pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "uta"
version = "1.2.0"
description = "Universal Task Agent - 本地学习型 Agent 框架"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
authors = [
    {name = "UTA Team"},
]
keywords = ["agent", "llm", "rag", "desktop"]
classifiers = [
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]
dependencies = [
    "pytest>=8.0.0",
    "pandas>=2.0.0",
    "openpyxl>=3.1.0",
    "numpy>=2.0.0",
    "certifi>=2024.0.0",
    "fastapi>=0.115.0",
    "uvicorn>=0.30.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
desktop = [
    "pywebview>=5.0.0",
    "pyinstaller>=6.0.0",
]
dev = [
    "ruff>=0.5.0",
    "pytest-cov>=5.0.0",
]

[project.scripts]
uta = "main:main"
uta-api = "api.server:main"
uta-desktop = "desktop.app:main"

[tool.setuptools.packages.find]
include = ["api*", "core*", "desktop*", "llm*", "memory_providers*", "rag*", "search_providers*", "skills*", "tools*", "weather_providers*"]

[tool.pytest.ini_options]
markers = [
    "integration: 需要真实模型或网络的集成测试（默认跳过，手动 -m integration 运行）",
]
addopts = "-m 'not integration'"

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "W"]

[tool.ruff.lint.pydocstyle]
convention = "google"
```

- [ ] **Step 2: 删除 pytest.ini**

```bash
rm pytest.ini
```

- [ ] **Step 3: 更新 requirements.txt 为可编辑安装**

```text
-e .
```

- [ ] **Step 4: 更新 requirements-desktop.txt**

```text
-r requirements.txt
-e .[desktop]
```

- [ ] **Step 5: 运行测试确认无回归**

Run: `pytest tests/ -q`
Expected: `441 passed, 5 deselected`

- [ ] **Step 6: 验证可编辑安装**

Run: `.venv/bin/python -m pip install -e .`
Expected: 安装成功，无错误。

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml requirements.txt requirements-desktop.txt pytest.ini
git commit -m "chore: add pyproject.toml and unify project configuration"
```

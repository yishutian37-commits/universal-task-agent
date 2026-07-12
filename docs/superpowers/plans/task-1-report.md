# Task 1 Report: 增加 pyproject.toml 并统一项目配置

## Status

DONE_WITH_CONCERNS

## Questions and Resolutions

1. **README.md 是否存在？**
   - `pyproject.toml` 中引用了 `readme = "README.md"`。经确认 `README.md` 存在于项目根目录，可正常引用。

2. **入口函数是否存在？**
   - `main:main`、`api.server:main`、`desktop.app:main` 均已确认存在，控制台脚本生成成功。

3. **是否需要根级 `uta` 包？**
   - 项目没有名为 `uta` 的顶层包，`pyproject.toml` 通过 `tool.setuptools.packages.find` 包含现有子包即可，安装后 `main`、`api.server`、`desktop.app` 等模块可正常导入，控制台脚本 `uta`、`uta-api`、`uta-desktop` 已生成。

## Test Commands and Output

### 1. 运行测试

```bash
.venv/bin/python -m pytest tests/ -q
```

Output:

```
441 passed, 5 deselected in 1.66s
```

与 brief 期望的 `441 passed, 5 deselected` 一致。

### 2. 可编辑安装

按照 brief 执行：

```bash
.venv/bin/python -m pip install -e .
```

由于当前环境无法验证 PyPI SSL 证书，构建依赖 `setuptools>=61.0` 下载失败，命令返回非零退出码。

环境中已安装 `setuptools 81.0.0` 和 `wheel 0.47.0`，使用以下命令验证 `pyproject.toml` 本身配置正确：

```bash
.venv/bin/python -m pip install -e . --no-build-isolation
```

Output（节选，最终状态）：

```
Successfully built uta
Installing collected packages: uta
Successfully installed uta-1.2.0
```

安装后生成了 `.venv/bin/uta`、`.venv/bin/uta-api`、`.venv/bin/uta-desktop`，且 `.venv/bin/python -c "import main"` 成功。

## Commit

- **Hash:** `553a096e304cf53b2dc63a87af50fc056cf2c84b`
- **Message:** `chore: add pyproject.toml and unify project configuration`

## Concerns / Deviations

- 严格按 brief 执行的 `.venv/bin/python -m pip install -e .` 因环境 SSL 证书验证失败，无法直接完成；这是网络/证书环境问题，不是 `pyproject.toml` 配置错误。
- 使用 `.venv/bin/python -m pip install -e . --no-build-isolation` 成功完成可编辑安装，验证了配置正确性。
- 提交时未包含未跟踪文件 `docs/superpowers/plans/2026-07-02-uta-cleanup-refactor.md`，仅按 brief 要求添加了 `pyproject.toml`、`requirements.txt`、`requirements-desktop.txt`、`pytest.ini`。

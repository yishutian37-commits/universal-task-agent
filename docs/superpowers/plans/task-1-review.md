# Task 1 Review: 增加 pyproject.toml 并统一项目配置

## Spec Compliance Verdict

**✅ 基本符合**（存在一个环境导致的验证缺口，见下方 Important 问题）。

### 逐项核对

| 要求 | 状态 | 说明 |
|------|------|------|
| 新建 `pyproject.toml`，内容与 brief 一致 | ✅ | diff 与 brief 完全对应，TOML 解析正常 |
| 删除 `pytest.ini` | ✅ | 已删除，配置已迁移至 `[tool.pytest.ini_options]` |
| `requirements.txt` 改为 `-e .` | ✅ | 已更新 |
| `requirements-desktop.txt` 改为 `-r requirements.txt` + `-e .[desktop]` | ✅ | 已更新 |
| 运行 `pytest tests/ -q`，期望 `441 passed, 5 deselected` | ✅ | 实际：`441 passed, 5 deselected in 1.64s` |
| 运行 `.venv/bin/python -m pip install -e .`，期望成功 | ⚠️ | 因环境 SSL 证书验证失败，无法直接成功 |
| Commit 包含指定文件并正确命名 | ✅ | `553a096 chore: add pyproject.toml and unify project configuration` |

## Code Quality Verdict

**Approved**

- 变更范围极小，仅涉及构建/依赖配置，未触碰业务逻辑或外部接口。
- `pyproject.toml` 格式正确，`tomllib` 可正常解析。
- 生成的控制台脚本 `.venv/bin/uta`、`.venv/bin/uta-api`、`.venv/bin/uta-desktop` 已存在。
- `import main` 成功，`main.py` 可被已安装环境导入。

## Issues

### Critical

无。

### Important

1. **`pip install -e .` 未能在目标环境按 brief 原命令成功**
   - 现象：`Installing build dependencies` 阶段因 `SSLCertVerificationError` 无法从 PyPI 拉取 `setuptools>=61.0`，命令退出码非零。
   - 影响：brief 第 6 步的“ exact command success”未能直接验证。
   - 缓解：实施者使用 `--no-build-isolation` 成功完成可编辑安装，并验证 `uta-1.2.0` 安装成功、脚本生成、模块可导入。
   - 建议：解决当前环境 SSL 证书配置后，重新执行一次 `.venv/bin/python -m pip install -e .` 以补齐正式验证；或在项目文档中记录该环境限制及推荐安装方式。

### Minor

1. **`requirements-desktop.txt` diff 中 `-r requirements.txt` 前存在多余空格**
   - 不影响功能，仅格式整齐性问题。

2. **顶层模块 `main.py` 未在 `pyproject.toml` 中显式声明**
   - brief 仅要求 editable install，当前已可正常工作；若未来需要生成 wheel，建议补充 `py-modules = ["main"]`。

## Test Results

```bash
.venv/bin/python -m pytest tests/ -q
```

结果：

```
441 passed, 5 deselected in 1.64s
```

与 brief 预期一致。

## Summary

- **Spec Compliance:** ✅（配置内容完全匹配 brief；`pip install -e .` 的 exact success 因环境 SSL 问题未直接验证）
- **Code Quality:** Approved
- **Critical Issues:** 无
- **Important Issues:** 1 个（环境 SSL 导致 `pip install -e .` 严格命令未通过，已通过 `--no-build-isolation` 验证配置正确性）

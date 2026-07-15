#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON:-$ROOT/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="${PYTHON:-python3}"
fi

export PYINSTALLER_CONFIG_DIR="$ROOT/build/pyinstaller-cache"

echo "==> 检查版本一致性"
"$PYTHON_BIN" - <<'PY'
import importlib.metadata
import tomllib
from pathlib import Path

root = Path.cwd()
project_version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
installed_version = importlib.metadata.version("uta")
api_text = (root / "api" / "server.py").read_text(encoding="utf-8")
spec_text = (root / "desktop" / "build" / "uta_app.spec").read_text(encoding="utf-8")

checks = {
    "Python 安装元数据": installed_version,
    "API": project_version if f'version="{project_version}"' in api_text else "不一致",
    "Info.plist spec": project_version
    if f'"CFBundleShortVersionString": "{project_version}"' in spec_text
    and f'"CFBundleVersion": "{project_version}"' in spec_text
    else "不一致",
}
errors = [f"{name}={value}" for name, value in checks.items() if value != project_version]
if errors:
    raise SystemExit(
        f"版本不一致：项目={project_version}；" + "；".join(errors)
        + "。若仅安装元数据过期，请运行 .venv/bin/python -m pip install --no-deps -e ."
    )
print(f"版本一致：{project_version}")
PY

echo "==> 运行测试"
"$PYTHON_BIN" -m pytest -q

echo "==> 检查桌面依赖"
"$PYTHON_BIN" - <<'PY'
import importlib.util

missing = [
    name
    for name, module in {"pywebview": "webview", "pyinstaller": "PyInstaller"}.items()
    if importlib.util.find_spec(module) is None
]
if missing:
    raise SystemExit("缺少依赖：" + ", ".join(missing) + "；请先运行 .venv/bin/python -m pip install -r requirements-desktop.txt")
PY

echo "==> 构建 UTA Desktop.app"
"$PYTHON_BIN" -m PyInstaller desktop/build/uta_app.spec \
  --distpath dist \
  --workpath build/pyinstaller \
  --clean \
  --noconfirm

echo "==> 打包 zip"
ARCHIVE_PATH="dist/UTA Desktop-macos.zip"
rm -f "$ARCHIVE_PATH"
if command -v ditto >/dev/null 2>&1; then
  ditto -c -k --keepParent --norsrc --noextattr --noqtn --noacl \
    "dist/UTA Desktop.app" "$ARCHIVE_PATH"
else
  (cd dist && zip -qr "UTA Desktop-macos.zip" "UTA Desktop.app")
fi

echo "构建完成：dist/UTA Desktop.app"
echo "压缩包：dist/UTA Desktop-macos.zip"

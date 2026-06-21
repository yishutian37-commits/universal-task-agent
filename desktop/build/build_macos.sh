#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON:-$ROOT/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="${PYTHON:-python3}"
fi

export PYINSTALLER_CONFIG_DIR="$ROOT/build/pyinstaller-cache"

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
if command -v ditto >/dev/null 2>&1; then
  ditto -c -k --keepParent "dist/UTA Desktop.app" "dist/UTA Desktop-macos.zip"
else
  (cd dist && zip -qr "UTA Desktop-macos.zip" "UTA Desktop.app")
fi

echo "构建完成：dist/UTA Desktop.app"
echo "压缩包：dist/UTA Desktop-macos.zip"

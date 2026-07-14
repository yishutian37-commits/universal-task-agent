import multiprocessing
import sys

# PyInstaller 打包后防子进程无限重启（torch/numba spawn 问题）。
# 必须在任何重库 import 之前调用。
if getattr(sys, "frozen", False):
    multiprocessing.freeze_support()

from desktop.app import cli_main


if __name__ == "__main__":
    raise SystemExit(cli_main(debug=False))

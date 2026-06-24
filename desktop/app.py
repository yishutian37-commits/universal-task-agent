from __future__ import annotations

import multiprocessing
import sys

from desktop.api import DesktopAPI
from desktop.paths import resource_path


def main(debug: bool = False) -> None:
    # PyInstaller 打包后，torch/numba 等库可能 spawn 子进程。
    # 没有 freeze_support() 时，子进程会重新执行入口脚本，
    # 导致无限弹出新的应用窗口。这行必须在任何重库 import 之前。
    if getattr(sys, "frozen", False):
        multiprocessing.freeze_support()

    import webview

    api = DesktopAPI()
    frontend_path = resource_path("frontend", "index.html").resolve()
    window = webview.create_window(
        "UTA Desktop",
        frontend_path.as_uri(),
        js_api=api,
        width=1280,
        height=820,
        min_size=(960, 640),
    )
    api.bind_window(window)
    webview.start(debug=debug)


if __name__ == "__main__":
    main(debug=True)

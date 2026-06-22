from __future__ import annotations

from desktop.api import DesktopAPI
from desktop.paths import resource_path


def main(debug: bool = False) -> None:
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

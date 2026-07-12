import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

from desktop import app


def test_desktop_window_allows_text_selection(monkeypatch):
    calls = []
    fake_window = object()
    fake_webview = SimpleNamespace(
        create_window=lambda *args, **kwargs: calls.append((args, kwargs)) or fake_window,
        start=lambda **kwargs: None,
    )
    monkeypatch.setitem(sys.modules, "webview", fake_webview)
    monkeypatch.setattr(app.DesktopAPI, "bind_window", lambda self, window: None)

    app.main(debug=False)

    assert calls[0][1]["text_select"] is True


def test_desktop_bundle_version_matches_project_version():
    root = Path(__file__).resolve().parents[1]
    project_version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    spec_text = (root / "desktop" / "build" / "uta_app.spec").read_text(encoding="utf-8")

    assert f'"CFBundleShortVersionString": "{project_version}"' in spec_text
    assert f'"CFBundleVersion": "{project_version}"' in spec_text

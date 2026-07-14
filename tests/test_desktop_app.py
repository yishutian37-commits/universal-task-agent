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


def test_desktop_cli_version_reports_installed_version_without_opening_window(monkeypatch, capsys):
    launches = []
    monkeypatch.setattr(app, "distribution_version", lambda name: "1.11.0")
    monkeypatch.setattr(app, "main", lambda debug=False: launches.append(debug))

    exit_code = app.cli_main(["--version"], debug=False)

    assert exit_code == 0
    assert capsys.readouterr().out == "UTA Desktop 1.11.0\n"
    assert launches == []


def test_desktop_bundle_version_matches_project_version():
    root = Path(__file__).resolve().parents[1]
    project_version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    spec_text = (root / "desktop" / "build" / "uta_app.spec").read_text(encoding="utf-8")
    api_text = (root / "api" / "server.py").read_text(encoding="utf-8")

    assert f'"CFBundleShortVersionString": "{project_version}"' in spec_text
    assert f'"CFBundleVersion": "{project_version}"' in spec_text
    assert f'FastAPI(title="UTA API", version="{project_version}")' in api_text
    assert 'copy_metadata("uta")' in spec_text


def test_macos_archive_omits_metadata_that_breaks_clean_extraction_signatures():
    root = Path(__file__).resolve().parents[1]
    build_script = (root / "desktop" / "build" / "build_macos.sh").read_text(encoding="utf-8")

    for flag in ("--norsrc", "--noextattr", "--noqtn", "--noacl"):
        assert flag in build_script

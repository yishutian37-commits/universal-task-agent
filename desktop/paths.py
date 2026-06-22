from __future__ import annotations

import os
import sys
from pathlib import Path


def uta_home() -> Path:
    return Path(os.getenv("UTA_HOME", Path.home() / ".uta")).expanduser()


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resource_path(*parts: str) -> Path:
    bundled_root = getattr(sys, "_MEIPASS", None)
    if bundled_root is not None:
        candidate = Path(bundled_root).joinpath(*parts)
        if candidate.exists():
            return candidate

    root = project_root()
    if parts and parts[0] == "frontend":
        return root / "desktop" / Path(*parts)
    return root.joinpath(*parts)

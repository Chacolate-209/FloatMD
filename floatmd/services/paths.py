"""Application data paths (Windows LOCALAPPDATA / XDG on Linux)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "FloatMD"


def app_data_dir() -> Path:
    if sys.platform == "win32":
        root = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        path = Path(root) / APP_NAME
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        if xdg:
            path = Path(xdg) / "floatmd"
        else:
            path = Path.home() / ".local" / "share" / "floatmd"
    path.mkdir(parents=True, exist_ok=True)
    return path


def notes_dir() -> Path:
    path = app_data_dir() / "notes"
    path.mkdir(parents=True, exist_ok=True)
    (path / ".trash").mkdir(exist_ok=True)
    return path


def config_path() -> Path:
    return app_data_dir() / "config.json"

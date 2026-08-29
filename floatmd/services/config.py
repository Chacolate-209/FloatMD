"""JSON app config with atomic writes."""

from __future__ import annotations

import json
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from floatmd.services.paths import config_path, notes_dir


DEFAULT_CONFIG: dict[str, Any] = {
    "window": {
        "x": 120,
        "y": 80,
        "width": 480,
        "height": 640,
        "always_on_top": True,
    },
    "notes_dir": None,  # None → default from paths.notes_dir()
    "hotkey": "Ctrl+Alt+Space",
    "locale": "zh-CN",
    "ai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "temperature": 0.3,
        "timeout_ms": 60000,
    },
}


class AppConfig:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or config_path()
        self._data: dict[str, Any] = deepcopy(DEFAULT_CONFIG)
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self._data = deepcopy(DEFAULT_CONFIG)
            self.save()
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("config root must be object")
            self._data = _deep_merge(deepcopy(DEFAULT_CONFIG), raw)
        except (OSError, json.JSONDecodeError, ValueError):
            bak = self.path.with_suffix(".json.bak")
            try:
                self.path.replace(bak)
            except OSError:
                pass
            self._data = deepcopy(DEFAULT_CONFIG)
            self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(self._data, indent=2, ensure_ascii=False) + "\n"
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self.path.parent), prefix=".config.", suffix=".tmp"
        )
        try:
            with open(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
                fh.flush()
            Path(tmp_name).replace(self.path)
        except Exception:
            try:
                Path(tmp_name).unlink(missing_ok=True)
            except OSError:
                pass
            raise

    @property
    def data(self) -> dict[str, Any]:
        return self._data

    def get_window_geometry(self) -> tuple[int, int, int, int]:
        w = self._data["window"]
        return int(w["x"]), int(w["y"]), int(w["width"]), int(w["height"])

    def set_window_geometry(self, x: int, y: int, width: int, height: int) -> None:
        self._data["window"].update(
            {"x": int(x), "y": int(y), "width": int(width), "height": int(height)}
        )
        self.save()

    def always_on_top(self) -> bool:
        return bool(self._data["window"].get("always_on_top", True))

    def set_always_on_top(self, value: bool) -> None:
        self._data["window"]["always_on_top"] = bool(value)
        self.save()

    def resolve_notes_dir(self) -> Path:
        custom = self._data.get("notes_dir")
        if custom:
            path = Path(custom)
            path.mkdir(parents=True, exist_ok=True)
            (path / ".trash").mkdir(exist_ok=True)
            return path
        return notes_dir()


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    for key, value in overlay.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = value
    return base

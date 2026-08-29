"""Resolve UI fonts with CJK fallbacks (avoid tofu □ for Chinese)."""

from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase


# Prefer cross-platform faces that cover Latin + CJK when installed.
_UI_CANDIDATES = [
    "Noto Sans CJK SC",
    "Noto Sans CJK JP",
    "Noto Sans SC",
    "Source Han Sans SC",
    "Source Han Sans CN",
    "WenQuanYi Micro Hei",
    "WenQuanYi Zen Hei",
    "Microsoft YaHei UI",
    "Microsoft YaHei",
    "PingFang SC",
    "Hiragino Sans GB",
    "Segoe UI",
    "Sans Serif",
]

_MONO_CANDIDATES = [
    "Noto Sans Mono CJK SC",
    "Sarasa Mono SC",
    "Cascadia Code",
    "Consolas",
    "Courier New",
    "Monospace",
]


def _first_available(candidates: list[str]) -> str:
    available = set(QFontDatabase.families())
    for name in candidates:
        if name in available:
            return name
        # Some systems report slightly different family strings
        for fam in available:
            if name.lower() in fam.lower() or fam.lower() in name.lower():
                return fam
    return candidates[-1]


def ui_font(point_size: int = 12, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont(_first_available(_UI_CANDIDATES), point_size)
    font.setWeight(weight)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    return font


def mono_font(point_size: int = 11) -> QFont:
    font = QFont(_first_available(_MONO_CANDIDATES), point_size)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setFixedPitch(True)
    return font


def apply_app_font(app) -> str:  # noqa: ANN001
    """Set application-wide UI font; returns chosen family name."""
    font = ui_font(12)
    app.setFont(font)
    return font.family()

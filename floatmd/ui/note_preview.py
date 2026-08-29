"""Beautified Markdown preview via QWebEngineView (local assets)."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QUrl, Signal, Slot
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

PREVIEW_DIR = Path(__file__).resolve().parent.parent / "resources" / "preview"
SHELL_HTML = PREVIEW_DIR / "shell.html"


def webengine_available() -> bool:
    try:
        from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401

        return True
    except Exception:
        return False


class NotePreview(QWidget):
    """Display-mode pane. Uses WebEngine when available; otherwise a plain fallback."""

    ready = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("notePreview")
        self._pending: str | None = None
        self._page_ready = False
        self._view = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if webengine_available() and SHELL_HTML.is_file():
            from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
            from PySide6.QtWebEngineWidgets import QWebEngineView

            self._view = QWebEngineView(self)
            page = QWebEnginePage(self._view)
            settings = page.settings()
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
            self._view.setPage(page)
            self._view.loadFinished.connect(self._on_load_finished)
            layout.addWidget(self._view)
            self._view.load(QUrl.fromLocalFile(str(SHELL_HTML.resolve())))
        else:
            self._fallback = QLabel(
                "预览引擎不可用（缺少 QtWebEngine 或本地资源）。\n"
                "请安装系统依赖后重试；编辑模式仍可正常使用。"
            )
            self._fallback.setWordWrap(True)
            self._fallback.setObjectName("placeholder")
            layout.addWidget(self._fallback)

    def set_markdown(self, text: str) -> None:
        self._pending = text
        if self._view is None:
            return
        if not self._page_ready:
            return
        self._push(text)

    def _push(self, text: str) -> None:
        assert self._view is not None
        payload = json.dumps(text, ensure_ascii=False)
        js = f"window.setMarkdown && window.setMarkdown({payload});"
        self._view.page().runJavaScript(js)

    @Slot(bool)
    def _on_load_finished(self, ok: bool) -> None:
        if not ok or self._view is None:
            return

        def _check(ready: object) -> None:
            self._page_ready = bool(ready)
            self.ready.emit()
            if self._pending is not None and self._page_ready:
                self._push(self._pending)

        self._view.page().runJavaScript(
            "!!(window.__floatmd_ready && window.setMarkdown)",
            _check,
        )

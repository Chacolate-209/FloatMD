"""Compact floating title chrome — short labels + icons."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QWidget,
)


def _icon_btn(text: str, tip: str, *, checkable: bool = False) -> QToolButton:
    btn = QToolButton()
    btn.setText(text)
    btn.setToolTip(tip)
    btn.setAutoRaise(True)
    btn.setCheckable(checkable)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


class TitleBar(QFrame):
    pin_toggled = Signal(bool)
    hide_requested = Signal()
    close_requested = Signal()
    drag_moved = Signal(QPoint)
    note_menu_requested = Signal()
    mode_changed = Signal(str)  # "edit" | "display"
    ai_toggled = Signal()
    ocr_toggled = Signal()
    settings_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("titleBar")
        self.setFixedHeight(34)
        self._drag_origin: QPoint | None = None
        self._dragging = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 4, 2)
        layout.setSpacing(3)

        self.note_btn = _icon_btn("笔记 ▾", "切换 / 新建笔记")
        self.note_btn.setObjectName("noteSwitcher")
        self.note_btn.setMinimumWidth(88)
        self.note_btn.setMaximumWidth(140)
        self.note_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.note_btn.clicked.connect(self.note_menu_requested.emit)
        layout.addWidget(self.note_btn)

        self.dirty_label = QLabel("")
        self.dirty_label.setObjectName("hintLabel")
        self.dirty_label.setFixedWidth(8)
        layout.addWidget(self.dirty_label)

        layout.addStretch(1)

        mode_wrap = QFrame()
        mode_wrap.setObjectName("modeGroup")
        mode_layout = QHBoxLayout(mode_wrap)
        mode_layout.setContentsMargins(2, 1, 2, 1)
        mode_layout.setSpacing(0)

        self.mode_edit = _icon_btn("写", "编辑 (Ctrl+E)", checkable=True)
        self.mode_edit.setObjectName("modeEdit")
        self.mode_edit.setChecked(True)
        self.mode_display = _icon_btn("阅", "预览 (Ctrl+E)", checkable=True)
        self.mode_display.setObjectName("modeDisplay")
        self.mode_edit.clicked.connect(lambda: self._set_mode("edit"))
        self.mode_display.clicked.connect(lambda: self._set_mode("display"))
        mode_layout.addWidget(self.mode_edit)
        mode_layout.addWidget(self.mode_display)
        layout.addWidget(mode_wrap)

        self.ai_btn = _icon_btn("AI", "AI 面板 (Ctrl+Shift+A)", checkable=True)
        self.ai_btn.clicked.connect(self.ai_toggled.emit)
        layout.addWidget(self.ai_btn)

        self.ocr_btn = _icon_btn("OCR", "OCR 面板 (Ctrl+Shift+O)", checkable=True)
        self.ocr_btn.clicked.connect(self.ocr_toggled.emit)
        layout.addWidget(self.ocr_btn)

        self.pin_btn = _icon_btn("📌", "置顶", checkable=True)
        self.pin_btn.setObjectName("pinBtn")
        self.pin_btn.setChecked(True)
        self.pin_btn.toggled.connect(self.pin_toggled.emit)
        layout.addWidget(self.pin_btn)

        self.settings_btn = _icon_btn("⚙", "设置 (Ctrl+,)")
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        layout.addWidget(self.settings_btn)

        self.hide_btn = _icon_btn("—", "隐藏")
        self.hide_btn.setObjectName("winHide")
        self.hide_btn.clicked.connect(self.hide_requested.emit)
        layout.addWidget(self.hide_btn)

        self.close_btn = _icon_btn("✕", "退出")
        self.close_btn.setObjectName("winClose")
        self.close_btn.clicked.connect(self.close_requested.emit)
        layout.addWidget(self.close_btn)

    def set_note_title(self, title: str) -> None:
        # Elide by pixel width so CJK isn't crushed into "欢…"
        metrics = self.note_btn.fontMetrics()
        avail = max(60, self.note_btn.maximumWidth() - 28)
        elided = metrics.elidedText(title, Qt.TextElideMode.ElideRight, avail)
        self.note_btn.setText(f"{elided} ▾")
        self.note_btn.setToolTip(title)

    def set_dirty(self, dirty: bool) -> None:
        self.dirty_label.setText("•" if dirty else "")
        self.dirty_label.setToolTip("未保存" if dirty else "")

    def set_ai_open(self, open_: bool) -> None:
        self.ai_btn.blockSignals(True)
        self.ai_btn.setChecked(open_)
        self.ai_btn.blockSignals(False)

    def set_ocr_open(self, open_: bool) -> None:
        self.ocr_btn.blockSignals(True)
        self.ocr_btn.setChecked(open_)
        self.ocr_btn.blockSignals(False)

    def _set_mode(self, mode: str) -> None:
        self.mode_edit.setChecked(mode == "edit")
        self.mode_display.setChecked(mode == "display")
        self.mode_changed.emit(mode)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.position().toPoint())
            if child is None or child is self or isinstance(child, QLabel):
                self._dragging = True
                self._drag_origin = event.globalPosition().toPoint()
                event.accept()
                return
            if not isinstance(child, QAbstractButton) and not isinstance(child, QToolButton):
                self._dragging = True
                self._drag_origin = event.globalPosition().toPoint()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging and self._drag_origin is not None:
            delta = event.globalPosition().toPoint() - self._drag_origin
            self._drag_origin = event.globalPosition().toPoint()
            self.drag_moved.emit(delta)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._dragging = False
        self._drag_origin = None
        super().mouseReleaseEvent(event)

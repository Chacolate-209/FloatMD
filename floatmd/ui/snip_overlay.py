"""Fullscreen translucent overlay for region screenshot (drag to select)."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QMouseEvent, QPainter, QPen, QScreen
from PySide6.QtWidgets import QWidget


class SnipOverlay(QWidget):
    """Covers virtual desktop; user drags a rectangle. Esc cancels."""

    region_selected = Signal(QRect)  # global coordinates
    cancelled = Signal()

    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)

        self._origin: QPoint | None = None
        self._current: QPoint | None = None
        self._selecting = False

        # Cover all screens' virtual geometry
        virtual = QRect()
        for screen in QGuiApplication.screens():
            virtual = virtual.united(screen.geometry())
        if virtual.isNull():
            screen = QGuiApplication.primaryScreen()
            virtual = screen.geometry() if screen else QRect(0, 0, 800, 600)
        self.setGeometry(virtual)

    def paintEvent(self, event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(15, 40, 35, 120))
        sel = self._selection_local()
        if sel is not None and sel.width() > 2 and sel.height() > 2:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(sel, Qt.GlobalColor.transparent)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.setPen(QPen(QColor("#0D9488"), 2))
            painter.drawRect(sel.adjusted(0, 0, -1, -1))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(
                sel.bottomLeft() + QPoint(4, 16),
                f"{sel.width()} × {sel.height()}",
            )
        else:
            painter.setPen(QColor("#ffffff"))
            painter.drawText(20, 40, "拖拽选择区域 · Esc 取消")

    def _selection_local(self) -> QRect | None:
        if self._origin is None or self._current is None:
            return None
        return QRect(self._origin, self._current).normalized()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._selecting = True
            self._origin = event.position().toPoint()
            self._current = self._origin
            self.update()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._selecting:
            self._current = event.position().toPoint()
            self.update()
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._selecting:
            self._selecting = False
            self._current = event.position().toPoint()
            local = self._selection_local()
            self.hide()
            if local and local.width() >= 4 and local.height() >= 4:
                top_left = self.mapToGlobal(local.topLeft())
                global_rect = QRect(top_left, local.size())
                self.region_selected.emit(global_rect)
            else:
                self.cancelled.emit()
            self.close()
            event.accept()

    def keyPressEvent(self, event) -> None:  # noqa: ANN001
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            self.cancelled.emit()
            self.close()
            event.accept()
            return
        super().keyPressEvent(event)


def capture_region(global_rect: QRect) -> bytes:
    """Capture a global screen region as PNG bytes using mss."""
    import io

    from PIL import Image
    import mss

    # mss uses physical pixels; Qt may be logical — scale via devicePixelRatio of containing screen
    screen = QGuiApplication.screenAt(global_rect.center())
    dpr = screen.devicePixelRatio() if screen is not None else 1.0

    left = int(global_rect.x() * dpr)
    top = int(global_rect.y() * dpr)
    width = max(1, int(global_rect.width() * dpr))
    height = max(1, int(global_rect.height() * dpr))

    with mss.mss() as sct:
        monitor = {"left": left, "top": top, "width": width, "height": height}
        shot = sct.grab(monitor)
        img = Image.frombytes("RGB", shot.size, shot.rgb)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

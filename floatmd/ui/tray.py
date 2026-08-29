"""System tray icon and menu."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget


def make_app_icon(size: int = 64) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#0F6B4C"))
    painter.setPen(QColor("#0F6B4C"))
    margin = size // 10
    painter.drawRoundedRect(margin, margin, size - 2 * margin, size - 2 * margin, 12, 12)
    painter.setPen(QColor("#ffffff"))
    font = painter.font()
    font.setBold(True)
    font.setPixelSize(size // 3)
    painter.setFont(font)
    painter.drawText(
        pix.rect(),
        int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
        "M",
    )
    painter.end()
    return QIcon(pix)


class AppTray(QSystemTrayIcon):
    def __init__(self, window: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._window = window
        self.setIcon(make_app_icon())
        self.setToolTip("FloatMD")

        menu = QMenu()
        show_action = QAction("显示 / 隐藏", menu)
        show_action.triggered.connect(self._toggle)
        menu.addAction(show_action)

        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

    def _toggle(self) -> None:
        toggle = getattr(self._window, "toggle_visibility", None)
        if callable(toggle):
            toggle()
        elif self._window.isVisible():
            self._window.hide()
        else:
            self._window.show()
            self._window.raise_()
            self._window.activateWindow()

    def _quit(self) -> None:
        persist = getattr(self._window, "persist_geometry", None)
        if callable(persist):
            persist()
        from PySide6.QtWidgets import QApplication

        QApplication.instance().quit()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._toggle()

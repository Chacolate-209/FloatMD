"""FloatMD application entrypoint."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QSharedMemory, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from floatmd.services.config import AppConfig
from floatmd.ui.fonts import apply_app_font
from floatmd.ui.main_window import MainWindow
from floatmd.ui.tray import AppTray, make_app_icon


SINGLE_INSTANCE_KEY = "FloatMD-single-instance-v1"


def _acquire_single_instance() -> QSharedMemory | None:
    """Return shared memory segment if we are the primary instance, else None."""
    mem = QSharedMemory(SINGLE_INSTANCE_KEY)
    if mem.attach():
        # Another instance holds the segment
        mem.detach()
        return None
    if not mem.create(1):
        # Stale segment from crash — try again
        mem.attach()
        mem.detach()
        if not mem.create(1):
            return None
    return mem


def _ensure_webengine_flags() -> None:
    """Chromium refuses to start as root without --no-sandbox (dev / CI)."""
    import os

    flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    extras: list[str] = []
    if hasattr(os, "geteuid") and os.geteuid() == 0 and "--no-sandbox" not in flags:
        extras.append("--no-sandbox")
    if "--disable-gpu" not in flags and sys.platform.startswith("linux"):
        # Avoid noisy Vulkan init failures on minimal Linux desktops.
        extras.append("--disable-gpu")
    if extras:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (flags + " " + " ".join(extras)).strip()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    _ensure_webengine_flags()
    # Import WebEngine before QApplication so Chromium initializes cleanly.
    try:
        from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
    except Exception:
        pass

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(argv)
    app.setApplicationName("FloatMD")
    app.setOrganizationName("FloatMD")
    app.setWindowIcon(make_app_icon())
    app.setQuitOnLastWindowClosed(False)
    family = apply_app_font(app)
    print(f"[FloatMD] UI font: {family}", flush=True)

    shared = _acquire_single_instance()
    if shared is None:
        QMessageBox.information(
            None,
            "FloatMD",
            "FloatMD 已在运行。请从系统托盘打开窗口。",
        )
        return 0

    # Keep reference so segment lives for process lifetime
    app._floatmd_shared = shared  # type: ignore[attr-defined]

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.warning(
            None,
            "FloatMD",
            "系统托盘不可用。窗口关闭时将直接退出。",
        )
        app.setQuitOnLastWindowClosed(True)

    config = AppConfig()
    window = MainWindow(config)
    tray = AppTray(window)
    tray.show()
    app._floatmd_tray = tray  # type: ignore[attr-defined]

    # Debounced geometry persist while moving/resizing via title-bar drag
    save_timer = QTimer()
    save_timer.setSingleShot(True)
    save_timer.setInterval(400)
    save_timer.timeout.connect(window.persist_geometry)
    window.geometry_changed.connect(lambda: save_timer.start())

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

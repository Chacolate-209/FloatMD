"""Frameless floating main window."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QKeySequence, QMouseEvent, QShortcut
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from floatmd.services.config import AppConfig
from floatmd.services.notes_store import NotesStore
from floatmd.ui.ai_drawer import AiDrawer, ContextChunk, RewriteApply, RewriteSnapshot, hash_text
from floatmd.ui.note_editor import NoteEditor
from floatmd.ui.note_preview import NotePreview
from floatmd.ui.note_switcher import NoteSwitcherPopup
from floatmd.ui.ocr_drawer import OcrDrawer
from floatmd.ui.settings_dialog import SettingsDialog
from floatmd.ui.snip_overlay import SnipOverlay, capture_region
from floatmd.ui.theme import APP_QSS
from floatmd.ui.title_bar import TitleBar

RESIZE_MARGIN = 6
MIN_WIDTH = 320
MIN_HEIGHT = 240


class MainWindow(QMainWindow):
    geometry_changed = Signal()

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.store = NotesStore(config.resolve_notes_dir())
        self.current_name: str | None = None
        self._dirty = False
        self._loading = False

        self.setObjectName("mainWindow")
        self.setWindowTitle("FloatMD")
        self.setMinimumSize(QSize(MIN_WIDTH, MIN_HEIGHT))

        self._resize_edges = Qt.Edge(0)
        self._resizing = False
        self._resize_origin = QPoint()
        self._resize_geom = QRect()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Window
            | Qt.WindowType.WindowSystemMenuHint
        )
        self.setMouseTracking(True)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(1, 1, 1, 1)
        root_layout.setSpacing(0)

        self.title_bar = TitleBar()
        root_layout.addWidget(self.title_bar)

        self.stack = QStackedWidget()
        self.editor = NoteEditor()
        self.preview = NotePreview()
        self.stack.addWidget(self.editor)
        self.stack.addWidget(self.preview)
        root_layout.addWidget(self.stack, 1)

        self.status_bar = QLabel("写 · 就绪")
        self.status_bar.setObjectName("statusBar")
        self.status_bar.setFixedHeight(22)
        self.status_bar.setToolTip("Ctrl+E 写/阅 · Ctrl+Shift+A AI · Ctrl+Shift+O OCR")
        root_layout.addWidget(self.status_bar)

        self.ai_drawer = AiDrawer(config)
        root_layout.addWidget(self.ai_drawer)

        self.ocr_drawer = OcrDrawer()
        root_layout.addWidget(self.ocr_drawer)

        self.switcher = NoteSwitcherPopup(self)
        self._snip: SnipOverlay | None = None

        self._autosave = QTimer(self)
        self._autosave.setSingleShot(True)
        self._autosave.setInterval(600)
        self._autosave.timeout.connect(self.flush_save)

        self.title_bar.drag_moved.connect(self._on_drag)
        self.title_bar.pin_toggled.connect(self._on_pin)
        self.title_bar.hide_requested.connect(self.hide_to_tray)
        self.title_bar.close_requested.connect(self.close)
        self.title_bar.note_menu_requested.connect(self._open_switcher)
        self.title_bar.mode_changed.connect(self._on_mode)
        self.title_bar.ai_toggled.connect(self._toggle_ai)
        self.title_bar.ocr_toggled.connect(self._toggle_ocr)
        self.title_bar.settings_requested.connect(self._open_settings)
        self.editor.content_modified.connect(self._on_editor_modified)
        self.switcher.note_chosen.connect(self.open_note)
        self.switcher.create_requested.connect(self._create_note)
        self.ai_drawer.add_selection_requested.connect(self._ai_add_selection)
        self.ai_drawer.rewrite_requested.connect(self._ai_start_rewrite)
        self.ai_drawer.apply_rewrite.connect(self._ai_apply_rewrite)
        self.ai_drawer.apply_format.connect(self._ai_apply_format)
        self.ai_drawer.request_full_note.connect(self._ai_format_note)
        self.ai_drawer.open_settings.connect(self._open_settings)
        self.ai_drawer.collapsed.connect(lambda: self.title_bar.set_ai_open(False))
        self.ocr_drawer.snip_requested.connect(self._start_snip)
        self.ocr_drawer.insert_text.connect(self._ocr_insert)
        self.ocr_drawer.append_text.connect(self._ocr_append)
        self.ocr_drawer.collapsed.connect(lambda: self.title_bar.set_ocr_open(False))

        self._install_shortcuts()
        self.setStyleSheet(APP_QSS)
        self._restore_geometry()
        self._apply_always_on_top(self.config.always_on_top())
        self.title_bar.pin_btn.setChecked(self.config.always_on_top())

        self._bootstrap_note()
        self._set_status("就绪")

    def _install_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+E"), self, self._toggle_mode)
        QShortcut(QKeySequence("Ctrl+Shift+A"), self, self._toggle_ai)
        QShortcut(QKeySequence("Ctrl+Shift+O"), self, self._toggle_ocr)
        QShortcut(QKeySequence("Ctrl+,"), self, self._open_settings)
        QShortcut(QKeySequence("Ctrl+S"), self, lambda: self.flush_save() and self._set_status("已保存"))
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._on_escape)

    def _toggle_mode(self) -> None:
        if self.stack.currentWidget() is self.editor:
            self.title_bar._set_mode("display")
        else:
            self.title_bar._set_mode("edit")

    def _on_escape(self) -> None:
        if self.ai_drawer.isVisible() or self.ocr_drawer.isVisible():
            self.ai_drawer.collapse()
            self.ocr_drawer.collapse()
            self.title_bar.set_ai_open(False)
            self.title_bar.set_ocr_open(False)
            return
        self.hide_to_tray()

    def _set_status(self, text: str) -> None:
        mode = "写" if self.stack.currentWidget() is self.editor else "阅"
        note = self.current_name or ""
        if len(note) > 18:
            note = note[:16] + "…"
        # Keep short; full detail in tooltip
        self.status_bar.setText(f"{mode} · {text}")
        self.status_bar.setToolTip(f"{text} · {self.current_name or ''}")

    def _bootstrap_note(self) -> None:
        notes = self.store.list_notes()
        if notes:
            self.open_note(notes[0].name)
        else:
            meta = self.store.create("欢迎")
            self.store.write(
                meta.name,
                "# 欢迎使用 FloatMD\n\n"
                "- 顶栏点**笔记名**可切换 / 新建\n"
                "- **编辑**写 Markdown，**显示**看美化预览\n"
                "- 公式示例：$E=mc^2$\n\n"
                "```python\n"
                "print('hello floatmd')\n"
                "```\n\n"
                "```mermaid\n"
                "graph LR\n"
                "  Edit --> Display\n"
                "  Display --> Notes\n"
                "```\n\n"
                "> 选中几行 → 顶栏 **AI** →「加入选区」→ **解释** / **改写**\n",
            )
            self.open_note(meta.name)

    def open_note(self, name: str) -> None:
        if self.current_name == name and not self._dirty:
            return
        if not self.flush_save():
            return
        try:
            text = self.store.read(name)
        except (OSError, ValueError, FileNotFoundError) as exc:
            QMessageBox.warning(self, "FloatMD", f"无法打开笔记：{exc}")
            return
        self._loading = True
        self.current_name = name
        self.editor.setPlainText(text)
        self._loading = False
        self._dirty = False
        self.title_bar.set_dirty(False)
        if self.stack.currentWidget() is self.preview:
            self.preview.set_markdown(text)
        title = next(
            (n.title for n in self.store.list_notes() if n.name == name),
            name,
        )
        self.title_bar.set_note_title(title)
        self.setWindowTitle(f"FloatMD — {title}")
        self._set_status("就绪")

    def _create_note(self) -> None:
        if not self.flush_save():
            return
        meta = self.store.create()
        self.switcher.hide()
        self.open_note(meta.name)

    def _open_switcher(self) -> None:
        notes = self.store.list_notes()
        self.switcher.set_notes(notes, self.current_name)
        pos = self.title_bar.note_btn.mapToGlobal(QPoint(0, self.title_bar.note_btn.height()))
        self.switcher.popup_at(pos)

    def _on_mode(self, mode: str) -> None:
        if mode == "edit":
            self.stack.setCurrentWidget(self.editor)
            self._set_status("就绪")
            self.editor.setFocus()
        else:
            self.flush_save()
            self.preview.set_markdown(self.editor.toPlainText())
            self.stack.setCurrentWidget(self.preview)
            self._set_status("预览")

    def _toggle_ai(self) -> None:
        if self.stack.currentWidget() is not self.editor:
            self.title_bar._set_mode("edit")
        if self.ai_drawer.isVisible():
            self.ai_drawer.collapse()
            self.title_bar.set_ai_open(False)
        else:
            self.ocr_drawer.collapse()
            self.title_bar.set_ocr_open(False)
            self.ai_drawer.expand()
            self.title_bar.set_ai_open(True)
            self.editor.setFocus()
            self._set_status("AI")

    def _toggle_ocr(self) -> None:
        if self.ocr_drawer.isVisible():
            self.ocr_drawer.collapse()
            self.title_bar.set_ocr_open(False)
        else:
            self.ai_drawer.collapse()
            self.title_bar.set_ai_open(False)
            self.ocr_drawer.expand()
            self.title_bar.set_ocr_open(True)
            self._set_status("OCR")

    def _start_snip(self) -> None:
        # Hide float so it does not cover the capture target
        was_visible = self.isVisible()
        self.hide()

        def restore() -> None:
            if was_visible:
                self.show_from_tray()

        overlay = SnipOverlay()
        self._snip = overlay

        def on_region(rect) -> None:  # noqa: ANN001
            restore()
            try:
                png = capture_region(rect)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "OCR", f"截屏失败：{exc}")
                return
            self.ocr_drawer.expand()
            self.ocr_drawer.recognize_png(png)

        def on_cancel() -> None:
            restore()

        overlay.region_selected.connect(on_region)
        overlay.cancelled.connect(on_cancel)
        # Slight delay so our window finishes hiding before overlay grabs
        QTimer.singleShot(150, overlay.show)

    def _ocr_insert(self, text: str) -> None:
        if self.stack.currentWidget() is not self.editor:
            self.title_bar._set_mode("edit")
        self.editor.textCursor().insertText(text)
        self._dirty = True
        self.flush_save()

    def _ocr_append(self, text: str) -> None:
        if self.stack.currentWidget() is not self.editor:
            self.title_bar._set_mode("edit")
        cursor = self.editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        if not self.editor.toPlainText().endswith("\n") and self.editor.toPlainText():
            cursor.insertText("\n")
        cursor.insertText(text)
        self.editor.setTextCursor(cursor)
        self._dirty = True
        self.flush_save()

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.config, self)
        dlg.exec()

    def _ai_add_selection(self) -> None:
        if self.stack.currentWidget() is not self.editor:
            self.title_bar._set_mode("edit")
        start, end, _sel = self.editor.selected_line_range()
        text = self.editor.get_line_range_text(start, end)
        if not text.strip():
            QMessageBox.information(self, "AI", "请先在编辑器中选中一些文字。")
            return
        self.ai_drawer.add_chunk(ContextChunk(start, end, text))
        self.ai_drawer.expand()

    def _ai_start_rewrite(self) -> None:
        """Snapshot Lx–Ly at rewrite click, then start the worker."""
        if self.stack.currentWidget() is not self.editor:
            self.title_bar._set_mode("edit")
        start, end, _ = self.editor.selected_line_range()
        text = self.editor.get_line_range_text(start, end)
        if not text.strip():
            QMessageBox.information(self, "AI", "请先选中要改写的行（可点行号多选）。")
            return
        # Keep the target highlighted while the request runs
        self.editor.select_line_range(start, end)
        snap = RewriteSnapshot.from_range(start, end, text)
        self.ai_drawer.expand()
        self.title_bar.set_ai_open(True)
        self.ai_drawer.begin_rewrite(snap)
        self._set_status(f"改写 {snap.label()}")

    def _ai_apply_rewrite(self, payload: object) -> None:
        if not isinstance(payload, RewriteApply):
            QMessageBox.warning(self, "AI", "写回数据无效。")
            return
        if self.stack.currentWidget() is not self.editor:
            self.title_bar._set_mode("edit")

        snap = payload.snapshot
        current = self.editor.get_line_range_text(snap.start_line, snap.end_line)
        if hash_text(current) != snap.text_hash:
            QMessageBox.warning(
                self,
                "AI",
                f"{snap.label()} 已变动，取消自动写回。结果仍在 AI 面板，可手动粘贴。",
            )
            return
        try:
            self.editor.replace_line_range(snap.start_line, snap.end_line, payload.content)
        except ValueError as exc:
            QMessageBox.warning(self, "AI", f"写回失败：{exc}")
            return
        self._dirty = True
        self.title_bar.set_dirty(True)
        self.flush_save()
        self._set_status(f"已写回 {snap.label()}")

    def _ai_format_note(self) -> None:
        if self.stack.currentWidget() is not self.editor:
            self.title_bar._set_mode("edit")
        self.ai_drawer.expand()
        self.title_bar.set_ai_open(True)
        self.ai_drawer.begin_format(self.editor.toPlainText())

    def _ai_apply_format(self, content: str) -> None:
        if self.stack.currentWidget() is not self.editor:
            self.title_bar._set_mode("edit")
        self.editor.setPlainText(content)
        self._dirty = True
        self.title_bar.set_dirty(True)
        self.flush_save()
        self._set_status("已排版")

    def _on_editor_modified(self) -> None:
        if self._loading:
            return
        self._dirty = True
        self.title_bar.set_dirty(True)
        self._autosave.start()

    def flush_save(self) -> bool:
        if not self._dirty or not self.current_name:
            return True
        try:
            self.store.write(self.current_name, self.editor.toPlainText())
            self._dirty = False
            self.title_bar.set_dirty(False)
            title = next(
                (n.title for n in self.store.list_notes() if n.name == self.current_name),
                self.current_name,
            )
            self.title_bar.set_note_title(title)
            self._set_status("已存")
            return True
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "FloatMD", f"保存失败：{exc}")
            return False

    def _restore_geometry(self) -> None:
        x, y, w, h = self.config.get_window_geometry()
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            w = max(MIN_WIDTH, min(w, avail.width()))
            h = max(MIN_HEIGHT, min(h, avail.height()))
            x = min(max(avail.x(), x), avail.x() + avail.width() - 40)
            y = min(max(avail.y(), y), avail.y() + avail.height() - 40)
        self.setGeometry(x, y, w, h)

    def persist_geometry(self) -> None:
        g = self.geometry()
        self.config.set_window_geometry(g.x(), g.y(), g.width(), g.height())

    def hide_to_tray(self) -> None:
        self.flush_save()
        self.persist_geometry()
        self.hide()

    def show_from_tray(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def toggle_visibility(self) -> None:
        if self.isVisible():
            self.hide_to_tray()
        else:
            self.show_from_tray()

    def _on_drag(self, delta: QPoint) -> None:
        self.move(self.pos() + delta)

    def _on_pin(self, pinned: bool) -> None:
        self.config.set_always_on_top(pinned)
        self._apply_always_on_top(pinned)

    def _apply_always_on_top(self, pinned: bool) -> None:
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, pinned)
        if self.isVisible():
            self.show()

    def _hit_resize_edges(self, pos: QPoint) -> Qt.Edge:
        rect = self.rect()
        edges = Qt.Edge(0)
        if pos.x() <= RESIZE_MARGIN:
            edges |= Qt.Edge.LeftEdge
        if pos.x() >= rect.width() - RESIZE_MARGIN:
            edges |= Qt.Edge.RightEdge
        if pos.y() <= RESIZE_MARGIN:
            edges |= Qt.Edge.TopEdge
        if pos.y() >= rect.height() - RESIZE_MARGIN:
            edges |= Qt.Edge.BottomEdge
        return edges

    def _update_cursor(self, edges: Qt.Edge) -> None:
        if edges & Qt.Edge.LeftEdge and edges & Qt.Edge.TopEdge:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edges & Qt.Edge.RightEdge and edges & Qt.Edge.BottomEdge:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edges & Qt.Edge.RightEdge and edges & Qt.Edge.TopEdge:
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif edges & Qt.Edge.LeftEdge and edges & Qt.Edge.BottomEdge:
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif edges & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edges & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.unsetCursor()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            edges = self._hit_resize_edges(event.position().toPoint())
            if edges:
                self._resizing = True
                self._resize_edges = edges
                self._resize_origin = event.globalPosition().toPoint()
                self._resize_geom = self.geometry()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._resizing:
            self._perform_resize(event.globalPosition().toPoint())
            event.accept()
            return
        self._update_cursor(self._hit_resize_edges(event.position().toPoint()))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._resizing:
            self._resizing = False
            self._resize_edges = Qt.Edge(0)
            self.persist_geometry()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _perform_resize(self, global_pos: QPoint) -> None:
        delta = global_pos - self._resize_origin
        geom = QRect(self._resize_geom)
        if self._resize_edges & Qt.Edge.LeftEdge:
            new_x = geom.x() + delta.x()
            new_w = geom.width() - delta.x()
            if new_w >= MIN_WIDTH:
                geom.setX(new_x)
                geom.setWidth(new_w)
        if self._resize_edges & Qt.Edge.RightEdge:
            new_w = geom.width() + delta.x()
            if new_w >= MIN_WIDTH:
                geom.setWidth(new_w)
        if self._resize_edges & Qt.Edge.TopEdge:
            new_y = geom.y() + delta.y()
            new_h = geom.height() - delta.y()
            if new_h >= MIN_HEIGHT:
                geom.setY(new_y)
                geom.setHeight(new_h)
        if self._resize_edges & Qt.Edge.BottomEdge:
            new_h = geom.height() + delta.y()
            if new_h >= MIN_HEIGHT:
                geom.setHeight(new_h)
        self.setGeometry(geom)

    def moveEvent(self, event) -> None:  # noqa: ANN001
        super().moveEvent(event)
        self.geometry_changed.emit()

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        self.geometry_changed.emit()

    def closeEvent(self, event) -> None:  # noqa: ANN001
        if not self.flush_save():
            event.ignore()
            return
        self.persist_geometry()
        super().closeEvent(event)

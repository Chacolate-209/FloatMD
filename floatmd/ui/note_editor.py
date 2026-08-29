"""Plain-text Markdown editor with line-number gutter."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPalette, QTextCursor, QTextFormat
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from floatmd.ui.fonts import mono_font


class LineNumberArea(QWidget):
    """Gutter: click / drag line numbers to select whole lines (VS Code–like)."""

    def __init__(self, editor: "NoteEditor") -> None:
        super().__init__(editor)
        self._editor = editor
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setMouseTracking(True)
        self.setToolTip("点击选行 · 拖动多选 · Shift+点击扩展")
        self._anchor_line: int | None = None

    def sizeHint(self) -> QSize:
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:  # noqa: ANN001
        self._editor.paint_line_numbers(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        line = self._editor.line_at_gutter_y(event.position().toPoint().y())
        if line is None:
            return
        self._anchor_line = line
        # Shift+click extends from current cursor line
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            cur = self._editor.textCursor().blockNumber() + 1
            self._editor.select_line_range(min(cur, line), max(cur, line))
        else:
            self._editor.select_line_range(line, line)
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not (event.buttons() & Qt.MouseButton.LeftButton) or self._anchor_line is None:
            return
        line = self._editor.line_at_gutter_y(event.position().toPoint().y())
        if line is None:
            return
        a, b = self._anchor_line, line
        self._editor.select_line_range(min(a, b), max(a, b))
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._anchor_line = None
        super().mouseReleaseEvent(event)


class NoteEditor(QPlainTextEdit):
    """VS Code–like monospace editor; exposes selection helpers for AI later."""

    content_modified = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("noteEditor")
        self.setFrameStyle(QPlainTextEdit.Shape.NoFrame)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setFont(mono_font(11))
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
        pal.setColor(QPalette.ColorRole.Window, QColor("#ffffff"))
        pal.setColor(QPalette.ColorRole.Text, QColor("#1d1d1f"))
        pal.setColor(QPalette.ColorRole.Highlight, QColor("#cce8df"))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#0F6B4C"))
        self.setPalette(pal)
        self.viewport().setAutoFillBackground(True)
        self.viewport().setPalette(pal)
        self.viewport().setStyleSheet("background-color: #ffffff; color: #1d1d1f;")

        self._line_area = LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self.textChanged.connect(self.content_modified.emit)

        self._update_line_number_area_width(0)
        self._highlight_current_line()
        self.setStyleSheet(
            """
            QPlainTextEdit#noteEditor, QPlainTextEdit#noteEditor QWidget {
                background-color: #ffffff;
                color: #1d1d1f;
                border: none;
            }
            """
        )

    def line_number_area_width(self) -> int:
        digits = max(1, len(str(max(1, self.blockCount()))))
        return 12 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_line_number_area_width(self, _count: int = 0) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self._line_area.scroll(0, dy)
        else:
            self._line_area.update(0, rect.y(), self._line_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width()

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def paint_line_numbers(self, event) -> None:  # noqa: ANN001
        painter = QPainter(self._line_area)
        painter.fillRect(self._line_area.rect(), QColor("#f5f7f6"))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor("#8e8e93"))
                painter.drawText(
                    0,
                    top,
                    self._line_area.width() - 6,
                    self.fontMetrics().height(),
                    int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                    number,
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    def _highlight_current_line(self) -> None:
        extras = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor("#eef6f2"))
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extras.append(selection)
        self.setExtraSelections(extras)

    def line_at_gutter_y(self, y: int) -> int | None:
        """Map gutter Y (widget coords) → 1-based line number."""
        block = self.firstVisibleBlock()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        while block.isValid():
            bottom = top + round(self.blockBoundingRect(block).height())
            if top <= y < bottom:
                return block.blockNumber() + 1
            block = block.next()
            top = bottom
        return None

    def select_line_range(self, start_line: int, end_line: int) -> None:
        """Select inclusive 1-based whole lines."""
        if start_line > end_line:
            start_line, end_line = end_line, start_line
        doc = self.document()
        start_block = doc.findBlockByNumber(max(0, start_line - 1))
        end_block = doc.findBlockByNumber(max(0, end_line - 1))
        if not start_block.isValid() or not end_block.isValid():
            return
        cursor = QTextCursor(doc)
        cursor.setPosition(start_block.position())
        # Select through end of end_block (include newline if not last)
        if end_block.blockNumber() < doc.blockCount() - 1:
            cursor.setPosition(
                end_block.position() + end_block.length(),
                QTextCursor.MoveMode.KeepAnchor,
            )
        else:
            cursor.setPosition(
                end_block.position() + max(0, end_block.length() - 1),
                QTextCursor.MoveMode.KeepAnchor,
            )
        self.setTextCursor(cursor)
        self.setFocus(Qt.FocusReason.MouseFocusReason)

    def selected_line_range(self) -> tuple[int, int, str]:
        """Return 1-based inclusive line range and exact selected text (or current line)."""
        cursor = self.textCursor()
        if not cursor.hasSelection():
            block = cursor.block()
            return block.blockNumber() + 1, block.blockNumber() + 1, block.text()

        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        c = QTextCursor(self.document())
        c.setPosition(start)
        start_line = c.blockNumber() + 1
        c.setPosition(end)
        # If selection ends at block start, last line is previous block
        if c.atBlockStart() and end > start:
            end_line = c.blockNumber()
        else:
            end_line = c.blockNumber() + 1
        end_line = max(end_line, start_line)
        return start_line, end_line, cursor.selectedText().replace("\u2029", "\n")

    def get_line_range_text(self, start_line: int, end_line: int) -> str:
        """Exact text of inclusive 1-based lines, joined by \\n (no trailing final newline)."""
        if start_line > end_line:
            start_line, end_line = end_line, start_line
        lines: list[str] = []
        doc = self.document()
        for i in range(start_line - 1, end_line):
            block = doc.findBlockByNumber(i)
            if not block.isValid():
                break
            lines.append(block.text())
        return "\n".join(lines)

    def replace_current_selection(self, text: str) -> bool:
        """Replace the current selection (or current line if empty). Returns False if nothing to do."""
        cursor = self.textCursor()
        cursor.beginEditBlock()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        if not cursor.hasSelection():
            cursor.endEditBlock()
            return False
        cursor.insertText(text)
        cursor.endEditBlock()
        self.setTextCursor(cursor)
        return True

    def replace_line_range(self, start_line: int, end_line: int, text: str) -> None:
        """Replace inclusive 1-based lines with text (single undo step)."""
        doc = self.document()
        start_block = doc.findBlockByNumber(start_line - 1)
        end_block = doc.findBlockByNumber(end_line - 1)
        if not start_block.isValid() or not end_block.isValid():
            raise ValueError("line range out of bounds")

        cursor = QTextCursor(doc)
        cursor.beginEditBlock()
        cursor.setPosition(start_block.position())
        end_pos = end_block.position() + end_block.length() - 1  # exclude final block sep of last?
        # Include through end of end_block, including its newline except for last doc block
        cursor.setPosition(end_block.position() + end_block.length() - 1, QTextCursor.MoveMode.KeepAnchor)
        # If not last block, length includes \n; if last, no trailing \n in length-1
        if end_block.blockNumber() < doc.blockCount() - 1:
            # end_block.length() includes the newline; we already anchored at length-1 which is before \n
            # Expand to include the newline so the following line stays separated correctly
            cursor.setPosition(end_block.position() + end_block.length(), QTextCursor.MoveMode.KeepAnchor)
            replacement = text if text.endswith("\n") else text + "\n"
        else:
            replacement = text.rstrip("\n")
        cursor.insertText(replacement)
        cursor.endEditBlock()

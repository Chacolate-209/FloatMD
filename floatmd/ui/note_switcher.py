"""Popup list to switch / create notes."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from floatmd.services.notes_store import NoteMeta


class NoteSwitcherPopup(QWidget):
    note_chosen = Signal(str)
    create_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("noteSwitcherPopup")
        self.setMinimumWidth(260)
        self.setMaximumHeight(360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索")
        self.search.textChanged.connect(self._filter)
        row.addWidget(self.search)
        self.new_btn = QPushButton("新建")
        self.new_btn.clicked.connect(self.create_requested.emit)
        row.addWidget(self.new_btn)
        layout.addLayout(row)

        self.list = QListWidget()
        self.list.itemActivated.connect(self._activate)
        self.list.itemClicked.connect(self._activate)
        layout.addWidget(self.list)

        self._all: list[NoteMeta] = []
        self.setStyleSheet(
            """
            #noteSwitcherPopup {
                background: #2a2a2c;
                border: 1px solid #3c3c3c;
                border-radius: 8px;
            }
            QLineEdit, QPushButton, QListWidget {
                background: #1e1e1e;
                color: #cccccc;
                border: 1px solid #3c3c3c;
                border-radius: 5px;
                padding: 5px 8px;
                font-size: 12px;
            }
            QPushButton { background: #0e639c; border: none; color: #fff; }
            QPushButton:hover { background: #1177bb; }
            QListWidget::item { padding: 4px 6px; }
            QListWidget::item:selected { background: #0e639c; }
            QListWidget::item:hover { background: #333336; }
            """
        )

    def set_notes(self, notes: list[NoteMeta], current: str | None = None) -> None:
        self._all = list(notes)
        self._filter(self.search.text())
        if current:
            for i in range(self.list.count()):
                item = self.list.item(i)
                if item and item.data(Qt.ItemDataRole.UserRole) == current:
                    self.list.setCurrentItem(item)
                    break

    def _filter(self, text: str = "") -> None:
        q = (text or "").strip().lower()
        self.list.clear()
        for meta in self._all:
            hay = f"{meta.title} {meta.name}".lower()
            if q and q not in hay:
                continue
            item = QListWidgetItem(f"{meta.title}  ({meta.name})")
            item.setData(Qt.ItemDataRole.UserRole, meta.name)
            self.list.addItem(item)

    def _activate(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.ItemDataRole.UserRole)
        if name:
            self.note_chosen.emit(str(name))
            self.hide()

    def popup_at(self, global_pos) -> None:  # noqa: ANN001
        self.adjustSize()
        self.move(global_pos)
        self.show()
        self.search.setFocus()
        self.raise_()

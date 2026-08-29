"""Collapsible AI drawer: context chips + explain / rewrite."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from floatmd.services.ai_client import Action, AiClient, AiError, AiResult
from floatmd.services.config import AppConfig


@dataclass
class ContextChunk:
    start_line: int
    end_line: int
    text: str

    def preview(self, limit: int = 64) -> str:
        one = self.text.replace("\n", " ").strip()
        if len(one) > limit:
            one = one[: limit - 1] + "…"
        return f"L{self.start_line}–{self.end_line}  {one}"


@dataclass
class RewriteSnapshot:
    """Locked write-back target captured when Rewrite is clicked."""

    start_line: int
    end_line: int
    text: str
    text_hash: str

    @staticmethod
    def from_range(start_line: int, end_line: int, text: str) -> "RewriteSnapshot":
        return RewriteSnapshot(
            start_line=start_line,
            end_line=end_line,
            text=text,
            text_hash=hash_text(text),
        )

    def label(self) -> str:
        if self.start_line == self.end_line:
            return f"L{self.start_line}"
        return f"L{self.start_line}–{self.end_line}"


@dataclass
class RewriteApply:
    snapshot: RewriteSnapshot
    content: str


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class _AiWorker(QThread):
    finished_ok = Signal(object)
    finished_err = Signal(object)

    def __init__(
        self,
        client: AiClient,
        task: Action,
        chunks: list[str],
        instruction: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._task = task
        self._chunks = chunks
        self._instruction = instruction

    def run(self) -> None:
        try:
            result = self._client.chat(
                task=self._task,
                context_chunks=self._chunks,
                instruction=self._instruction,
            )
            self.finished_ok.emit(result)
        except AiError as exc:
            self.finished_err.emit(exc)
        except Exception as exc:  # noqa: BLE001
            self.finished_err.emit(exc)


class AiDrawer(QFrame):
    apply_rewrite = Signal(object)  # RewriteApply
    apply_format = Signal(str)  # full-note Markdown after format
    request_full_note = Signal()  # ask host to push whole note into context for format
    rewrite_requested = Signal()  # host must call begin_rewrite(snapshot)
    open_settings = Signal()
    add_selection_requested = Signal()
    collapsed = Signal()

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.setObjectName("aiDrawer")
        self.setVisible(False)
        self.setFixedHeight(228)
        self._chunks: list[ContextChunk] = []
        self._worker: _AiWorker | None = None
        self._pending_task: Action | None = None
        self._rewrite_snap: RewriteSnapshot | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 8)
        layout.setSpacing(5)

        head = QHBoxLayout()
        head.setSpacing(6)
        title = QLabel("AI")
        title.setObjectName("aiTitle")
        head.addWidget(title)
        head.addStretch(1)
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setToolTip("设置")
        self.settings_btn.setFixedWidth(32)
        self.settings_btn.clicked.connect(self.open_settings.emit)
        head.addWidget(self.settings_btn)
        self.close_btn = QPushButton("▾")
        self.close_btn.setToolTip("收起 (Esc)")
        self.close_btn.setFixedWidth(32)
        self.close_btn.clicked.connect(self.collapse)
        head.addWidget(self.close_btn)
        layout.addLayout(head)

        row = QHBoxLayout()
        row.setSpacing(6)
        self.add_btn = QPushButton("＋选区")
        self.add_btn.setObjectName("primaryBtn")
        self.add_btn.setToolTip("加入选区（可在行号栏点击/拖动选行）")
        self.add_btn.clicked.connect(self.add_selection_requested.emit)
        row.addWidget(self.add_btn)
        self.clear_btn = QPushButton("清空")
        self.clear_btn.setToolTip("清空上下文")
        self.clear_btn.clicked.connect(self.clear_context)
        row.addWidget(self.clear_btn)
        self.ctx_count = QLabel("0")
        self.ctx_count.setObjectName("hintLabel")
        self.ctx_count.setToolTip("上下文段数")
        row.addWidget(self.ctx_count)
        row.addStretch(1)
        layout.addLayout(row)

        self.ctx_list = QListWidget()
        self.ctx_list.setFixedHeight(44)
        self.ctx_list.setToolTip("双击移除")
        self.ctx_list.itemDoubleClicked.connect(self._remove_item)
        layout.addWidget(self.ctx_list)

        self.instruction = QPlainTextEdit()
        self.instruction.setPlaceholderText("说明（可空）")
        self.instruction.setFixedHeight(36)
        layout.addWidget(self.instruction)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        self.explain_btn = QPushButton("解释")
        self.explain_btn.setObjectName("primaryBtn")
        self.explain_btn.setToolTip("解释上下文")
        self.explain_btn.clicked.connect(lambda: self._run("explain"))
        self.rewrite_btn = QPushButton("改写")
        self.rewrite_btn.setObjectName("primaryBtn")
        self.rewrite_btn.setToolTip("改写当前选中行并写回（局部）")
        self.rewrite_btn.clicked.connect(self._request_rewrite)
        self.format_btn = QPushButton("排版")
        self.format_btn.setObjectName("formatBtn")
        self.format_btn.setToolTip("优化整篇 Markdown 结构")
        self.format_btn.clicked.connect(self._run_format)
        actions.addWidget(self.explain_btn)
        actions.addWidget(self.rewrite_btn)
        actions.addWidget(self.format_btn)
        self.status = QLabel("")
        self.status.setObjectName("aiStatus")
        actions.addWidget(self.status)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.result = QTextEdit()
        self.result.setReadOnly(True)
        self.result.setPlaceholderText("结果")
        self.result.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.result)
    def toggle(self) -> None:
        if self.isVisible():
            self.collapse()
        else:
            self.expand()

    def collapse(self) -> None:
        self.setVisible(False)
        self.collapsed.emit()

    def expand(self) -> None:
        self.setVisible(True)

    def clear_context(self) -> None:
        self._chunks.clear()
        self.ctx_list.clear()
        self._refresh_count()

    def add_chunk(self, chunk: ContextChunk) -> None:
        text = chunk.text.strip("\n")
        if not text.strip():
            return
        self._chunks.append(ContextChunk(chunk.start_line, chunk.end_line, text))
        item = QListWidgetItem(chunk.preview())
        self.ctx_list.addItem(item)
        self._refresh_count()

    def _refresh_count(self) -> None:
        n = len(self._chunks)
        self.ctx_count.setText(str(n))

    def _remove_item(self, item: QListWidgetItem) -> None:
        row = self.ctx_list.row(item)
        self.ctx_list.takeItem(row)
        if 0 <= row < len(self._chunks):
            self._chunks.pop(row)
        self.ctx_list.clear()
        for c in self._chunks:
            self.ctx_list.addItem(QListWidgetItem(c.preview()))
        self._refresh_count()

    def _set_busy(self, busy: bool) -> None:
        self.explain_btn.setEnabled(not busy)
        self.rewrite_btn.setEnabled(not busy)
        self.format_btn.setEnabled(not busy)
        self.add_btn.setEnabled(not busy)
        self.status.setText("…" if busy else "")

    def _make_client(self) -> AiClient | None:
        ai = self.config.data.get("ai", {})
        try:
            return AiClient(
                base_url=str(ai.get("base_url", "")),
                model=str(ai.get("model", "")),
                temperature=float(ai.get("temperature", 0.3)),
                timeout_ms=int(ai.get("timeout_ms", 60_000)),
            )
        except AiError as exc:
            QMessageBox.warning(self, "AI", str(exc))
            return None

    def _run(self, task: Action) -> None:
        if self._worker and self._worker.isRunning():
            return
        client = self._make_client()
        if client is None:
            return

        chunks = [c.text for c in self._chunks]
        if not chunks:
            QMessageBox.information(self, "AI", "请先选中文本并点击「加入选区」。")
            return

        self._rewrite_snap = None
        self._start_worker(client, task, chunks, self.instruction.toPlainText())

    def _request_rewrite(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        # Host snapshots editor line range, then calls begin_rewrite(...)
        self.rewrite_requested.emit()

    def begin_rewrite(self, snapshot: RewriteSnapshot) -> None:
        """Start rewrite with a locked write-back target (Lx–Ly)."""
        if self._worker and self._worker.isRunning():
            return
        client = self._make_client()
        if client is None:
            return
        if not snapshot.text.strip():
            QMessageBox.information(self, "AI", "请先选中要改写的行。")
            return

        self._rewrite_snap = snapshot
        # Context for model: explicit chunks if any, else the snapshot text
        chunks = [c.text for c in self._chunks] or [snapshot.text]
        instruction = self.instruction.toPlainText()
        # Tell the model which lines will be replaced
        meta = (
            f"Write-back target: {snapshot.label()} only. "
            "Return rewrite content for those lines alone, not the whole document."
        )
        if instruction.strip():
            instruction = meta + "\n" + instruction
        else:
            instruction = meta
        self._start_worker(client, "rewrite", chunks, instruction)

    def _run_format(self) -> None:
        """Format whole note: ask host to supply full body as context."""
        if self._worker and self._worker.isRunning():
            return
        self._rewrite_snap = None
        # Host will call begin_format(full_text)
        self.request_full_note.emit()

    def begin_format(self, full_note: str) -> None:
        client = self._make_client()
        if client is None:
            return
        if not full_note.strip():
            QMessageBox.information(self, "AI", "笔记为空，无需排版。")
            return
        self._rewrite_snap = None
        instruction = self.instruction.toPlainText().strip() or (
            "请优化 Markdown 结构：合理分段、标题层级、列表与空行，不要改动原意。"
        )
        self._start_worker(client, "format", [full_note], instruction)

    def _start_worker(
        self,
        client: AiClient,
        task: Action,
        chunks: list[str],
        instruction: str,
    ) -> None:
        self._pending_task = task
        self._set_busy(True)
        self.result.clear()
        worker = _AiWorker(client, task, chunks, instruction, self)
        worker.finished_ok.connect(self._on_ok)
        worker.finished_err.connect(self._on_err)
        worker.finished.connect(lambda: self._set_busy(False))
        self._worker = worker
        worker.start()

    def _on_ok(self, result: object) -> None:
        assert isinstance(result, AiResult)
        task = self._pending_task or result.action
        if task == "explain" or result.action == "explain":
            self.result.setPlainText(result.content)
            self.status.setText("OK")
            return

        preview = result.content
        if task == "format" or result.action == "format":
            box = QMessageBox(self)
            box.setWindowTitle("排版")
            box.setIcon(QMessageBox.Icon.Question)
            box.setText("替换整篇笔记？")
            box.setInformativeText(preview if len(preview) < 600 else preview[:600] + "\n…")
            box.setDetailedText(preview)
            box.setStandardButtons(
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
            )
            if box.exec() == QMessageBox.StandardButton.Ok:
                self.result.setPlainText(preview)
                self.status.setText("OK")
                self.apply_format.emit(preview)
            else:
                self.result.setPlainText(preview)
                self.status.setText("取消")
            return

        snap = self._rewrite_snap
        target = snap.label() if snap else "选区"
        box = QMessageBox(self)
        box.setWindowTitle("改写")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(f"替换 {target}？")
        box.setInformativeText(preview if len(preview) < 600 else preview[:600] + "\n…")
        box.setDetailedText(preview)
        box.setStandardButtons(
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        if box.exec() == QMessageBox.StandardButton.Ok:
            self.result.setPlainText(preview)
            self.status.setText("OK")
            if snap is None:
                QMessageBox.warning(self, "AI", "缺少写回行号快照，已取消。")
                return
            self.apply_rewrite.emit(RewriteApply(snapshot=snap, content=preview))
        else:
            self.result.setPlainText(preview)
            self.status.setText("取消")

    def _on_err(self, err: object) -> None:
        msg = str(err)
        if isinstance(err, AiError) and err.raw_snippet:
            msg += f"\n\n{err.raw_snippet}"
        self.result.setPlainText(msg)
        self.status.setText("失败")
        QMessageBox.warning(self, "AI", str(err))

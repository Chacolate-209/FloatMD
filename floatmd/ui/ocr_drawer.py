"""Collapsible OCR drawer: paste / drop / snip → recognize → insert."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QMimeData, Qt, QThread, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from floatmd.services.ocr_engine import OcrError, OcrResult, engine_status, recognize_png


class _OcrWorker(QThread):
    progress = Signal(str)
    finished_ok = Signal(object)
    finished_err = Signal(object)

    def __init__(self, png: bytes, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._png = png

    def run(self) -> None:
        try:
            result = recognize_png(self._png, progress=lambda m: self.progress.emit(m))
            self.finished_ok.emit(result)
        except OcrError as exc:
            self.finished_err.emit(exc)
        except Exception as exc:  # noqa: BLE001
            self.finished_err.emit(exc)


class OcrDrawer(QFrame):
    insert_text = Signal(str)
    append_text = Signal(str)
    snip_requested = Signal()
    collapsed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ocrDrawer")
        self.setVisible(False)
        self.setFixedHeight(190)
        self._worker: _OcrWorker | None = None
        self._last_png: bytes | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 8)
        layout.setSpacing(5)

        head = QHBoxLayout()
        title = QLabel("OCR")
        title.setObjectName("ocrTitle")
        head.addWidget(title)
        status = engine_status()
        eng = {
            "paddle+rapid": "Paddle",
            "paddle": "Paddle",
            "rapid": "Rapid",
        }.get(status, "—")
        self.engine_label = QLabel(eng)
        self.engine_label.setObjectName("ocrStatus")
        self.engine_label.setToolTip(f"引擎: {status}")
        head.addWidget(self.engine_label)
        head.addStretch(1)
        self.close_btn = QPushButton("▾")
        self.close_btn.setToolTip("收起 (Esc)")
        self.close_btn.setFixedWidth(32)
        self.close_btn.clicked.connect(self.collapse)
        head.addWidget(self.close_btn)
        layout.addLayout(head)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        self.snip_btn = QPushButton("截屏")
        self.snip_btn.setObjectName("primaryBtn")
        self.snip_btn.setToolTip("画框截屏")
        self.snip_btn.clicked.connect(self.snip_requested.emit)
        self.paste_btn = QPushButton("粘贴")
        self.paste_btn.setToolTip("粘贴剪贴板图片")
        self.paste_btn.clicked.connect(self._paste_image)
        self.retry_btn = QPushButton("↻")
        self.retry_btn.setToolTip("重新识别")
        self.retry_btn.setFixedWidth(32)
        self.retry_btn.clicked.connect(self._retry)
        self.retry_btn.setEnabled(False)
        actions.addWidget(self.snip_btn)
        actions.addWidget(self.paste_btn)
        actions.addWidget(self.retry_btn)
        self.status = QLabel("待识别")
        self.status.setObjectName("ocrStatus")
        actions.addWidget(self.status)
        actions.addStretch(1)
        layout.addLayout(actions)
        body = QHBoxLayout()
        body.setSpacing(8)
        self.preview = QLabel()
        self.preview.setFixedSize(56, 56)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet(
            "background:#ffffff; border:1px solid #e3e8e6; border-radius:6px; color:#8e8e93;"
        )
        self.preview.setText("图")
        body.addWidget(self.preview)

        self.result = QTextEdit()
        self.result.setPlaceholderText("结果")
        body.addWidget(self.result, 1)
        layout.addLayout(body)

        out = QHBoxLayout()
        out.setSpacing(6)
        self.insert_btn = QPushButton("插入")
        self.insert_btn.setObjectName("primaryBtn")
        self.insert_btn.setToolTip("插入到光标处")
        self.insert_btn.clicked.connect(self._insert)
        self.append_btn = QPushButton("追加")
        self.append_btn.setToolTip("追加到文末")
        self.append_btn.clicked.connect(self._append)
        self.copy_btn = QPushButton("复制")
        self.copy_btn.clicked.connect(self._copy)
        out.addWidget(self.insert_btn)
        out.addWidget(self.append_btn)
        out.addWidget(self.copy_btn)
        out.addStretch(1)
        layout.addLayout(out)

        self.setAcceptDrops(True)

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

    def dragEnterEvent(self, event) -> None:  # noqa: ANN001
        if event.mimeData().hasImage() or event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: ANN001
        png = _mime_to_png(event.mimeData())
        if png:
            self.recognize_png(png)
            event.acceptProposedAction()
        else:
            QMessageBox.information(self, "OCR", "未能从拖放中读取图片")

    def _paste_image(self) -> None:
        from PySide6.QtWidgets import QApplication

        clip = QApplication.clipboard()
        png = _mime_to_png(clip.mimeData() if clip else None)
        if not png:
            QMessageBox.information(self, "OCR", "剪贴板里没有图片")
            return
        self.recognize_png(png)

    def _retry(self) -> None:
        if self._last_png:
            self.recognize_png(self._last_png)

    def recognize_png(self, png: bytes) -> None:
        if self._worker and self._worker.isRunning():
            return
        self._last_png = png
        self.retry_btn.setEnabled(True)
        self._show_thumb(png)
        self.result.clear()
        self._set_busy(True)
        self.status.setText("…")
        worker = _OcrWorker(png, self)
        worker.progress.connect(self.status.setText)
        worker.finished_ok.connect(self._on_ok)
        worker.finished_err.connect(self._on_err)
        worker.finished.connect(lambda: self._set_busy(False))
        self._worker = worker
        worker.start()

    def _show_thumb(self, png: bytes) -> None:
        img = QImage.fromData(QByteArray(png))
        if img.isNull():
            self.preview.setText("图")
            return
        pix = QPixmap.fromImage(img).scaled(
            54,
            54,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview.setPixmap(pix)

    def _set_busy(self, busy: bool) -> None:
        self.snip_btn.setEnabled(not busy)
        self.paste_btn.setEnabled(not busy)
        self.retry_btn.setEnabled(not busy and self._last_png is not None)

    def _on_ok(self, result: object) -> None:
        assert isinstance(result, OcrResult)
        self.result.setPlainText(result.text)
        self.status.setText("OK" if result.text else "空")
        self.engine_label.setText("Paddle" if "paddle" in result.engine else "Rapid")

    def _on_err(self, err: object) -> None:
        self.status.setText("失败")
        self.result.setPlainText(str(err))
        QMessageBox.warning(self, "OCR", str(err))

    def _insert(self) -> None:
        text = self.result.toPlainText().strip()
        if text:
            self.insert_text.emit(text)

    def _append(self) -> None:
        text = self.result.toPlainText().strip()
        if text:
            self.append_text.emit(text)

    def _copy(self) -> None:
        from PySide6.QtWidgets import QApplication

        clip = QApplication.clipboard()
        if clip is not None:
            clip.setText(self.result.toPlainText())


def _mime_to_png(mime: QMimeData | None) -> bytes | None:
    if mime is None:
        return None
    if mime.hasImage():
        img = mime.imageData()
        if isinstance(img, QImage) and not img.isNull():
            ba = QByteArray()
            from PySide6.QtCore import QBuffer

            buf = QBuffer(ba)
            buf.open(QBuffer.OpenModeFlag.WriteOnly)
            img.save(buf, "PNG")
            return bytes(ba)
        if isinstance(img, QPixmap) and not img.isNull():
            ba = QByteArray()
            from PySide6.QtCore import QBuffer

            buf = QBuffer(ba)
            buf.open(QBuffer.OpenModeFlag.WriteOnly)
            img.toImage().save(buf, "PNG")
            return bytes(ba)
    if mime.hasUrls():
        for url in mime.urls():
            path = url.toLocalFile()
            if path and path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif")):
                try:
                    import io

                    from PIL import Image

                    im = Image.open(path).convert("RGB")
                    bio = io.BytesIO()
                    im.save(bio, format="PNG")
                    return bio.getvalue()
                except Exception:
                    continue
    return None

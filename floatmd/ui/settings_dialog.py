"""Lightweight settings dialog (AI endpoint + API key)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from floatmd.services import secrets
from floatmd.services.ai_client import AiError, validate_base_url
from floatmd.services.config import AppConfig


class SettingsDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("FloatMD 设置")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        ai = config.data.get("ai", {})
        self.base_url = QLineEdit(str(ai.get("base_url", "")))
        self.base_url.setPlaceholderText("https://api.openai.com/v1 或 http://127.0.0.1:11434/v1")
        self.model = QLineEdit(str(ai.get("model", "")))
        self.model.setPlaceholderText("gpt-4o-mini / deepseek-chat / …")
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("留空=不改已有 Key")
        self.persist_key = QCheckBox("保存到系统钥匙串（关=仅本次）")
        self.persist_key.setChecked(True)

        st = secrets.status()
        src = st.get("source", "none")
        self.key_status = QLabel(
            f"Key：{'已配置（' + str(src) + '）' if st.get('present') else '未配置'}"
        )

        form.addRow("Base URL", self.base_url)
        form.addRow("Model", self.model)
        form.addRow("API Key", self.api_key)
        form.addRow("", self.persist_key)
        form.addRow("", self.key_status)
        layout.addLayout(form)

        clear_row = QHBoxLayout()
        from PySide6.QtWidgets import QPushButton

        clear_btn = QPushButton("清除 Key")
        clear_btn.clicked.connect(self._clear_key)
        clear_row.addWidget(clear_btn)
        clear_row.addStretch(1)
        layout.addLayout(clear_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _clear_key(self) -> None:
        secrets.clear_api_key()
        self.api_key.clear()
        self.key_status.setText("当前 Key：未配置")

    def _save(self) -> None:
        try:
            base = validate_base_url(self.base_url.text())
        except AiError as exc:
            QMessageBox.warning(self, "设置", str(exc))
            return
        model = self.model.text().strip()
        if not model:
            QMessageBox.warning(self, "设置", "Model 不能为空")
            return

        # Native-ish confirm when endpoint changes
        old = str(self.config.data.get("ai", {}).get("base_url", "")).rstrip("/")
        if base != old:
            reply = QMessageBox.question(
                self,
                "确认 API 地址",
                f"之后的请求（含 API Key）将发往：\n{base}\n\n确认保存？",
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.config.data["ai"]["base_url"] = base
        self.config.data["ai"]["model"] = model
        self.config.save()

        key = self.api_key.text().strip()
        if key:
            try:
                secrets.set_api_key(key, persist=self.persist_key.isChecked())
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "设置", f"保存 Key 失败：{exc}\n将尝试仅会话保存。")
                secrets.set_api_key(key, persist=False)

        self.accept()

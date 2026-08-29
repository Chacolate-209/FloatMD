"""Light theme inspired by macOS Notes / floating panels.

Palette (user preference: white canvas + 墨绿 / 青 / 蓝 accents):
  canvas      #FFFFFF
  surface     #F5F7F6
  border      #E3E8E6
  text        #1D1D1F
  muted       #6E6E73
  green       #0F6B4C   primary actions
  teal        #0D9488   secondary / OCR
  blue        #2563EB   links / AI focus
"""

APP_QSS = """
* {
    font-family: "Noto Sans CJK SC", "Noto Sans SC", "WenQuanYi Micro Hei",
                 "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif;
}

#root {
    background: #ffffff;
    border: 1px solid #d8dedb;
    border-radius: 12px;
}

#titleBar {
    background: #f5f7f6;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    border-bottom: 1px solid #e3e8e6;
}

QToolButton {
    color: #3a3a3c;
    padding: 4px 9px;
    border-radius: 6px;
    border: none;
    font-size: 12px;
    background: transparent;
}
QToolButton:hover {
    background: rgba(15, 107, 76, 0.10);
    color: #0F6B4C;
}
QToolButton:checked {
    background: #0F6B4C;
    color: #ffffff;
}

QToolButton#noteSwitcher {
    font-weight: 600;
    font-size: 13px;
    color: #1d1d1f;
    padding-left: 8px;
    padding-right: 8px;
}
QToolButton#noteSwitcher:hover {
    background: rgba(15, 107, 76, 0.08);
}

QFrame#modeGroup {
    background: #ffffff;
    border: 1px solid #e3e8e6;
    border-radius: 7px;
}
QToolButton#modeEdit, QToolButton#modeDisplay {
    min-width: 28px;
    padding: 3px 8px;
}
QToolButton#pinBtn, QToolButton#winHide, QToolButton#winClose {
    min-width: 26px;
    padding: 3px 6px;
}

QToolButton#pinBtn:checked {
    background: #0D9488;
    color: #fff;
}

QToolButton#winHide, QToolButton#winClose {
    min-width: 24px;
    padding: 3px 7px;
    color: #8e8e93;
}
QToolButton#winClose:hover {
    background: #ff3b30;
    color: #ffffff;
}

#statusBar {
    background: #f5f7f6;
    border-top: 1px solid #e3e8e6;
    color: #6e6e73;
    font-size: 11px;
    padding: 2px 12px;
}

#hintLabel {
    color: #8e8e93;
    font-size: 11px;
}
#placeholder {
    color: #8e8e93;
    font-size: 14px;
}

/* Drawers — frosted light panels */
#aiDrawer, #ocrDrawer {
    background: #f7faf9;
    border-top: 1px solid #e3e8e6;
}
#aiTitle, #ocrTitle {
    color: #1d1d1f;
    font-weight: 600;
    font-size: 12px;
}
#aiStatus, #ocrStatus {
    color: #6e6e73;
    font-size: 11px;
}

#aiDrawer QPushButton, #ocrDrawer QPushButton, #noteSwitcherPopup QPushButton {
    background: #ffffff;
    color: #1d1d1f;
    border: 1px solid #d8dedb;
    padding: 5px 11px;
    border-radius: 6px;
    font-size: 12px;
}
#aiDrawer QPushButton:hover, #ocrDrawer QPushButton:hover {
    border-color: #0D9488;
    color: #0F6B4C;
}
#aiDrawer QPushButton:disabled, #ocrDrawer QPushButton:disabled {
    color: #a1a1a6;
    background: #f2f2f7;
    border-color: #e5e5ea;
}

#aiDrawer QPushButton#primaryBtn {
    background: #0F6B4C;
    color: #ffffff;
    border: none;
}
#aiDrawer QPushButton#primaryBtn:hover {
    background: #0c5a40;
}
#aiDrawer QPushButton#formatBtn {
    background: #2563EB;
    color: #ffffff;
    border: none;
}
#aiDrawer QPushButton#formatBtn:hover {
    background: #1d4ed8;
}
#ocrDrawer QPushButton#primaryBtn {
    background: #0D9488;
    color: #ffffff;
    border: none;
}
#ocrDrawer QPushButton#primaryBtn:hover {
    background: #0f766e;
}

#aiDrawer QListWidget, #aiDrawer QPlainTextEdit, #aiDrawer QTextEdit,
#ocrDrawer QTextEdit {
    background: #ffffff;
    color: #1d1d1f;
    border: 1px solid #e3e8e6;
    border-radius: 6px;
    font-size: 12px;
    selection-background-color: #cce8df;
}

#noteSwitcherPopup {
    background: #ffffff;
    border: 1px solid #d8dedb;
    border-radius: 10px;
}
#noteSwitcherPopup QLineEdit, #noteSwitcherPopup QListWidget {
    background: #ffffff;
    color: #1d1d1f;
    border: 1px solid #e3e8e6;
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 12px;
}
#noteSwitcherPopup QPushButton {
    background: #0F6B4C;
    border: none;
    color: #fff;
}
#noteSwitcherPopup QPushButton:hover { background: #0c5a40; }
#noteSwitcherPopup QListWidget::item { padding: 5px 8px; }
#noteSwitcherPopup QListWidget::item:selected { background: #0F6B4C; color: #fff; }
#noteSwitcherPopup QListWidget::item:hover { background: #e8f5f0; }
"""

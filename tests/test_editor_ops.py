"""Operational tests: selection, AI context wiring (no live network)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication

from floatmd.services.ai_client import AiClient, AiError, AiResult, build_user_message, parse_ai_json
from floatmd.services.config import AppConfig
from floatmd.ui.ai_drawer import AiDrawer, ContextChunk
from floatmd.ui.main_window import MainWindow
from floatmd.ui.note_editor import NoteEditor


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def editor(qapp):
    ed = NoteEditor()
    ed.setPlainText("line1\nline2\nline3\nline4\n")
    return ed


def test_select_line_range_single(editor):
    editor.select_line_range(2, 2)
    start, end, text = editor.selected_line_range()
    assert start == 2 and end == 2
    assert "line2" in text
    assert "line1" not in text
    assert "line3" not in text


def test_select_line_range_multi(editor):
    editor.select_line_range(2, 4)
    start, end, text = editor.selected_line_range()
    assert start == 2 and end == 4
    assert "line2" in text and "line3" in text and "line4" in text
    assert "line1" not in text


def test_select_line_range_reversed(editor):
    editor.select_line_range(4, 2)
    start, end, text = editor.selected_line_range()
    assert start == 2 and end == 4


def test_empty_selection_falls_back_to_current_line(editor):
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.Start)
    cursor.movePosition(QTextCursor.MoveOperation.Down)
    cursor.clearSelection()
    editor.setTextCursor(cursor)
    start, end, text = editor.selected_line_range()
    assert start == end == 2
    assert text == "line2"


def test_replace_current_selection(editor):
    editor.select_line_range(2, 3)
    assert editor.replace_current_selection("NEW\nBLOCK")
    body = editor.toPlainText()
    assert "line1" in body
    assert "NEW\nBLOCK" in body or "NEW" in body
    assert "line2" not in body


def test_ai_add_selection_ops(qapp, tmp_path):
    cfg = AppConfig(path=tmp_path / "config.json")
    cfg.data["notes_dir"] = str(tmp_path / "notes")
    cfg.save()
    win = MainWindow(cfg)
    win.editor.setPlainText("alpha\nbeta\ngamma\n")
    win.editor.select_line_range(1, 2)
    win._ai_add_selection()
    assert len(win.ai_drawer._chunks) == 1
    chunk = win.ai_drawer._chunks[0]
    assert chunk.start_line == 1 and chunk.end_line == 2
    assert "alpha" in chunk.text and "beta" in chunk.text

    # second add
    win.editor.select_line_range(3, 3)
    win._ai_add_selection()
    assert len(win.ai_drawer._chunks) == 2


def test_ai_apply_rewrite_ops(qapp, tmp_path):
    from floatmd.ui.ai_drawer import RewriteApply, RewriteSnapshot, hash_text

    cfg = AppConfig(path=tmp_path / "config.json")
    cfg.data["notes_dir"] = str(tmp_path / "notes")
    cfg.save()
    win = MainWindow(cfg)
    win.editor.setPlainText("old\nkeep\nthird\n")
    text = win.editor.get_line_range_text(1, 2)
    snap = RewriteSnapshot.from_range(1, 2, text)
    win._ai_apply_rewrite(RewriteApply(snapshot=snap, content="fresh\nblock"))
    body = win.editor.toPlainText()
    assert body.startswith("fresh")
    assert "block" in body
    assert "third" in body
    assert "old" not in body
    assert "keep" not in body


def test_ai_rewrite_refuses_stale_hash(qapp, tmp_path):
    from floatmd.ui.ai_drawer import RewriteApply, RewriteSnapshot

    cfg = AppConfig(path=tmp_path / "config.json")
    cfg.data["notes_dir"] = str(tmp_path / "notes")
    cfg.save()
    win = MainWindow(cfg)
    win.editor.setPlainText("old\nkeep\n")
    snap = RewriteSnapshot.from_range(1, 1, "old")
    # mutate document after snapshot
    win.editor.setPlainText("CHANGED\nkeep\n")
    with patch("floatmd.ui.main_window.QMessageBox.warning"):
        win._ai_apply_rewrite(RewriteApply(snapshot=snap, content="fresh"))
    # unchanged because hash mismatch
    assert win.editor.toPlainText().startswith("CHANGED")


def test_get_line_range_text_and_hash(editor):
    from floatmd.ui.ai_drawer import hash_text

    text = editor.get_line_range_text(2, 3)
    assert text == "line2\nline3"
    assert len(hash_text(text)) == 64


def test_ai_apply_format_ops(qapp, tmp_path):
    cfg = AppConfig(path=tmp_path / "config.json")
    cfg.data["notes_dir"] = str(tmp_path / "notes")
    cfg.save()
    win = MainWindow(cfg)
    win.editor.setPlainText("messy text")
    win._ai_apply_format("# Title\n\n neat\n")
    assert win.editor.toPlainText().startswith("# Title")


def test_ai_client_mocked_explain():
    client = AiClient(base_url="https://api.example.com/v1", model="m")
    fake = {
        "choices": [{"message": {"content": '{"action":"explain","content":"含义是…"}'}}]
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b'{"ok":true}'
    mock_resp.json.return_value = fake
    mock_resp.text = "{}"

    with patch("floatmd.services.ai_client.secrets.get_api_key", return_value="sk-test"), patch(
        "floatmd.services.ai_client.httpx.Client"
    ) as Client:
        inst = Client.return_value.__enter__.return_value
        inst.post.return_value = mock_resp
        result = client.chat(task="explain", context_chunks=["code here"], instruction="")
    assert isinstance(result, AiResult)
    assert result.action == "explain"
    assert "含义" in result.content


def test_ai_client_mocked_format():
    client = AiClient(base_url="http://127.0.0.1:11434/v1", model="llama")
    body = '{"action":"format","content":"# A\\n\\nB"}'
    fake = {"choices": [{"message": {"content": body}}]}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"{}"
    mock_resp.json.return_value = fake
    mock_resp.text = "{}"

    with patch("floatmd.services.ai_client.secrets.get_api_key", return_value="sk"), patch(
        "floatmd.services.ai_client.httpx.Client"
    ) as Client:
        inst = Client.return_value.__enter__.return_value
        inst.post.return_value = mock_resp
        result = client.chat(task="format", context_chunks=["A\nB"], instruction="")
    assert result.action == "format"
    assert result.content.startswith("# A")


def test_ai_client_missing_key():
    client = AiClient(base_url="https://api.example.com/v1", model="m")
    with patch("floatmd.services.ai_client.secrets.get_api_key", return_value=None):
        with pytest.raises(AiError) as ei:
            client.chat(task="explain", context_chunks=["x"])
    assert ei.value.code == "key_missing"


def test_build_message_for_format():
    msg = build_user_message(task="format", context_chunks=["整篇"], instruction="排版")
    assert "[Task]" in msg and "format" in msg
    assert "整篇" in msg

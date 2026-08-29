from __future__ import annotations

from pathlib import Path

import pytest

from floatmd.services.notes_store import NotesStore


def test_create_write_read_list(tmp_path: Path) -> None:
    store = NotesStore(tmp_path)
    meta = store.create("Hello")
    assert meta.name.endswith(".md")
    text = store.read(meta.name)
    assert text.startswith("# Hello")
    store.write(meta.name, "# Hello\n\nbody\n")
    assert "body" in store.read(meta.name)
    notes = store.list_notes()
    assert any(n.name == meta.name and n.title == "Hello" for n in notes)


def test_rejects_path_escape(tmp_path: Path) -> None:
    store = NotesStore(tmp_path)
    with pytest.raises(ValueError):
        store.read("../secret.md")
    with pytest.raises(ValueError):
        store.write("bad/name.md", "x")


def test_delete_to_trash(tmp_path: Path) -> None:
    store = NotesStore(tmp_path)
    meta = store.create("T")
    store.delete(meta.name)
    assert not (tmp_path / meta.name).exists()
    assert any((tmp_path / ".trash").glob("*.md"))

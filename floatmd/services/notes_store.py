"""Files-first Markdown note storage."""

from __future__ import annotations

import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass
class NoteMeta:
    name: str
    title: str
    mtime_ms: int
    size_bytes: int


class NotesStore:
    def __init__(self, notes_dir: Path) -> None:
        self.root = notes_dir
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / ".trash").mkdir(exist_ok=True)

    def list_notes(self) -> list[NoteMeta]:
        items: list[NoteMeta] = []
        for path in sorted(self.root.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                text = ""
            st = path.stat()
            items.append(
                NoteMeta(
                    name=path.name,
                    title=_title_from_content(text, path.stem),
                    mtime_ms=int(st.st_mtime * 1000),
                    size_bytes=st.st_size,
                )
            )
        return items

    def read(self, name: str) -> str:
        path = self._safe_path(name, must_exist=True)
        return path.read_text(encoding="utf-8")

    def write(self, name: str, content: str) -> None:
        path = self._safe_path(name, must_exist=False)
        self._atomic_write(path, content)

    def create(self, title: str | None = None) -> NoteMeta:
        stamp = time.strftime("%Y-%m-%d-%H%M%S")
        name = f"{stamp}.md"
        # Avoid rare collisions within the same second
        n = 1
        while (self.root / name).exists():
            name = f"{stamp}-{n}.md"
            n += 1
        body = f"# {title.strip()}\n\n" if title and title.strip() else ""
        self.write(name, body)
        return NoteMeta(
            name=name,
            title=title.strip() if title and title.strip() else stamp,
            mtime_ms=int(time.time() * 1000),
            size_bytes=len(body.encode("utf-8")),
        )

    def rename(self, name: str, new_name: str) -> NoteMeta:
        src = self._safe_path(name, must_exist=True)
        if not new_name.endswith(".md"):
            new_name = f"{new_name}.md"
        dst = self._safe_path(new_name, must_exist=False)
        if dst.exists():
            raise FileExistsError(new_name)
        src.rename(dst)
        text = dst.read_text(encoding="utf-8")
        st = dst.stat()
        return NoteMeta(
            name=dst.name,
            title=_title_from_content(text, dst.stem),
            mtime_ms=int(st.st_mtime * 1000),
            size_bytes=st.st_size,
        )

    def delete(self, name: str) -> None:
        src = self._safe_path(name, must_exist=True)
        trash = self.root / ".trash"
        trash.mkdir(exist_ok=True)
        dst = trash / name
        if dst.exists():
            dst = trash / f"{int(time.time())}-{name}"
        src.rename(dst)

    def _safe_path(self, name: str, *, must_exist: bool) -> Path:
        if not name or not SAFE_NAME.match(name) or "/" in name or "\\" in name or ".." in name:
            raise ValueError(f"invalid note name: {name!r}")
        if not name.endswith(".md"):
            raise ValueError("note name must end with .md")
        path = (self.root / name).resolve()
        root_res = self.root.resolve()
        try:
            path.relative_to(root_res)
        except ValueError as exc:
            raise ValueError("path escapes notes dir") from exc
        if must_exist and not path.is_file():
            raise FileNotFoundError(name)
        return path

    def _atomic_write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
        try:
            with open(fd, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(content)
                fh.flush()
            Path(tmp_name).replace(path)
        except Exception:
            try:
                Path(tmp_name).unlink(missing_ok=True)
            except OSError:
                pass
            raise


def _title_from_content(text: str, fallback: str) -> str:
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip() or fallback
    return fallback

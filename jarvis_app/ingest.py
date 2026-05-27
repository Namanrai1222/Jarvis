from __future__ import annotations

from pathlib import Path

from .memory import MemoryStore


TEXT_EXTENSIONS = {".txt", ".md", ".py", ".json", ".csv", ".log"}
MAX_INGEST_BYTES = 2_000_000
MAX_SNIPPET_CHARS = 12_000


def ingest_path(memory: MemoryStore, path: Path) -> list[str]:
    stored: list[str] = []
    if path.is_file():
        _ingest_file(memory, path, stored)
        return stored

    for file_path in path.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in TEXT_EXTENSIONS:
            _ingest_file(memory, file_path, stored)
    return stored


def _ingest_file(memory: MemoryStore, file_path: Path, stored: list[str]) -> None:
    try:
        if file_path.stat().st_size > MAX_INGEST_BYTES:
            return
    except OSError:
        return

    try:
        with file_path.open("r", encoding="utf-8", errors="ignore") as handle:
            content = handle.read(MAX_SNIPPET_CHARS)
    except OSError:
        return
    if not content.strip():
        return

    trimmed = content[:MAX_SNIPPET_CHARS]
    memory.add_document(str(file_path), file_path.name, trimmed)
    stored.append(str(file_path))


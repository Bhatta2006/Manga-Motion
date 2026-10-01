"""Small on-disk store for immutable originals and atomic import manifests."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Iterator

from pipeline.cache import page_sha256
from pipeline.ingest import ImportFailure
from pipeline.runtime.scheduler import _single_heavy_model


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def read_json(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def safe_id(value: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", value):
        raise ImportFailure(f"Invalid library identifier: {value!r}")
    if value.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        raise ImportFailure(f"Reserved Windows identifier: {value!r}")
    return value


class ChapterStore:
    def __init__(self, root: Path, series: str, chapter: str) -> None:
        self.root = root.resolve()
        if os.name == "nt" and self.root.drive.upper() != "D:":
            raise ImportFailure("Library writes must stay on D:")
        self.series = safe_id(series)
        self.chapter = safe_id(chapter)
        self.series_root = self.root / self.series
        self.chapter_root = self.series_root / self.chapter
        # Resolve before any write, including pre-existing directory links/junctions.
        for path in (self.series_root, self.chapter_root, self.chapter_root / "sources",
                     self.chapter_root / "pages", self.chapter_root / "cache"):
            self.checked(path)

    def checked(self, path: Path) -> Path:
        if not path.resolve().is_relative_to(self.root):
            raise ImportFailure(f"Store path escapes library: {path}")
        return path

    @contextmanager
    def lock(self) -> Iterator[None]:
        # Reuse the tested OS lock primitive, with a distinct library lock file.
        # No models are loaded and this does not take the scheduler's model lock.
        with _single_heavy_model(self.checked(self.root / "import.lock")):
            yield

    def copy_original(self, stream: BinaryIO, suffix: str, max_bytes: int) -> tuple[Path, str]:
        parent = self.checked(self.chapter_root / "sources")
        parent.mkdir(parents=True, exist_ok=True)
        temp = parent / f".{uuid.uuid4().hex}.tmp"
        digest = hashlib.sha256()
        length = 0
        try:
            with temp.open("xb") as out:
                while block := stream.read(1024 * 1024):
                    length += len(block)
                    if length > max_bytes:
                        raise ImportFailure(f"Source exceeds {max_bytes} byte limit")
                    digest.update(block)
                    out.write(block)
            value = digest.hexdigest()
            destination = self.checked(parent / f"{value}{suffix}")
            if not destination.is_file() or page_sha256(destination) != value:
                os.replace(temp, destination)
            return destination, value
        finally:
            temp.unlink(missing_ok=True)

    def relative(self, path: Path) -> str:
        return self.checked(path).relative_to(self.chapter_root).as_posix()

    def asset(self, relative: str) -> Path:
        path = self.checked(self.chapter_root / relative)
        if not path.resolve().is_relative_to(self.chapter_root.resolve()):
            raise ImportFailure(f"Asset escapes chapter: {relative}")
        return path

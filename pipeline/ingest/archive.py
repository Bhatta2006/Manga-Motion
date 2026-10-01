"""Enumerate ZIP members without extractall or trusting member paths."""

from __future__ import annotations

import re
import stat
from pathlib import PurePosixPath
from zipfile import ZipFile, ZipInfo

from pipeline.ingest import ImportFailure

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".gif", ".avif"}
MAX_PAGES = 2000
MAX_IMAGE_BYTES = 128 * 2**20
MAX_SOURCE_BYTES = 2 * 2**30
MAX_EXPANDED_BYTES = 4 * 2**30


def natural_key(name: str) -> tuple:
    return tuple((0, int(piece)) if piece.isdecimal() else (1, piece.casefold())
                 for piece in re.split(r"(\d+)", name)) + ((2, name),)


def validate_name(name: str) -> str:
    if "\\" in name or "\x00" in name or ":" in name or name.startswith("/"):
        raise ImportFailure(f"Unsafe archive member: {name!r}")
    parts = name.rstrip("/").split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ImportFailure(f"Unsafe archive member: {name!r}")
    return PurePosixPath(*parts).as_posix()


def image_members(archive: ZipFile) -> tuple[list[ZipInfo], list[str]]:
    if len(archive.infolist()) > MAX_PAGES * 4:
        raise ImportFailure("Archive has too many entries")
    seen = set()
    pages = []
    ignored = []
    expanded = 0
    for entry in archive.infolist():
        name = validate_name(entry.orig_filename)
        key = name.casefold()
        if key in seen:
            raise ImportFailure(f"Duplicate archive member: {name}")
        seen.add(key)
        mode = entry.external_attr >> 16
        if stat.S_ISLNK(mode) or stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise ImportFailure(f"Non-regular archive member: {name}")
        if entry.flag_bits & 1:
            raise ImportFailure(f"Encrypted archive member: {name}")
        expanded += entry.file_size
        if expanded > MAX_EXPANDED_BYTES:
            raise ImportFailure(f"Archive expansion limit exceeded at: {name}")
        if entry.file_size > MAX_IMAGE_BYTES:
            raise ImportFailure(f"Archive member exceeds size limit: {name}")
        if entry.file_size > 2**20 and entry.file_size / max(1, entry.compress_size) > 1000:
            raise ImportFailure(f"Archive compression ratio exceeds limit: {name}")
        if entry.is_dir():
            continue
        if PurePosixPath(name).suffix.lower() in IMAGE_SUFFIXES and "__MACOSX" not in PurePosixPath(name).parts:
            pages.append(entry)
        else:
            ignored.append(name)
    if not pages or len(pages) > MAX_PAGES:
        raise ImportFailure(f"Archive requires 1..{MAX_PAGES} image pages; found {len(pages)}")
    return sorted(pages, key=lambda item: natural_key(item.filename)), ignored

"""Page-hash and stage-version based cache for intermediate JSON."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def page_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def cache_key(page_hash: str, stage: str, revision: str, config: dict[str, Any]) -> str:
    payload = json.dumps(
        {"page_sha256": page_hash, "stage": stage, "revision": revision, "config": config},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class JsonStageCache:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path(self, stage: str, key: str) -> Path:
        return self.root / stage / f"{key}.json"

    def read(self, stage: str, key: str) -> dict[str, Any] | None:
        path = self.path(stage, key)
        if not path.is_file():
            return None
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def write(self, stage: str, key: str, value: dict[str, Any]) -> Path:
        path = self.path(stage, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(f".{os.getpid()}.tmp")
        with temp.open("w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
        os.replace(temp, path)
        return path


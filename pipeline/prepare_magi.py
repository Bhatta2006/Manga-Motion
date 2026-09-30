"""Fetch the exact Magi v3 snapshot into the D: cache and verify its weight hash."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    runtime = Path(os.environ.get("MANGAMOTION_RUNTIME", ""))
    cache = Path(os.environ.get("HF_HUB_CACHE", ""))
    if not runtime.is_dir() or runtime.drive.upper() != "D:" or not cache.is_dir() or cache.drive.upper() != "D:":
        raise RuntimeError("Dot-source scripts/enter-runtime.ps1 before downloading; all files must stay on D:")

    from huggingface_hub import snapshot_download

    manifest = json.loads((project / "pipeline" / "model_manifest.json").read_text(encoding="utf-8"))["magiv3"]
    snapshot = Path(
        snapshot_download(
            repo_id=manifest["repo_id"],
            revision=manifest["revision"],
            cache_dir=cache,
            max_workers=2,
        )
    )
    if snapshot.drive.upper() != "D:":
        raise RuntimeError(f"Model snapshot escaped D: {snapshot}")
    weight = snapshot / manifest["weight_file"]
    digest = hashlib.sha256()
    with weight.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    if weight.stat().st_size != manifest["weight_bytes"] or digest.hexdigest() != manifest["weight_sha256"]:
        raise RuntimeError("Magi v3 weight size or SHA-256 differs from the pinned official model file")
    record = {
        "snapshot": str(snapshot),
        "revision": manifest["revision"],
        "weight_bytes": weight.stat().st_size,
        "weight_sha256": digest.hexdigest(),
    }
    (runtime / "magiv3-verification.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()

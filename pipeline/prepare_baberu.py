"""Fetch only the verified Baberu ONNX inference files into the D-drive cache."""

import json
import os
from pathlib import Path

from pipeline.cache import page_sha256

MODEL_ID = "genshiai-daichi/baberu-ocr"
MODEL_REVISION = "d9cc13153e9a1cd8fdfa3b7b1cc329da2020aeae"
WEIGHTS = {
    "onnx/vision_fp16.onnx": (172917304, "4ce333804846b23f1983376efe363c164d4624ecc6bd16f99a15a859d8423117"),
    "onnx/decoder_prefill_int8.onnx": (35133596, "4f8d28d4e5e8b6c7f3a4510663aa0a9199a7eec06bcb1dc0afb3ca571494e97f"),
    "onnx/decoder_step_int8.onnx": (33929034, "2eaf792ca70b67e55140ef0bcfbfc3c3b1e07d72ca277dcc46aae27c81f27ac8"),
}


def main() -> None:
    for name in ("MANGAMOTION_RUNTIME", "HF_HUB_CACHE", "TEMP", "TMP"):
        if Path(os.environ.get(name, "")).drive.upper() != "D:":
            raise RuntimeError(f"{name} must point to D:")
    from huggingface_hub import snapshot_download

    snapshot = Path(snapshot_download(
        MODEL_ID, revision=MODEL_REVISION, cache_dir=os.environ["HF_HUB_CACHE"],
        allow_patterns=[*WEIGHTS, "onnx_infer.py", "README.md", "LICENSE", "config.json",
                        "tokenizer/vocab.json", "tokenizer/tokenizer_config.json"],
        max_workers=2,
    ))
    records = []
    for name, (size, digest) in WEIGHTS.items():
        path = snapshot / name
        if path.stat().st_size != size or page_sha256(path) != digest:
            raise RuntimeError(f"Weight verification failed: {path}")
        records.append({"file": name, "bytes": size, "sha256": digest})
    record = {"repo_id": MODEL_ID, "revision": MODEL_REVISION, "snapshot": str(snapshot), "weights": records}
    target = Path(os.environ["MANGAMOTION_RUNTIME"]) / "baberu-verification.json"
    target.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()

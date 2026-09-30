"""Magi v3 detection and text-crop OCR adapter, pinned to one model revision."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any


MODEL_ID = "ragavsachdeva/magiv3"
MODEL_REVISION = "c9d0a345b07be759be61c5cd9570ce2df73ee80b"


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "tolist"):
        return _jsonable(value.tolist())
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"Magi returned an unsupported JSON value: {type(value).__name__}")


def _crop_box(raw_box: Any, width: int, height: int, pad: int = 8) -> tuple[int, int, int, int] | None:
    if not isinstance(raw_box, (list, tuple)) or len(raw_box) != 4:
        return None
    try:
        x1, y1, x2, y2 = (float(value) for value in raw_box)
    except (TypeError, ValueError):
        return None
    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        return None
    return (
        max(0, int(x1) - pad),
        max(0, int(y1) - pad),
        min(width, int(x2 + 0.9999) + pad),
        min(height, int(y2 + 0.9999) + pad),
    )


class MagiV3Adapter:
    stage_name = "magiv3"
    revision = MODEL_REVISION
    heavy = True

    def __init__(self, include_ocr: bool = True) -> None:
        self.include_ocr = include_ocr
        self.stage_name = "magiv3" if include_ocr else "magiv3-detection"
        self._model: Any = None
        self._processor: Any = None

    def load(self) -> None:
        for name in ("MANGAMOTION_RUNTIME", "HF_HOME", "HF_HUB_CACHE", "HF_MODULES_CACHE", "TEMP", "TMP"):
            value = os.environ.get(name)
            if not value or Path(value).drive.upper() != "D:":
                raise RuntimeError(f"{name} must point to D:; dot-source scripts/enter-runtime.ps1 first")

        import torch
        from huggingface_hub import snapshot_download
        from transformers import AutoModelForCausalLM, AutoProcessor

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable; Magi v3 GPU feasibility cannot be measured")
        snapshot = snapshot_download(
            repo_id=MODEL_ID,
            revision=self.revision,
            cache_dir=os.environ["HF_HUB_CACHE"],
            local_files_only=True,
        )
        self._processor = AutoProcessor.from_pretrained(
            snapshot,
            trust_remote_code=True,
            local_files_only=True,
        )
        self._model = AutoModelForCausalLM.from_pretrained(
            snapshot,
            torch_dtype=torch.float16,
            trust_remote_code=True,
            local_files_only=True,
        ).cuda().eval()

    def run_page(self, page: Path) -> dict[str, Any]:
        if self._model is None or self._processor is None:
            raise RuntimeError("Magi v3 adapter is not loaded")
        import numpy as np
        from PIL import Image

        with Image.open(page) as source:
            image = np.asarray(source.convert("RGB"))
        height, width = image.shape[:2]

        started = time.perf_counter()
        detections = self._model.predict_detections_and_associations([image], self._processor)[0]
        detection_seconds = time.perf_counter() - started

        ocr_items = []
        ocr_seconds = 0.0
        for index, raw_box in enumerate(detections.get("texts", []) if self.include_ocr else []):
            box = _crop_box(raw_box, width, height)
            if box is None:
                ocr_items.append({"text_index": index, "bbox": _jsonable(raw_box), "status": "invalid_box", "confidence": None})
                continue
            crop = image[box[1] : box[3], box[0] : box[2]]
            started = time.perf_counter()
            raw_ocr = self._model.predict_ocr([crop], self._processor)[0]
            ocr_seconds += time.perf_counter() - started
            ocr_items.append(
                {
                    "text_index": index,
                    "bbox": _jsonable(raw_box),
                    "crop_bbox": list(box),
                    "raw": _jsonable(raw_ocr),
                    "confidence": None,
                    "confidence_note": "The pinned Magi v3 inference method does not return OCR confidence",
                }
            )

        return {
            "image_size": [width, height],
            "detections": _jsonable(detections),
            "ocr": ocr_items,
            "confidence_note": "The pinned Magi v3 inference method exposes thresholded associations, not calibrated scores",
            "timings": {
                "detection_seconds": round(detection_seconds, 4),
                "ocr_seconds": round(ocr_seconds, 4),
            },
        }

    def unload(self) -> None:
        self._model = None
        self._processor = None

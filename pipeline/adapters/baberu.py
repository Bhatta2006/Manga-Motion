"""Pinned Baberu ONNX crop OCR behind the single-model stage interface."""

from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from pipeline.adapters.magi import _crop_box
from pipeline.cache import page_sha256
from pipeline.prepare_baberu import MODEL_ID, MODEL_REVISION


def baberu_cache_config(threads: int, vision_device: str, split_tall: bool = True) -> dict[str, Any]:
    import onnxruntime as ort

    return {"adapter_version": 3, "runtime_version": ort.__version__, "crop_pad_px": 8,
            "threads": threads, "vision_device": vision_device, "split_tall": split_tall,
            "max_new_tokens": 256, "repetition_penalty": 1.2, "max_content_run": 12,
            "weights": "vision_fp16-decoder_int8"}


def detection_fingerprint(record: dict[str, Any]) -> str:
    """Only inputs affecting OCR invalidate it; JSON formatting never does."""
    inputs = {"detector_revision": record["adapter_revision"], "texts": record["detections"]["texts"]}
    encoded = json.dumps(inputs, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _split_tall_crop(image: Any) -> list[tuple[int, int, int, int]]:
    """Split only at a clear horizontal gap; preserve every crop pixel."""
    width, height = image.size
    whole = (0, 0, width, height)
    if height <= 2 * width or height < 150:
        return [whole]
    import numpy as np

    gray = np.asarray(image.convert("L"))
    # Exclude curved bubble borders at the edges when looking for text gaps.
    inner = gray[:, int(width * 0.12):max(int(width * 0.88), int(width * 0.12) + 1)]
    blank = (inner < 160).sum(axis=1) == 0
    candidates = []
    for row in range(int(height * 0.35) + 1, int(height * 0.65) - 1):
        if blank[row - 1:row + 2].all():
            candidates.append(row)
    if not candidates:
        return [whole]
    cut = min(candidates, key=lambda row: abs(row - height / 2))
    return [(0, 0, width, cut), (0, cut, width, height)]


class BaberuOnnxAdapter:
    stage_name = "baberu-ocr"
    revision = MODEL_REVISION
    heavy = True  # Serialize CPU models too, to bound system RAM.

    def __init__(self, detections: dict[str, dict[str, Any]], threads: int = 4,
                 vision_device: str = "cpu", split_tall: bool = True) -> None:
        if threads not in (1, 2, 4, 8):
            raise ValueError("Use a measured thread limit: 1, 2, 4, or 8")
        self.detections = detections
        self.threads = threads
        if vision_device not in ("cpu", "cuda"):
            raise ValueError("Vision device must be cpu or cuda")
        self.vision_device = vision_device
        self.split_tall = split_tall
        self._engine: Any = None

    def load(self) -> None:
        for name in ("MANGAMOTION_RUNTIME", "HF_HUB_CACHE", "TEMP", "TMP"):
            if Path(os.environ.get(name, "")).drive.upper() != "D:":
                raise RuntimeError(f"{name} must point to D:")
        import onnxruntime as ort
        from huggingface_hub import snapshot_download

        if self.vision_device == "cuda":
            # Official ORT guidance: import the existing D-drive Torch runtime
            # to preload compatible CUDA/cuDNN DLLs. No Torch model is loaded.
            import torch

            if not torch.cuda.is_available() or "CUDAExecutionProvider" not in ort.get_available_providers():
                raise RuntimeError("CUDA execution provider is unavailable; no silent CPU fallback")

        snapshot = Path(snapshot_download(MODEL_ID, revision=MODEL_REVISION,
                                         cache_dir=os.environ["HF_HUB_CACHE"], local_files_only=True))
        spec = importlib.util.spec_from_file_location("mangamotion_pinned_baberu", snapshot / "onnx_infer.py")
        if spec is None or spec.loader is None:
            raise RuntimeError("Pinned Baberu inference source is unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Preserve the author's preprocessing and decode loop. Only session
        # creation differs: cap CPU threads and disable idle worker spinning.
        engine = module.BaberuOnnxOCR.__new__(module.BaberuOnnxOCR)
        self._engine = engine  # Keep partial initialization releasable on failure.
        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        options.intra_op_num_threads = self.threads
        options.inter_op_num_threads = 1
        options.add_session_config_entry("session.intra_op.allow_spinning", "0")
        for attr, filename in (("vis", "vision_fp16.onnx"), ("pre", "decoder_prefill_int8.onnx"),
                               ("stp", "decoder_step_int8.onnx")):
            providers: list[Any] = ["CPUExecutionProvider"]
            if attr == "vis" and self.vision_device == "cuda":
                providers = [("CUDAExecutionProvider", {"gpu_mem_limit": 512 * 2**20,
                    "arena_extend_strategy": "kSameAsRequested", "cudnn_conv_algo_search": "HEURISTIC",
                    "use_tf32": 0}), "CPUExecutionProvider"]
            session = ort.InferenceSession(str(snapshot / "onnx" / filename), options, providers=providers)
            if attr == "vis" and self.vision_device == "cuda" and session.get_providers()[0] != "CUDAExecutionProvider":
                raise RuntimeError("CUDA provider initialization failed; no silent CPU fallback")
            setattr(engine, attr, session)
        engine.vocab = module.Vocab(snapshot / "tokenizer" / "vocab.json")

    def run_page(self, page: Path) -> dict[str, Any]:
        if self._engine is None:
            raise RuntimeError("Baberu is not loaded")
        from PIL import Image

        digest = page_sha256(page)
        detection = self.detections[digest]
        if detection["page_sha256"] != digest:
            raise ValueError("Detection/source hash mismatch")
        items = []
        with Image.open(page) as source:
            image = source.convert("RGB")
        width, height = image.size
        for index, raw_box in enumerate(detection["detections"]["texts"]):
            box = _crop_box(raw_box, width, height, pad=8)
            if box is None:
                raise ValueError(f"Invalid text box {index}: {raw_box}")
            started = time.perf_counter()
            crop = image.crop(box)
            parts = _split_tall_crop(crop) if self.split_tall else [(0, 0, crop.width, crop.height)]
            segments = []
            for part in parts:
                value = self._engine(crop.crop(part), max_new_tokens=256,
                                     repetition_penalty=1.2, max_content_run=12)
                segments.append({"crop_bbox": [box[0] + part[0], box[1] + part[1],
                                               box[0] + part[2], box[1] + part[3]], "text": value})
            text = " ".join(segment["text"].strip() for segment in segments)
            seconds = time.perf_counter() - started
            status = "text_returned_unverified" if text.strip() else "empty_needs_review"
            if any(len(segment["text"]) >= 256 for segment in segments):
                status = "possible_token_limit_needs_review"
            items.append({"text_index": index, "bbox": raw_box, "crop_bbox": list(box),
                          "text": text, "segments": segments, "status": status, "run_seconds": round(seconds, 4),
                          "confidence": None,
                          "confidence_note": "Pinned Baberu inference returns text, not calibrated confidence"})
        return {"image_size": [width, height], "ocr": items,
                "timings": {"ocr_seconds": round(sum(item["run_seconds"] for item in items), 4)},
                "execution": {"vision_device": self.vision_device, "decoder_device": "cpu", "threads": self.threads}}

    def unload(self) -> None:
        self._engine = None

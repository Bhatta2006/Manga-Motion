"""Chapter crop OCR: compose the already verified, swappable Baberu adapter."""

from __future__ import annotations

from pathlib import Path

from pipeline.adapters.baberu import BaberuOnnxAdapter, baberu_cache_config
from pipeline.cache import page_sha256
from pipeline.vision.crops import crop_boxes


class ChapterCropOcrAdapter(BaberuOnnxAdapter):
    def run_page(self, page: Path) -> dict:
        detection = self.detections[page_sha256(page)]
        expected = crop_boxes(detection["detections"]["texts"], detection["image_size"])
        if [0, 0, *detection["image_size"]] in expected:
            raise ValueError("Whole-page OCR is disabled; review the oversized text detection")
        result = super().run_page(page)
        if result["image_size"] != detection["image_size"]:
            raise ValueError(f"Detection/source size mismatch: {page.name}")
        if [item["crop_bbox"] for item in result["ocr"]] != expected:
            raise ValueError("OCR must use only the recorded padded text crops")
        result["crop_audit"] = {"mode": "detected-text-crops-only", "pad_px": 8,
                                "crop_count": len(expected), "page_input_to_ocr_engine": False}
        return result


def chapter_ocr_config(threads: int, vision_device: str, source_language: str) -> dict:
    return {**baberu_cache_config(threads, vision_device, split_tall=source_language == "en"),
            "chapter_crop_adapter": 1, "source_language": source_language}

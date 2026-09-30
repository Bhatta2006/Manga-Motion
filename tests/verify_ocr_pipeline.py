"""Audit the optimized private five-page pipeline after cold/warm execution."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.cache import page_sha256


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    cold = json.loads((root / "reports/M0a-opt-pipeline-cold.json").read_text())
    warm = json.loads((root / "reports/M0a-opt-pipeline-warm.json").read_text())
    baseline = json.loads((root / "reports/M0a-cold-metrics.json").read_text())
    assert cold["error"] is warm["error"] is None
    for stage in ("detection", "ocr"):
        assert cold["stages"][stage]["cache_hits"] == 0
        assert warm["stages"][stage]["cache_hits"] == 5
        assert warm["stages"][stage]["load_seconds"] == 0
        assert warm["stages"][stage]["unload_seconds"] == 0
        assert cold["stages"][stage]["device_vram_peak_mib"] < 6141
    # The next model starts far below the Magi weight footprint, after unload.
    assert cold["stages"]["ocr"]["device_vram_baseline_mib"] < 512
    crops = segments = 0
    for index, metric in enumerate(baseline["pages"], 1):
        digest = metric["page_sha256"]
        assert page_sha256(Path(metric["page"])) == digest
        folder = root / "library/golden-opt-final/cache" / f"p{index:03d}-{digest[:12]}"
        detection = json.loads((folder / "detections.json").read_text())
        ocr = json.loads((folder / "ocr.json").read_text(encoding="utf-8"))
        assert detection["page_sha256"] == ocr["page_sha256"] == digest
        assert len(detection["detections"]["texts"]) == len(ocr["ocr"])
        width, height = ocr["image_size"]
        for item in ocr["ocr"]:
            assert item["bbox"] == detection["detections"]["texts"][item["text_index"]]
            assert item["text"].strip() and item["confidence"] is None
            assert item["status"] == "text_returned_unverified"
            x1, y1, x2, y2 = item["crop_bbox"]
            assert 0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height
            cursor = y1
            for segment in item["segments"]:
                left, top, right, bottom = segment["crop_bbox"]
                assert (left, top, right) == (x1, cursor, x2)
                assert top < bottom <= y2
                cursor = bottom
                segments += 1
            assert cursor == y2  # No missing pixels or overlapping segments.
            crops += 1
    assert crops == 53
    print(json.dumps({"checks": "PASS", "sources_unchanged": 5, "crops": crops,
                      "inference_segments": segments, "warm_stage_hits": 10,
                      "mean_page_run_seconds": sum(item["run_seconds"] for item in cold["pages"]) / 5,
                      "cold_pipeline_seconds": cold["elapsed_seconds"],
                      "warm_pipeline_seconds": warm["elapsed_seconds"]}, indent=2))


if __name__ == "__main__":
    main()

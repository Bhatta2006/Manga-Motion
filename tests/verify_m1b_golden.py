"""Score private M1b output and verify all four stage caches replay unchanged."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.analyze_chapter import analyze_chapter
from pipeline.cache import page_sha256
from pipeline.store import write_json
from pipeline.vision.evaluate import score_analysis


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    private = root / "library/golden-m1b"
    reference = json.loads((private / "reference.json").read_text(encoding="utf-8"))
    output = private / "chapter/analysis.json"
    before = page_sha256(output)
    with patch("pipeline.adapters.magi.MagiV3Adapter.load", side_effect=AssertionError("Magi loaded on warm cache")), \
         patch("pipeline.adapters.ocr.ChapterCropOcrAdapter.load", side_effect=AssertionError("Baberu loaded on warm cache")):
        analysis, warm = analyze_chapter(root / "library", "golden-m1b", "chapter", Path(os.environ["MANGAMOTION_RUNTIME"]))
    assert page_sha256(output) == before
    assert all(stage["cache_hits"] == 5 for stage in warm["stages"])
    quality = score_analysis(analysis, reference)
    inventory = json.loads((root / "reports/M0a-cold-metrics.json").read_text(encoding="utf-8"))
    segments = 0
    for original, page in zip(inventory["pages"], analysis["pages"]):
        assert original["page_sha256"] == page["page_sha256"] == page_sha256(Path(original["page"]))
        assert page_sha256(private / "chapter" / page["image"]) == page["page_sha256"]
        geometry = json.loads((private / "chapter/cache/pages" / page["page_sha256"] / "geometry.json").read_text(encoding="utf-8"))
        raw_ocr = json.loads((private / "chapter/cache/pages" / page["page_sha256"] / "ocr.json").read_text(encoding="utf-8"))
        assert raw_ocr["crop_audit"]["page_input_to_ocr_engine"] is False
        assert len(raw_ocr["ocr"]) == len(geometry["detections"]["texts"])
        for item, box in zip(raw_ocr["ocr"], geometry["detections"]["texts"]):
            assert item["bbox"] == box
            x1, y1, x2, y2 = item["crop_bbox"]
            width, height = page["size"]
            assert 0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height
            assert (x1, y1, x2, y2) != (0, 0, width, height)
            cursor = y1
            for part in item["segments"]:
                a, b, c, d = part["crop_bbox"]
                assert (a, b, c) == (x1, cursor, x2)
                assert b < d <= y2
                cursor = d
                segments += 1
            assert cursor == y2
    cold = json.loads((root / "reports/M1b-cold.json").read_text(encoding="utf-8"))
    heavy = [stage for stage in cold["stages"] if stage["heavy"]]
    assert all(stage["cache_hits"] == 0 and stage["error"] is None for stage in heavy)
    assert all(stage["device_vram_peak_mib"] < 6141 for stage in heavy)
    assert heavy[1]["device_vram_baseline_mib"] < 512
    audit = {"original_and_served_hashes_unchanged": 5, "text_crops": warm["text_crops_total"],
             "inference_segments": segments, "whole_page_ocr_calls": 0,
             "sequential_heavy_stage_memory_checks": "PASS", "analysis_hash_unchanged": True}
    write_json(root / "reports/M1b-audit.json", audit)
    write_json(root / "reports/M1b-warm.json", warm)
    write_json(root / "reports/M1b-quality.json", quality)
    print(json.dumps({"warm_cache_hits": [m["cache_hits"] for m in warm["stages"]],
                      "warm_seconds": warm["elapsed_seconds"], "analysis_hash_unchanged": True,
                      "audit": audit,
                      "quality": quality}, indent=2))


if __name__ == "__main__":
    main()

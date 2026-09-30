"""Audit private five-page M0a artifacts after cold inference and cache replay."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image

from pipeline.cache import JsonStageCache, cache_key, page_sha256


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    cold = json.loads((root / "reports/M0a-cold-metrics.json").read_text())
    warm = json.loads((root / "reports/M0a-warm-metrics.json").read_text())
    assert cold["pages_total"] == warm["pages_total"] == 5
    assert cold["cache_hits"] == 0 and warm["cache_hits"] == 5
    assert cold["error"] is None and warm["error"] is None
    assert warm["load_seconds"] == warm["unload_seconds"] == 0
    assert cold["device_vram_peak_mib"] < 6141
    cache_root = root / "library/golden-m0/cache"
    cache = JsonStageCache(cache_root / "stage")
    rows = []
    for index, metric in enumerate(cold["pages"], 1):
        page = Path(metric["page"])
        digest = page_sha256(page)
        assert digest == metric["page_sha256"] == warm["pages"][index - 1]["page_sha256"]
        key = cache_key(digest, cold["stage"], cold["revision"], {"crop_pad_px": 8})
        cached = cache.read(cold["stage"], key)
        assert cached and cached["page_sha256"] == digest
        with Image.open(page) as image:
            width, height = image.size
        assert cached["image_size"] == [width, height]
        folder = cache_root / f"p{index:03d}-{digest[:12]}"
        detections = json.loads((folder / "detections.json").read_text())
        ocr = json.loads((folder / "ocr.json").read_text())
        assert detections["page_sha256"] == ocr["page_sha256"] == digest
        assert detections["detections"] == cached["detections"]
        for kind in ("panels", "texts", "characters", "tails"):
            for box in detections["detections"][kind]:
                assert len(box) == 4 and all(math.isfinite(value) for value in box)
                assert 0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height
        assert len(ocr["ocr"]) == len(detections["detections"]["texts"])
        returned = 0
        for item, original in zip(ocr["ocr"], cached["ocr"]):
            assert item["confidence"] is None
            assert item["raw"] == original["raw"]
            x1, y1, x2, y2 = item["crop_bbox"]
            assert 0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height
            assert len(item["raw"]["ocr_texts"]) == len(item["raw"]["bboxes"])
            has_text = any(item["raw"]["ocr_texts"])
            assert item["status"] == ("text_returned_unverified" if has_text else "empty_needs_review")
            returned += int(has_text)
        rows.append({
            "index": index, "filename": page.name, "page_sha256": digest,
            "source_bytes": page.stat().st_size, "dimensions": [width, height],
            "panels": len(cached["detections"]["panels"]),
            "texts": len(cached["ocr"]), "ocr_crops_with_text": returned,
            "run_seconds": metric["run_seconds"], **cached["timings"],
        })
    report = {"checks": "PASS", "source_hashes_unchanged": 5,
              "cache_replay_hits": 5, "pages": rows,
              "mean_run_seconds": sum(row["run_seconds"] for row in rows) / 5}
    (root / "reports/M0a-golden-audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

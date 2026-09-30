"""Run five-page detection then specialist OCR, unloading between stages."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

from pipeline.adapters.baberu import BaberuOnnxAdapter, baberu_cache_config, detection_fingerprint
from pipeline.adapters.magi import MagiV3Adapter
from pipeline.cache import JsonStageCache, page_sha256
from pipeline.runtime.scheduler import StageExecutionError, StageScheduler


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pages", nargs=5, type=Path, help="five real manga page files in reading order")
    parser.add_argument("--chapter", required=True, help="private library name, e.g. golden-m0")
    parser.add_argument("--run-label", default="latest")
    parser.add_argument("--ocr-vision-device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--ocr-threads", type=int, choices=(1, 2, 4, 8), default=4)
    args = parser.parse_args()

    runtime = Path(os.environ.get("MANGAMOTION_RUNTIME", ""))
    if not runtime.is_dir() or runtime.drive.upper() != "D:":
        parser.error("Dot-source scripts/enter-runtime.ps1 so all caches and temp files stay on D:")
    for name in (args.chapter, args.run_label):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            parser.error("Names must contain only letters, numbers, underscores, or hyphens")

    project = Path(__file__).resolve().parents[1]
    cache_root = project / "library" / args.chapter / "cache"
    pages = [page.resolve() for page in args.pages]
    scheduler = StageScheduler(runtime, JsonStageCache(cache_root / "stage"))
    report_path = project / "reports" / f"M0a-opt-pipeline-{args.run_label}.json"
    stages = {}
    started = time.perf_counter()
    try:
        detections, stages["detection"] = scheduler.run_pages(
            MagiV3Adapter(include_ocr=False), pages,
            {"adapter_version": 1, "include_ocr": False, "dtype": "float16"})
        # Detection has fully unloaded and cleared CUDA before OCR loads.
        inputs, page_configs = {}, {}
        for index, result in enumerate(detections, 1):
            digest = result["page_sha256"]
            target = cache_root / f"p{index:03d}-{digest[:12]}" / "detections.json"
            record = {"page_sha256": digest, "adapter_revision": result["adapter_revision"],
                      "detections": result["detections"]}
            write_json(target, record)
            inputs[digest] = record
            page_configs[digest] = {"text_boxes_sha256": detection_fingerprint(record)}
        config = baberu_cache_config(args.ocr_threads, args.ocr_vision_device)
        results, stages["ocr"] = scheduler.run_pages(
            BaberuOnnxAdapter(inputs, args.ocr_threads, args.ocr_vision_device),
            pages, config, page_configs)
        stages["ocr"]["config"] = config
        stages["ocr"]["page_configs"] = page_configs
    except StageExecutionError as exc:
        stages["failed_stage"] = exc.metrics
        write_json(report_path, {"stages": stages, "error": str(exc)})
        raise

    for index, result in enumerate(results, start=1):
        target = cache_root / f"p{index:03d}-{result['page_sha256'][:12]}" / "ocr.json"
        write_json(target, result)

    per_stage_pages = {name: {item["page_sha256"]: item for item in metric["pages"]}
                       for name, metric in stages.items()}
    page_metrics = []
    for result in results:
        digest = result["page_sha256"]
        page_metrics.append({"page_sha256": digest, "image_size": result["image_size"],
            "run_seconds": round(sum(mapping[digest]["run_seconds"] for mapping in per_stage_pages.values()), 4),
            "text_crops": len(result["ocr"]),
            "nonempty_crops": sum(bool(item["text"].strip()) for item in result["ocr"])})
    report = {"stages": stages, "pages": page_metrics,
              "elapsed_seconds": round(time.perf_counter() - started, 4), "error": None}
    write_json(report_path, report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

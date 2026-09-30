"""Compare specialist OCR on the existing five-page M0a detection set."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from pipeline.adapters.baberu import BaberuOnnxAdapter, baberu_cache_config, detection_fingerprint
from pipeline.cache import JsonStageCache, page_sha256
from pipeline.runtime.scheduler import StageExecutionError, StageScheduler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chapter", default="golden-m0")
    parser.add_argument("--threads", type=int, choices=(1, 2, 4, 8), default=4)
    parser.add_argument("--run-label", required=True)
    parser.add_argument("--vision-device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--no-split-tall", action="store_true")
    args = parser.parse_args()
    for value in (args.chapter, args.run_label):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            parser.error("Names must contain only letters, numbers, underscores, or hyphens")
    project = Path(__file__).resolve().parents[1]
    runtime = Path(os.environ.get("MANGAMOTION_RUNTIME", ""))
    if not runtime.is_dir() or runtime.drive.upper() != "D:":
        parser.error("Dot-source scripts/enter-runtime.ps1 first")
    baseline = json.loads((project / "reports/M0a-cold-metrics.json").read_text())
    pages = [Path(item["page"]) for item in baseline["pages"]]
    if len(pages) != 5:
        parser.error("This follow-up requires the five real M0a pages")
    cache_root = project / "library" / args.chapter / "cache"
    detections, dependencies = {}, {}
    for index, (page, metric) in enumerate(zip(pages, baseline["pages"]), 1):
        digest = page_sha256(page)
        if digest != metric["page_sha256"]:
            raise ValueError(f"Source changed since M0a: {page.name}")
        path = cache_root / f"p{index:03d}-{digest[:12]}" / "detections.json"
        record = json.loads(path.read_text())
        if record["page_sha256"] != digest:
            raise ValueError("Detection/source hash mismatch")
        detections[digest] = record
        dependencies[digest] = detection_fingerprint(record)
    config = baberu_cache_config(args.threads, args.vision_device, not args.no_split_tall)
    page_configs = {digest: {"text_boxes_sha256": value} for digest, value in dependencies.items()}
    scheduler = StageScheduler(runtime, JsonStageCache(cache_root / "stage"))
    report = project / "reports" / f"M0a-opt-{args.vision_device}-t{args.threads}-{args.run_label}.json"
    try:
        results, metrics = scheduler.run_pages(
            BaberuOnnxAdapter(detections, args.threads, args.vision_device, not args.no_split_tall),
            pages, config, page_configs)
    except StageExecutionError as exc:
        report.write_text(json.dumps(exc.metrics, indent=2) + "\n", encoding="utf-8")
        raise
    for index, result in enumerate(results, 1):
        target = cache_root / f"p{index:03d}-{result['page_sha256'][:12]}" / f"baberu-{args.vision_device}-t{args.threads}.json"
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    metrics["config"] = config
    metrics["page_configs"] = page_configs
    metrics["crops_total"] = sum(len(result["ocr"]) for result in results)
    metrics["nonempty_crops"] = sum(bool(item["text"].strip()) for result in results for item in result["ocr"])
    report.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()

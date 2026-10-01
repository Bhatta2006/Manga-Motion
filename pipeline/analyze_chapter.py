"""M1b imported chapter -> normalized panels/order + detected-crop OCR."""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from importlib.metadata import version
from pathlib import Path

from pipeline.adapters.magi import MagiV3Adapter
from pipeline.adapters.ocr import ChapterCropOcrAdapter, chapter_ocr_config
from pipeline.cache import JsonStageCache, page_sha256
from pipeline.ingest import ImportFailure
from pipeline.ingest.hashes import object_hash
from pipeline.runtime.scheduler import StageExecutionError, StageScheduler
from pipeline.store import ChapterStore, read_json, write_json
from pipeline.vision.panels import NORMALIZATION_REVISION, normalize_detections
from pipeline.vision.text import text_metadata


class NormalizeAdapter:
    stage_name = "vision-normalize"
    revision = NORMALIZATION_REVISION
    heavy = False

    def __init__(self, records: dict, direction: str) -> None:
        self.records = records
        self.direction = direction

    def load(self) -> None:
        pass

    def unload(self) -> None:
        pass

    def run_page(self, page: Path) -> dict:
        from PIL import Image

        with Image.open(page) as image:
            size = list(image.size)
        return normalize_detections(self.records[page_sha256(page)], size, self.direction)


class TextMetadataAdapter:
    stage_name = "vision-text-metadata"
    revision = "text-metadata-2"
    heavy = False

    def __init__(self, detections: dict, ocr: dict) -> None:
        self.detections, self.ocr = detections, ocr

    def load(self) -> None:
        pass

    def unload(self) -> None:
        pass

    def run_page(self, page: Path) -> dict:
        digest = page_sha256(page)
        return text_metadata(self.detections[digest], self.ocr[digest])


def semantic_ocr(record: dict) -> dict:
    return {"revision": record["adapter_revision"], "image_size": record["image_size"],
            "ocr": [{k: v for k, v in item.items() if k != "run_seconds"} for item in record["ocr"]]}


def analyze_chapter(library: Path, series: str, chapter: str, runtime: Path,
                    threads: int = 4, vision_device: str = "cuda",
                    detection_adapter=None, ocr_factory=None) -> tuple[dict, dict]:
    store = ChapterStore(library, series, chapter)
    if runtime.resolve().drive.upper() != "D:" or not runtime.is_dir():
        raise ImportFailure("Dot-source scripts/enter-runtime.ps1; runtime must exist on D:")
    with store.lock():
        started = time.perf_counter()
        manifest = read_json(store.asset("import.json"))
        if manifest is None or manifest.get("import_manifest_version") != 1:
            raise ImportFailure("A valid M1a import.json is required")
        language = manifest["settings"]["source_language"]
        if language != "en":
            raise ImportFailure(f"M1b is verified on English only; source language {language!r} needs a separate OCR evaluation")
        direction = manifest["settings"]["direction"]
        unique = {}
        for entry in manifest["pages"]:
            asset = store.asset(entry["image"])
            if not asset.is_file() or page_sha256(asset) != entry["page_sha256"]:
                raise ImportFailure(f"Imported page changed or missing: {entry['source_name']}")
            unique.setdefault(entry["page_sha256"], asset)
        if not unique:
            raise ImportFailure("The import manifest contains no pages")
        pages = list(unique.values())
        cache = JsonStageCache(store.checked(store.chapter_root / "cache/stages"))
        scheduler = StageScheduler(runtime, cache)
        stage_metrics = []

        def run(adapter, config=None, dependencies=None):
            try:
                output, metrics = scheduler.run_pages(adapter, pages, config, dependencies)
            except StageExecutionError as exc:
                stage_metrics.append(exc.metrics)
                write_json(store.asset("cache/analysis-last-failure.json"), {"stages": stage_metrics, "error": str(exc)})
                raise
            stage_metrics.append(metrics)
            return {entry["page_sha256"]: entry for entry in output}

        def save(records: dict, filename: str) -> None:
            for digest, record in records.items():
                write_json(store.asset(f"cache/pages/{digest}/{filename}"), record)

        detector = detection_adapter or MagiV3Adapter(include_ocr=False)
        detector_config = {"adapter_version": 1, "include_ocr": False,
                           "runtime": {name: version(name) for name in ("torch", "transformers", "Pillow")}}
        raw = run(detector, detector_config)
        save(raw, "detections.json")
        dependencies = {h: {"detections_sha256": object_hash({"revision": r["adapter_revision"], "detections": r["detections"]})}
                        for h, r in raw.items()}
        normalized = run(NormalizeAdapter(raw, direction), {"direction": direction}, dependencies)
        save(normalized, "geometry.json")
        factory = ocr_factory or ChapterCropOcrAdapter
        ocr_inputs = {h: {"detector_revision": r["detector_revision"], "adapter_revision": r["detector_revision"],
                          "page_sha256": h, "image_size": r["image_size"], "detections": r["detections"]}
                      for h, r in normalized.items()}
        ocr_dependencies = {h: {"boxes_sha256": object_hash({"texts": r["detections"]["texts"], "size": r["image_size"],
                                                           "detector_revision": r["detector_revision"]})}
                            for h, r in normalized.items()}
        ocr = run(factory(ocr_inputs, threads=threads, vision_device=vision_device, split_tall=True),
                  chapter_ocr_config(threads, vision_device, language), ocr_dependencies)
        save(ocr, "ocr.json")
        final_dependencies = {h: {"geometry_sha256": object_hash(normalized[h]), "ocr_sha256": object_hash(semantic_ocr(ocr[h]))}
                              for h in unique}
        texts = run(TextMetadataAdapter(normalized, ocr), {}, final_dependencies)
        save(texts, "text-metadata.json")
        # Atomically publish only a complete chapter; raw stages remain resumable.
        analyzed = []
        for entry in manifest["pages"]:
            digest = entry["page_sha256"]
            analyzed.append({"id": entry["id"], "image": entry["image"], "source_name": entry["source_name"],
                             "page_sha256": digest, "size": normalized[digest]["image_size"],
                             "panels": normalized[digest]["panels"], "order": normalized[digest]["order"],
                             "coverage": normalized[digest]["coverage"], "texts": texts[digest]["texts"],
                             "review": normalized[digest]["review"] + texts[digest]["review"],
                             "confidence_status": "uncalibrated"})
        # Check again before publishing: a corrupted source never gains fresh metadata.
        for digest, asset in unique.items():
            if page_sha256(asset) != digest:
                raise ImportFailure(f"Source changed during analysis: {asset.name}")
        result = {"analysis_version": 1, "chapter": f"{series}/{chapter}",
                  "input_sha256": manifest["input_sha256"], "direction": direction, "source_language": language,
                  "pages": analyzed, "confidence_note": "No calibrated detector/OCR probabilities; review reasons and measured golden metrics are separate."}
        write_json(store.asset("cache/detections.json"), {"pages": [{"id": p["id"], **normalized[p["page_sha256"]]} for p in manifest["pages"]]})
        write_json(store.asset("cache/ocr.json"), {"pages": [{"id": p["id"], **texts[p["page_sha256"]]} for p in manifest["pages"]]})
        write_json(store.asset("analysis.json"), result)
        metrics = {"stages": stage_metrics, "pages_total": len(analyzed), "unique_pages": len(unique),
                   "panels_total": sum(len(p["panels"]) for p in analyzed),
                   "text_crops_total": sum(len(p["texts"]) for p in analyzed),
                   "review_flags": sum(len(p["review"]) for p in analyzed),
                   "order_review_pages": sum(p["order"]["needs_review"] for p in analyzed),
                   "elapsed_seconds": round(time.perf_counter() - started, 4),
                   "analysis_sha256": page_sha256(store.asset("analysis.json"))}
        return result, metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--series", required=True)
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--library", type=Path, default=Path(__file__).resolve().parents[1] / "library")
    parser.add_argument("--threads", type=int, choices=(1, 2, 4, 8), default=4)
    parser.add_argument("--vision-device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--run-label", default="current")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", args.run_label):
        parser.error("Use a simple local run label")
    runtime = Path(os.environ.get("MANGAMOTION_RUNTIME", ""))
    report = Path(__file__).resolve().parents[1] / "reports" / f"M1b-{args.run_label}.json"
    try:
        _, metrics = analyze_chapter(args.library, args.series, args.chapter, runtime, args.threads, args.vision_device)
        write_json(report, metrics)
        import json

        print(json.dumps(metrics, indent=2))
        return 0
    except StageExecutionError as exc:
        write_json(report, {"failed_stage": exc.metrics, "error": str(exc)})
        print(str(exc), file=sys.stderr)
        return 2
    except (ImportFailure, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

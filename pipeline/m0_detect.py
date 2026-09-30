"""Run M0a only on five real user-provided pages."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from pipeline.adapters.magi import MagiV3Adapter
from pipeline.cache import JsonStageCache
from pipeline.runtime.scheduler import StageExecutionError, StageScheduler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pages", nargs=5, type=Path, help="five real manga page files in reading order")
    parser.add_argument("--chapter", required=True, help="private library name, e.g. golden-m0")
    args = parser.parse_args()

    runtime = Path(os.environ.get("MANGAMOTION_RUNTIME", ""))
    if not runtime.is_dir() or runtime.drive.upper() != "D:":
        parser.error("Dot-source scripts/enter-runtime.ps1 so all caches and temp files stay on D:")
    if any(part in ("..", "") for part in Path(args.chapter).parts) or Path(args.chapter).is_absolute():
        parser.error("--chapter must be a simple relative library name")

    project = Path(__file__).resolve().parents[1]
    chapter_root = project / "library" / args.chapter
    cache = JsonStageCache(chapter_root / "cache" / "stage")
    scheduler = StageScheduler(runtime, cache)
    try:
        results, metrics = scheduler.run_pages(MagiV3Adapter(), [page.resolve() for page in args.pages], {"crop_pad_px": 8})
    except StageExecutionError as exc:
        report_dir = project / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        with (report_dir / "M0a-metrics.json").open("w", encoding="utf-8") as handle:
            json.dump(exc.metrics, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        raise

    for index, result in enumerate(results, start=1):
        page_dir = chapter_root / "cache" / f"p{index:03d}-{result['page_sha256'][:12]}"
        page_dir.mkdir(parents=True, exist_ok=True)
        for name in ("detections", "ocr"):
            with (page_dir / f"{name}.json").open("w", encoding="utf-8") as handle:
                json.dump(
                    {"page_sha256": result["page_sha256"], "adapter_revision": result["adapter_revision"], name: result[name]},
                    handle,
                    ensure_ascii=False,
                    indent=2,
                )
                handle.write("\n")

    report_dir = project / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    with (report_dir / "M0a-metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

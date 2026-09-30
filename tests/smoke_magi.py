"""Optional synthetic API smoke test. Never use its output for quality claims."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw, ImageFont

from pipeline.adapters.magi import MagiV3Adapter
from pipeline.cache import JsonStageCache
from pipeline.runtime.scheduler import StageExecutionError, StageScheduler


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    runtime = Path(os.environ["MANGAMOTION_RUNTIME"])
    page = runtime / "tmp" / "synthetic-api-smoke.png"
    image = Image.new("RGB", (768, 1024), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((32, 32, 736, 992), outline="black", width=7)
    draw.ellipse((90, 80, 650, 310), outline="black", width=5)
    draw.text((180, 150), "HELLO!", fill="black", font=ImageFont.load_default(size=48))
    image.save(page)

    scheduler = StageScheduler(runtime, JsonStageCache(runtime / "smoke-cache"))
    report = root / "reports" / "M0a-synthetic-smoke.json"
    try:
        results, metrics = scheduler.run_pages(MagiV3Adapter(), [page], {"crop_pad_px": 8, "synthetic_smoke": True})
        metrics["detections_count"] = {name: len(results[0]["detections"].get(name, [])) for name in ("panels", "texts", "characters", "tails")}
        metrics["ocr_crops_count"] = len(results[0]["ocr"])
    except StageExecutionError as exc:
        metrics = exc.metrics
        report.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
        raise
    report.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()

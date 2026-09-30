"""Measure pinned Magi v3 load/unload fit without using a test page."""

from __future__ import annotations

import json
import os
from pathlib import Path

from pipeline.adapters.magi import MagiV3Adapter
from pipeline.cache import JsonStageCache
from pipeline.runtime.scheduler import StageExecutionError, StageScheduler


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    runtime = Path(os.environ.get("MANGAMOTION_RUNTIME", ""))
    if not runtime.is_dir() or runtime.drive.upper() != "D:":
        raise RuntimeError("Dot-source scripts/enter-runtime.ps1 first")
    scheduler = StageScheduler(runtime, JsonStageCache(project / "library" / "golden-m0" / "cache"))
    report = project / "reports" / "M0a-load-probe.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    try:
        metrics = scheduler.probe_load(MagiV3Adapter())
    except StageExecutionError as exc:
        metrics = exc.metrics
        report.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
        raise
    report.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()

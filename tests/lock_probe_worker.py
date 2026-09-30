"""Subprocess helper for verifying the heavy-model lock across processes."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.cache import JsonStageCache
from pipeline.runtime.scheduler import StageScheduler


class TimedAdapter:
    stage_name = "lock-probe"
    revision = "r1"
    heavy = True

    def __init__(self, log: Path) -> None:
        self.log = log

    def load(self) -> None:
        with self.log.open("a", encoding="utf-8") as handle:
            handle.write(f"{os.getpid()} start {time.monotonic()}\n")
        time.sleep(0.35)

    def run_page(self, page: Path) -> dict:
        return {}

    def unload(self) -> None:
        with self.log.open("a", encoding="utf-8") as handle:
            handle.write(f"{os.getpid()} end {time.monotonic()}\n")


if __name__ == "__main__":
    root = Path(sys.argv[1])
    log = Path(sys.argv[2])
    StageScheduler(root, JsonStageCache(root / "cache")).probe_load(TimedAdapter(log))

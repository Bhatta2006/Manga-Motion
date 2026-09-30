from __future__ import annotations

import tempfile
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path

from pipeline.adapters.magi import _crop_box
from pipeline.cache import JsonStageCache, cache_key, page_sha256
from pipeline.runtime.scheduler import StageExecutionError, StageScheduler


class FakeAdapter:
    stage_name = "fake"
    revision = "r1"
    heavy = True

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.loads = 0
        self.unloads = 0

    def load(self) -> None:
        self.loads += 1

    def run_page(self, page: Path) -> dict:
        if self.fail:
            raise RuntimeError("deliberate page failure")
        return {"length": page.stat().st_size}

    def unload(self) -> None:
        self.unloads += 1


class M0aTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / ".runtime" / "tmp")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.page = self.root / "page.bin"
        self.page.write_bytes(b"private page bytes")

    def test_cache_key_tracks_page_config_and_version(self) -> None:
        page_hash = page_sha256(self.page)
        self.assertEqual(page_hash, page_sha256(self.page))
        self.assertNotEqual(cache_key(page_hash, "a", "r1", {}), cache_key(page_hash, "a", "r2", {}))
        self.assertNotEqual(cache_key(page_hash, "a", "r1", {}), cache_key(page_hash, "a", "r1", {"pad": 8}))
        self.page.write_bytes(b"changed private page bytes")
        self.assertNotEqual(page_hash, page_sha256(self.page))

    def test_cache_hit_skips_model_load(self) -> None:
        adapter = FakeAdapter()
        scheduler = StageScheduler(self.root, JsonStageCache(self.root / "cache"))
        results, first = scheduler.run_pages(adapter, [self.page])
        again, second = scheduler.run_pages(adapter, [self.page])
        self.assertEqual(results, again)
        self.assertEqual((adapter.loads, adapter.unloads), (1, 1))
        self.assertEqual((first["cache_hits"], second["cache_hits"]), (0, 1))

    def test_detection_change_invalidates_only_its_page(self) -> None:
        second_page = self.root / "second.bin"
        second_page.write_bytes(b"another real page placeholder")
        pages = [self.page, second_page]
        hashes = [page_sha256(page) for page in pages]
        inputs = {digest: {"detection_sha256": "original"} for digest in hashes}
        scheduler = StageScheduler(self.root, JsonStageCache(self.root / "cache"))
        adapter = FakeAdapter()
        scheduler.run_pages(adapter, pages, page_configs=inputs)
        inputs[hashes[0]] = {"detection_sha256": "corrected"}
        _, metrics = scheduler.run_pages(adapter, pages, page_configs=inputs)
        hits = {item["page_sha256"]: item["cache_hit"] for item in metrics["pages"]}
        self.assertEqual(hits, {hashes[0]: False, hashes[1]: True})

    def test_failure_still_unloads_model_and_releases_lock(self) -> None:
        scheduler = StageScheduler(self.root, JsonStageCache(self.root / "cache"))
        bad = FakeAdapter(fail=True)
        with self.assertRaisesRegex(StageExecutionError, "deliberate") as caught:
            scheduler.run_pages(bad, [self.page])
        self.assertIn("deliberate", caught.exception.metrics["error"])
        self.assertEqual((bad.loads, bad.unloads), (1, 1))
        good = FakeAdapter()
        scheduler.run_pages(good, [self.page])
        self.assertEqual((good.loads, good.unloads), (1, 1))

    def test_load_probe_unloads_and_does_not_claim_page_metrics(self) -> None:
        scheduler = StageScheduler(self.root, JsonStageCache(self.root / "cache"))
        adapter = FakeAdapter()
        metrics = scheduler.probe_load(adapter)
        self.assertEqual((adapter.loads, adapter.unloads), (1, 1))
        self.assertEqual(metrics["kind"], "load_only_probe")
        self.assertNotIn("pages", metrics)

    def test_source_change_during_inference_does_not_poison_cache(self) -> None:
        class ChangingAdapter(FakeAdapter):
            def run_page(self, page: Path) -> dict:
                page.write_bytes(b"changed during inference")
                return {"length": 999}

        adapter = ChangingAdapter()
        scheduler = StageScheduler(self.root, JsonStageCache(self.root / "cache"))
        with self.assertRaisesRegex(StageExecutionError, "Source changed"):
            scheduler.run_pages(adapter, [self.page])
        self.assertEqual(adapter.unloads, 1)
        self.assertFalse(list((self.root / "cache").rglob("*.json")))

    def test_heavy_stages_do_not_overlap(self) -> None:
        state = {"active": 0, "peak": 0}
        guard = threading.Lock()

        class SlowAdapter(FakeAdapter):
            stage_name = "slow"

            def load(self) -> None:
                super().load()
                with guard:
                    state["active"] += 1
                    state["peak"] = max(state["peak"], state["active"])
                time.sleep(0.15)

            def unload(self) -> None:
                with guard:
                    state["active"] -= 1
                super().unload()

        failures = []

        def worker(number: int) -> None:
            try:
                page = self.root / f"page-{number}.bin"
                page.write_bytes(str(number).encode())
                StageScheduler(self.root, JsonStageCache(self.root / f"cache-{number}")).run_pages(SlowAdapter(), [page])
            except Exception as exc:
                failures.append(exc)

        threads = [threading.Thread(target=worker, args=(number,)) for number in (1, 2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertFalse(failures, failures)
        self.assertEqual(state["peak"], 1)

    def test_heavy_stages_do_not_overlap_across_processes(self) -> None:
        log = self.root / "lock-times.txt"
        helper = Path(__file__).with_name("lock_probe_worker.py")
        command = [sys.executable, str(helper), str(self.root), str(log)]
        processes = [subprocess.Popen(command, cwd=Path(__file__).resolve().parents[1]) for _ in range(2)]
        for process in processes:
            self.assertEqual(process.wait(timeout=20), 0)
        intervals: dict[str, dict[str, float]] = {}
        for line in log.read_text(encoding="utf-8").splitlines():
            pid, event, stamp = line.split()
            intervals.setdefault(pid, {})[event] = float(stamp)
        self.assertEqual(len(intervals), 2)
        first, second = sorted(intervals.values(), key=lambda item: item["start"])
        self.assertGreaterEqual(second["start"], first["end"])

    def test_ocr_crop_stays_inside_source_pixels(self) -> None:
        self.assertEqual(_crop_box([3, 4, 20, 30], 100, 100), (0, 0, 28, 38))
        self.assertIsNone(_crop_box([20, 30, 3, 4], 100, 100))
        self.assertIsNone(_crop_box([0, 0, 120, 30], 100, 100))


if __name__ == "__main__":
    unittest.main()

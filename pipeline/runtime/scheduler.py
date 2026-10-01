"""Serialize heavy stages and always release model/CUDA resources."""

from __future__ import annotations

import gc
import ctypes
import os
import subprocess
import sys
import threading
import time
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Any, Iterator

from pipeline.adapters.base import PageAdapter
from pipeline.cache import JsonStageCache, cache_key, page_sha256


class StageExecutionError(RuntimeError):
    def __init__(self, message: str, metrics: dict[str, Any]) -> None:
        super().__init__(message)
        self.metrics = metrics


def _device_memory_mib() -> int | None:
    try:
        completed = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=3,
            check=True,
        )
        return int(completed.stdout.strip().splitlines()[0].strip())
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None


def _process_ram_mib(peak: bool = False) -> int | None:
    if os.name != "nt":
        return None
    from ctypes import wintypes

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    ctypes.windll.kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessMemoryCounters),
        wintypes.DWORD,
    ]
    ctypes.windll.psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    handle = ctypes.windll.kernel32.GetCurrentProcess()
    if not ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
        return None
    return round((counters.PeakWorkingSetSize if peak else counters.WorkingSetSize) / 2**20)


def _power_status() -> dict[str, Any] | None:
    """Read-only Windows power context for comparable laptop benchmarks."""
    if os.name != "nt":
        return None

    class SystemPowerStatus(ctypes.Structure):
        _fields_ = [("ac", ctypes.c_ubyte), ("battery_flag", ctypes.c_ubyte),
                    ("battery_percent", ctypes.c_ubyte), ("saver", ctypes.c_ubyte),
                    ("remaining_seconds", ctypes.c_uint32), ("full_seconds", ctypes.c_uint32)]

    value = SystemPowerStatus()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(value)):
        return None
    return {"ac_line_status": value.ac, "ac_online": None if value.ac == 255 else value.ac == 1,
            "battery_percent": None if value.battery_percent == 255 else value.battery_percent,
            "battery_saver": bool(value.saver)}


class DeviceMemorySampler:
    def __init__(self, interval_seconds: float = 0.2) -> None:
        self.interval_seconds = interval_seconds
        self.baseline_mib: int | None = None
        self.peak_mib: int | None = None
        self.process_ram_baseline_mib: int | None = None
        self.process_ram_peak_mib: int | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self.baseline_mib = _device_memory_mib()
        self.peak_mib = self.baseline_mib
        self.process_ram_baseline_mib = _process_ram_mib()
        self.process_ram_peak_mib = self.process_ram_baseline_mib

        def sample() -> None:
            while not self._stop.wait(self.interval_seconds):
                current = _device_memory_mib()
                if current is not None:
                    self.peak_mib = max(self.peak_mib or current, current)
                ram = _process_ram_mib()
                if ram is not None:
                    self.process_ram_peak_mib = max(self.process_ram_peak_mib or ram, ram)

        self._thread = threading.Thread(target=sample, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=4)
        current = _device_memory_mib()
        if current is not None:
            self.peak_mib = max(self.peak_mib or current, current)
        ram = _process_ram_mib()
        if ram is not None:
            self.process_ram_peak_mib = max(self.process_ram_peak_mib or ram, ram)


@contextmanager
def _single_heavy_model(lock_path: Path, timeout_seconds: float = 300) -> Iterator[None]:
    """Use an OS file lock so separate worker processes cannot co-load models."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    with lock_path.open("a+b") as handle:
        while True:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timed out waiting for heavy-model lock: {lock_path}")
                time.sleep(0.1)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _clear_cuda_cache() -> dict[str, int | None]:
    """Call this only after the adapter has removed its model references."""
    gc.collect()
    torch = sys.modules.get("torch")
    if torch is None or not torch.cuda.is_available():
        return {"torch_peak_allocated_mib": None, "torch_peak_reserved_mib": None}
    torch.cuda.synchronize()
    peaks = {
        "torch_peak_allocated_mib": round(torch.cuda.max_memory_allocated() / 2**20),
        "torch_peak_reserved_mib": round(torch.cuda.max_memory_reserved() / 2**20),
    }
    torch.cuda.empty_cache()
    return peaks


def _reset_cuda_peaks() -> None:
    """Do not carry a previous stage's allocator peak into the next stage."""
    torch = sys.modules.get("torch")
    if torch is not None and torch.cuda.is_available():
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()


class StageScheduler:
    def __init__(self, runtime_root: Path, cache: JsonStageCache) -> None:
        self.runtime_root = runtime_root
        self.cache = cache

    def probe_load(self, adapter: PageAdapter) -> dict[str, Any]:
        """Measure model residency without claiming any real-page inference result."""
        lock = _single_heavy_model(self.runtime_root / "scheduler.lock") if adapter.heavy else nullcontext()
        with lock:
            _reset_cuda_peaks()
            sampler = DeviceMemorySampler()
            power_before = _power_status()
            sampler.start()
            error: str | None = None
            failure: Exception | None = None
            started = time.perf_counter()
            load_seconds = 0.0
            unload_seconds = 0.0
            peaks: dict[str, int | None] = {"torch_peak_allocated_mib": None, "torch_peak_reserved_mib": None}
            try:
                adapter.load()
                load_seconds = time.perf_counter() - started
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                failure = exc
            finally:
                started = time.perf_counter()
                try:
                    adapter.unload()
                except Exception as exc:
                    error = f"{error or ''}; unload {type(exc).__name__}: {exc}".strip("; ")
                    failure = failure or exc
                finally:
                    try:
                        peaks = _clear_cuda_cache()
                    except Exception as exc:
                        error = f"{error or ''}; CUDA cleanup {type(exc).__name__}: {exc}".strip("; ")
                        failure = failure or exc
                    finally:
                        unload_seconds = time.perf_counter() - started
                        sampler.stop()
            metrics = {
                "stage": adapter.stage_name,
                "revision": adapter.revision,
                "kind": "load_only_probe",
                "load_seconds": round(load_seconds, 4),
                "unload_seconds": round(unload_seconds, 4),
                "device_vram_baseline_mib": sampler.baseline_mib,
                "device_vram_peak_mib": sampler.peak_mib,
                "process_ram_baseline_mib": sampler.process_ram_baseline_mib,
                "process_ram_peak_mib": sampler.process_ram_peak_mib,
                "error": error,
                "power_before": power_before,
                "power_after": _power_status(),
                **peaks,
            }
            if failure is not None:
                raise StageExecutionError(error or "probe failed", metrics) from failure
            return metrics

    def run_pages(
        self, adapter: PageAdapter, pages: list[Path], config: dict[str, Any] | None = None,
        page_configs: dict[str, dict[str, Any]] | None = None,
        progress=None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        stage_started = time.perf_counter()
        if not pages:
            raise ValueError("At least one real page is required")
        config = config or {}
        if progress: progress({'stage': adapter.stage_name, 'completed': 0, 'total': len(pages), 'state': 'checking cache'})
        items = []
        for page in pages:
            if not page.is_file():
                raise FileNotFoundError(page)
            page_hash = page_sha256(page)
            key_config = config if page_configs is None else {**config, "page_inputs": page_configs[page_hash]}
            key = cache_key(page_hash, adapter.stage_name, adapter.revision, key_config)
            items.append((page, page_hash, key))

        outputs: list[dict[str, Any] | None] = [None] * len(items)
        page_metrics: list[dict[str, Any]] = []
        lock = _single_heavy_model(self.runtime_root / "scheduler.lock") if adapter.heavy else nullcontext()
        with lock:
            misses = []
            for index, (page, page_hash, key) in enumerate(items):
                cached = self.cache.read(adapter.stage_name, key)
                if cached is None or cached.get("page_sha256") != page_hash or cached.get("adapter_revision") != adapter.revision:
                    misses.append(index)
                else:
                    outputs[index] = cached
                    page_metrics.append({"page": str(page), "page_sha256": page_hash, "cache_hit": True, "run_seconds": 0.0})
                    if progress: progress({'stage': adapter.stage_name, 'completed': len(page_metrics), 'total': len(pages), 'state': 'cached'})

            load_seconds = 0.0
            unload_seconds = 0.0
            sampler = DeviceMemorySampler()
            power_before = _power_status()
            error: str | None = None
            failure: Exception | None = None
            peaks: dict[str, int | None] = {"torch_peak_allocated_mib": None, "torch_peak_reserved_mib": None}
            if misses:
                _reset_cuda_peaks()
                sampler.start()
                started = time.perf_counter()
                try:
                    if progress: progress({'stage': adapter.stage_name, 'completed': len(page_metrics), 'total': len(pages), 'state': 'loading model' if adapter.heavy else 'starting'})
                    adapter.load()
                    load_seconds = time.perf_counter() - started
                    for index in misses:
                        page, page_hash, key = items[index]
                        started = time.perf_counter()
                        result = adapter.run_page(page)
                        run_seconds = time.perf_counter() - started
                        if page_sha256(page) != page_hash:
                            raise ValueError(f"Source changed during stage: {page}")
                        if not isinstance(result, dict):
                            raise TypeError("Adapter must return a JSON object")
                        record = {**result, "page_sha256": page_hash, "adapter_revision": adapter.revision}
                        self.cache.write(adapter.stage_name, key, record)
                        outputs[index] = record
                        if progress: progress({'stage': adapter.stage_name, 'completed': len(page_metrics)+1, 'total': len(pages), 'state': 'processing'})
                        page_metrics.append({"page": str(page), "page_sha256": page_hash, "cache_hit": False, "run_seconds": round(run_seconds, 4)})
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
                    failure = exc
                finally:
                    started = time.perf_counter()
                    try:
                        adapter.unload()
                    except Exception as exc:
                        error = f"{error or ''}; unload {type(exc).__name__}: {exc}".strip("; ")
                        failure = failure or exc
                    finally:
                        try:
                            peaks = _clear_cuda_cache()
                        except Exception as exc:
                            error = f"{error or ''}; CUDA cleanup {type(exc).__name__}: {exc}".strip("; ")
                            failure = failure or exc
                        finally:
                            unload_seconds = time.perf_counter() - started
                            sampler.stop()

            metrics = {
                "stage": adapter.stage_name,
                "revision": adapter.revision,
                "heavy": adapter.heavy,
                "pages_total": len(items),
                "cache_hits": len(items) - len(misses),
                "load_seconds": round(load_seconds, 4),
                "unload_seconds": round(unload_seconds, 4),
                "device_vram_baseline_mib": sampler.baseline_mib,
                "device_vram_peak_mib": sampler.peak_mib,
                "process_ram_baseline_mib": sampler.process_ram_baseline_mib,
                "process_ram_peak_mib": sampler.process_ram_peak_mib,
                "error": error,
                "power_before": power_before,
                "power_after": _power_status(),
                "elapsed_seconds": round(time.perf_counter() - stage_started, 4),
                "pages": page_metrics,
                **peaks,
            }
            if failure is not None:
                raise StageExecutionError(error or "stage failed", metrics) from failure
        return [x for x in outputs if x is not None], metrics

# M1g — Incremental page availability (2026-10-02)

## Built

Scheduler emits completed cached/inferred page records. After each OCR page, CPU normalization and camera compilation publish a validated ordered v1 prefix. Detection/OCR still load once per batch, run and unload through the scheduler; no per-page heavy reload. Durable checksum-protected stream records and immutable asset snapshots preserve earlier reading. Library shows ready/total pages; reader appends validated scenes without restarting the current panel. Failed processing remains visible and retryable.

## Evidence

- `python -m unittest discover -s tests -p 'test_*.py'`: **73 tests, OK**. After the retry-retention refinement, `python -m unittest tests.test_streaming`: **4 tests, OK**. Tests cover out-of-order completion, prefix validation, source corruption, preserved snapshots, cache callbacks, callback failure unloading a heavy fixture and retry without readiness regression.
- `python tests/verify_m1g_golden.py`: actual local import/worker/API on the existing five original pages, all **20/20 analysis stage caches reused**, first observed **1/5 pages while status running** at **2.846019 s**; full request **3.781901 s**. Source hashes unchanged. Final camera compilation **5/5 cache hits**, using the artifacts prepared during streaming.
- `npm run build --prefix reader`: TypeScript/Vite passed.
- `node reader/tests/streaming-smoke.mjs`: Edge **154.0.4258.48**, 390×844; controlled API availability 1 → 3 → 5 pages, current index 1 and switch count 2 retained during append, final 25 panels navigable; failure notice visible, zero errors. This tests append/race behavior, not actual-phone performance.

## Measurements

| Measurement | Actual value |
|---|---:|
| Worker start to first readable prefix | 1.237570 s |
| Worker full completion | 2.318712 s |
| Publisher setup to first page | 0.384010 s |
| Per-page validated publication | 0.153263 / 0.152524 / 0.151834 / 0.151560 / 0.160553 s |
| Mean publication seconds/page | 0.153947 s |
| Final cached camera + validation | 0.249010 s |
| Analysis cache hits | 5 each detection/geometry/OCR/text stage |
| Heavy-model loads | 0 in this warm measurement |

All cached stages omit memory sampling: VRAM/RAM peaks are **unmeasured**, not fabricated zero. New publication is CPU-only; no GPU operations are added. Retain M1d's cold adapter measurements until a matched cold streaming run is warranted. Whole-chapter latency now includes per-prefix contract validation, an explicit ~0.15 s/page cost on this laptop.

## Acceptance and risks

First validated page appears before completion; ordered append, visible failure, durable retry, source integrity and no model overlap pass focused checks. Genuine cold model execution still uses the tested load/run/unload path, but this report does not claim a measured cold streaming speedup. Import itself remains atomic; streaming starts as each OCR page finishes after the detector batch. Actual phone performance and a continuous chapter remain pending inputs. Final semantics/depth/audio evaluation remain later slices.

MotionScript v1 is unchanged; partial availability is local job metadata, with every playable snapshot a complete valid v1 file for its available page prefix. Existing complete playback is retained separately. Proceed to M3a under the all-milestone authorization.

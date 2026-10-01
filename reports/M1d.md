# M1d — Durable chapter jobs and Library/Reader

2026-10-01. Authorized by the user's “okayy continue” after M1c. This report
covers M1d only. Stop before M1e until approval.

## Built

- Local FastAPI Library, import/job/retry and chapter playback endpoints, with
  strict JSON requests and existing D-drive folder/CBZ/ZIP/PDF import wiring.
- SQLite WAL jobs with atomic active-request deduplication, import checkpoint,
  persisted stage metrics, failure/retry status and bounded interruption recovery.
- One child worker per chapter, an OS worker lock before claim/recovery, existing
  heavy-stage serialization/cleanup, and process exit to release framework RAM.
  The API never imports Torch, Transformers or ONNX Runtime.
- Library import form, stage/page counts, saved-chapter links, visible failures
  and retry. Reader selects a chapter and keeps the existing tap camera, original
  page, Reduce motion and audio clock. Legacy SFX still works via new asset URLs.
- Validated immutable playback snapshots with hash-checked, allowlisted assets.
  Old playback survives failed reprocessing; no raw sources/caches/keys are served.

MotionScript remains **version 1 with no new fields**. Original art is never
regenerated. No new model, cloud API, TTS, semantic sound director, music or depth
feature is introduced. Pins/provenance: `pipeline/api/DEPENDENCIES.md` and
`pipeline/requirements-api.lock`, included by the main lock. All installed files,
database, logs, profiles, metadata and caches are on D. Existing Node/Edge binaries
are only read. All four existing model weight hashes were reverified before use.

## Acceptance evidence

| Item | Result / evidence |
| --- | --- |
| One import creates a resumable job | PASS. Actual `POST /api/imports` returned 202 and cold job `65955cf66c2d41a09fc6f21fc435e7d5`. Sixteen concurrent identical requests in the unit test return one ID. Conflicting active requests/case aliases fail. SQLite reopen retains the job. |
| Processed pages appear in Library | PASS. API and browser find `golden-m1d/chapter`, five pages, Ready to read, with 11 explicit review notes. Existing imported/preview chapters are also listed. |
| Full supplied set reads in order | PASS for the supplied **five mixed pages**, not an independently evaluated continuous chapter. Browser visits indexes 0..24 at 1280×900 and 390×844, camera rectangles stay finite, no horizontal overflow/errors, at most three loaded textures. RTL arrows tested; LTR mapping uses a controlled fixture. |
| Failure is visible and retryable | PASS. Actual invalid CBZ submitted through the Library shows Processing failed plus its error; Read saved version remains available. Replacing the test CBZ with the valid five-page fixture and pressing Retry finishes the same job on attempt 2. Final retry job `e3da0d90864f44e79b9dce97467c5617` has 20/20 analysis and 5/5 camera cache hits, 1.190103 s worker time. |
| No overlapping heavy stages | PASS. One OS worker lock precedes recovery/claim, and every heavy adapter retains the tested scheduler lock and unload/CUDA cleanup. A second worker cannot execute/recover while the first lock is held. A separately killed, test-owned process releases its lock and resumes its durable checkpoint on attempt 2. Real cold stages execute detection → normalization → OCR → metadata → camera; no OOM. |

Commands, after `. .\scripts\enter-runtime.ps1`:

```text
python -m unittest discover -s tests -p 'test_*.py'
Ran 62 tests in 27.755s
OK

npm test --prefix reader
tests 9; pass 9; fail 0

npm run build --prefix reader
tsc --noEmit succeeds; Vite 8.3.2 builds 791 modules

python -m pip check
No broken requirements found.

python tests/verify_m1d_golden.py
cold completed 52.178 seconds
warm completed 4.160 seconds
PASS: five pages / 25 panels, cold/warm, immutable pixels and responsive API

node reader/tests/library-smoke.mjs
desktop/mobile visited [0..24]; RTL/LTR controls pass
failedImportRetry: visible failure, preserved previous playback, successful retry
legacySfx: audible Web Audio signal through the new asset base
pageErrors: []

node reader/tests/camera-smoke.mjs
desktop/mobile visited [0..24]; Reduce motion holds source frame
Original page pauses; invalid contract rejected before renderer initialization
pageErrors: []

git diff --check
No whitespace errors.
```

The browser test waits for the expected navigation index, not merely the previous
panel's ready flag. This repaired a test race at audio unlocking. Process probe
import-path setup and inherited-fixture errors were fixed before the final pass.
No failing check is counted as done. Deprecated Starlette/HTTPX TestClient glue
was replaced with documented HTTPX ASGITransport; no extra HTTPX2 package needed.

## Measurements

Windows, RTX 4050 Laptop 6,141 MiB, RAM 15.65 GiB, driver 610.74, existing pinned
Python 3.11.9/Torch 2.4.1+cu121/ORT GPU 1.20.2. Five supplied pages; AC online,
battery 97–98%, saver off. Cold = empty application stage/import caches; the OS
file cache was not reset. Warm = the same source/config/model/camera hashes.

| Cold stage | Mean actual page work | Stage elapsed | Model load | Sampled device peak | Sampled process RAM peak |
| --- | ---: | ---: | ---: | ---: | ---: |
| Import | 0.031894 s | 1.960717 s | none | 0 MiB | 57 MiB (lifetime peak 79) |
| Magi detection | 3.43104 s | 39.5641 s | 22.084 s | 2,145 MiB | 2,583 MiB |
| Geometry/order, CPU | 0.00126 s | 0.2600 s | 0.0068 s | 121 MiB | 1,428 MiB |
| Baberu crop OCR | 1.42930 s | 8.0924 s | 0.6056 s | 393 MiB | 1,851 MiB |
| Text metadata, CPU | 0.00092 s | 0.2787 s | 0.0118 s | 123 MiB | 1,705 MiB |
| Camera, CPU | 0.00124 s | 0.2599 s | 0.0065 s | 123 MiB | 1,705 MiB |

Mean page work excludes load/cleanup and final publication. Stage elapsed includes
hash/cache checks, progress DB updates and telemetry/cleanup. CPU stages allocate
no model GPU tensors; their *device* samples include the CUDA context left in the
same worker after heavy models unload. Device sampling is global and every 0.2 s,
so brief peaks may be missed. RAM samples are worker working sets, not complete
machine consumption. Later CPU rows include loaded framework memory until child
exit, not CPU-adapter model residency.

- Combined actual heavy inference: **4.86034 s/page**, still misses the ≤3 s
  target. Magi loading is the largest cold startup cost. The earlier battery
  run was slower, but this is not a controlled power/thermal comparison.
- Cold worker: **50.991190 s**. Request-to-first-readable/full-chapter: **52.178203
  s**. Warm worker: **1.401806 s**; request-to-readable: **4.159521 s**, a measured
  **12.54×** end-to-end speedup. Worker process startup, coordinator polling and
  measurement polling are included in the request result.
- Warm import: 5/5 hits, 0.659382 s. Analysis stage elapsed
  0.0801/0.0749/0.0748/0.0644 s; camera 0.0770 s. All 25 stage-page entries hit;
  every model load is 0 s. Warm stage memory sampling is skipped and **unmeasured**.
- During processing: 110 probes each; health median/p95/max
  **2.893/23.587/27.267 ms**, Library **95.316/156.129/184.020 ms**. After trimming
  Library job payloads, final idle 30-probe Library **48.825/65.110/66.600 ms**;
  health **2.092/22.298/27.349 ms**. These are localhost single-client observations.
- Final API process working set **64 MiB**, zero live `pipeline.worker` processes,
  sampled NVIDIA usage **0 MiB** after jobs exited. A fresh API fixture uses
  56 MiB and imports no Torch/Transformers/ORT modules.
- Edge **154.0.4258.48**, headless laptop browser: desktop/mobile navigation
  frame median **7.0/6.9 ms**, p95 **7.2/10.0 ms**. Steady panel: 252 samples,
  median **6.9 ms**, p95 **11.0 ms**. This is laptop rendering, **not phone FPS**.
- Visual/audio-clock sample difference ≤**0.3001 ms** in the steady sample. This
  compares two reads of the same clock, **not externally measured A/V offset**.
  Legacy SFX has a nonzero Web Audio analyzer signal and mute works; physical
  output latency/listening was not measured.
- Five input hashes and all served page hashes match; no original page changed.
  Final five-page contract file SHA-256:
  `6d34eaf6ffab5cce4998f33709f57cca56476e072ff17c19be2d3ff23db7e359`.
  Its chapter identifier differs from M1c's; the v1 schema is unchanged.

Raw metrics/screenshots remain ignored: `reports/M1d-{golden,browser,service}.json`
and `reports/M1d-*-private.png`. No private pages/transcripts/model outputs are
included in this tracked report or commits. Screenshots were visually inspected.

## Deviations and remaining risks

1. **Incremental page streaming remains unimplemented.** Existing stages publish
   complete analysis/scripts atomically; the M1d first-page measurement equals
   complete-chapter readiness. This passes this slice's complete-set checklist,
   but does not satisfy/waive PRD §8 streaming. Add an approved follow-up slice
   before final acceptance. No streaming performance claim is made.
2. Import is a local D-drive path form, not a browser multipart upload. This uses
   the existing importer without extra upload copies/dependencies. Mobile network
   access is not enabled by the loopback service; actual-phone setup/trials remain.
3. A five-page mixed sample cannot establish whole-volume quality, arbitrary-page
   memory fit, long-job thermals, independent OCR accuracy, or subjective comfort.
   Actual glyph readability, external A/V sync and source-only depth remain open.
4. Existing M0b sound is a procedural prototype. Newly processed M1d chapters have
   camera-only timelines. Semantic SFX/music and real character depth retain their
   planned gates; voice interfaces remain available for future implementation.
5. Database/cache originals and playback snapshots are retained; disk cleanup is
   future work. Repeated worker crashes stop automatically and require explicit
   Retry. The tested safeguards do not guarantee zero errors on all future inputs.

## Commits / approval

Implementation commit: **3621f55**, `Add durable local chapter jobs and Library
reader`. Evidence/launch documentation is committed separately; its exact hash
is reported in the completion message after remote verification. Stop here. M1e
reading-aware Auto needs the user's next approval.

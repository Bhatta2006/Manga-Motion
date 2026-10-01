# M1c — MotionScript v1 and constrained camera solver

Date: 1 October 2026. The user answered the M1b approval request with “continue,” approving D26's explicit-unavailable confidence exception and authorizing M1c. The request to prevent future errors is addressed through tested failure guards, not a guarantee of error-free future inputs/devices.

**Status:** camera/contract implementation and numerical geometry/comfort checks verified. Actual-phone glyph readability remains unverified; nine small-text-box proxy warnings are explicit. Stop for approval before M1d. No later milestone is implemented.

## Built and verified dependencies

- `pipeline/build_motion.py` compiles M1b analysis into the existing v1 contract; `pipeline/motion/{compiler,solver,rules,timing}.py` supplies the CPU adapter, protected framing, analytic constraints, safe transitions and clock extents.
- Panel order is preserved. Local panel/text IDs are prefixed by page. Original serving images are referenced in place; all five source/served SHA-256 values remain unchanged. No model, API, download, new voice/audio asset or generated pixel is involved.
- Cameras preserve the entire panel and all assigned text. Text crossing a detected panel boundary receives explicit bleed; four real panels need this. At most 4% extra protected-frame margin is added, clipped to the source page. The center of this union stays in the central 60% throughout motion. This does not claim every bubble center is central.
- Slow push/pull/pan recipes remain geometric rules, without guessed story mood. Ambiguous order/fallback panels hold. Candidate 400 ms transition glides exceeding zoom/pan limits become cuts; the supplied set uses 20 cuts and five page-boundary fades. No shake, punch-in or whip is emitted.
- Python and the reader validate the unchanged shared schema using pinned AJV, plus geometry/timing/reference checks. `reader/src/types.ts` now narrows unions to existing v1 enums. The JSON Schema itself and PRD §6 fields/version are unchanged. Public `schema/examples/basic.json` provides a private-art-free fixture.
- Cache payload checksums detect parseable accidental corruption. Stale import/settings/order, changed metadata/source, invalid geometry/timing, missing Node/validator and failed validation prevent publication. The previous complete MotionScript survives failures. The existing chapter lock serializes import/analysis/build; relevant analysis hashes and solver revision/config isolate caches.

Existing versions/README/license and current official APIs were verified; no installs/upgrades were made. AJV 8.20.0, TypeScript 5.9.3, Vite 8.3.2, PixiJS 8.21.0, Playwright Core 1.63.0; Python 3.11.9. All packages/browser profiles/temp/artifacts/cache remain on D:. Existing Node v24.21.0 is read from C:, with no requested C: writes. Dependency documentation/provenance: `pipeline/motion/README.md`.

## Acceptance checklist and evidence

Commands executed from `D:\Motion Manga` after `. .\scripts\enter-runtime.ps1`:

```powershell
& .\.venv\Scripts\python.exe -m pipeline.build_motion --series golden-m1b --chapter chapter --run-label final4-cold
& .\.venv\Scripts\python.exe tests/verify_m1c_golden.py
& .\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
& .\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_camera_solver.py'
npm run build --prefix reader
npm test --prefix reader
node reader/tests/camera-smoke.mjs
& .\.venv\Scripts\python.exe -m pip check
git -c 'safe.directory=D:/Motion Manga' diff --check
```

| Acceptance | Evidence |
|---|---|
| Reader accepts generated `version: 1` files | Python invocation of the reader AJV validator: 5 pages / 25 panels. Nine Node tests pass, including unchanged M0b replay and future voice-event compatibility. TypeScript + Vite build passes. Real browser visits all 25 compiled panels at both 1280×900 and 390×844 without page errors. |
| Numeric camera comfort and text containment | 2,525 real-page samples plus endpoint/analytic derivative proof: zero geometry/comfort violations; 25/25 targets central. Property tests exercise 153 controlled/random geometries × four recipes × 101 poses (61,812 samples), including page edges, narrow frames and overflowing bubbles. All assigned text and the full panel remain protected. |
| Transition safety and Reduce motion | Twenty unsafe candidate glides become cuts; five page boundaries fade. Controlled tests retain a safe short glide and reject a glide measured against a narrow original panel. Real browser Reduce motion holds its rendered source frame during playback. |
| Minimum readable text | **Unverified.** At 390×600 CSS, nine boxes are below the provisional 24 px box-height proxy; at 1280×700 none are. Actual glyph size is not known from boxes and no final readable-font threshold was supplied. This is not a no-crop/comfort pass for phone reading. |
| No VLM/heavy model | CPU adapter only; sampled NVIDIA baseline/peak 0/0 MiB. No AI/API invocation or new dependencies. |
| Deterministic/cache behavior | Final warm run has 5/5 page hits with `CameraAdapter.run_page` patched to fail if called. Exact MotionScript SHA-256 remains `0bc8eecb2f73d72c0c88bd9423d2c05bf2d10d290241448a5fde1c6317adec1f`. Corrupt-cache repair recreates identical output in a publication test. |
| Contract/source fidelity | `git diff` confirms no shared-schema change. Original and served hashes match all five baseline pages. No new v1 field/version is added; review/readability details stay in the sidecar. Original-page access still pauses playback in the browser. |
| Failure behavior | Tests reject nonfinite/degenerate rectangles, unsafe paths, unsupported schema fields/easing, missing initial/overlapping cameras, duplicate IDs, unknown speakers/characters, invalid order and stale/import metadata. Missing Node produces a named validation error. Metadata edited during compilation and forced validator failure retain the previous output hash. An invalid contract produces a visible reader error before renderer initialization. |

Regression results: **47 Python tests in 23.560 s, OK**. After final audit-unit/cap revisions and missing-validator coverage, the focused solver/publication suite passed again: **7 tests in 2.374 s, OK**. **9 reader tests passed**. Build: TypeScript check and Vite succeeded. `pip check`: **No broken requirements found**. `git diff --check`: no errors (line-ending normalization warnings only).

Browser: existing Microsoft Edge **154.0.4258.48**, headless, original page textures. Canvas sizes were 1098×710 in the 1280×900 viewport and 368×611 in the 390×844 viewport. Both visited indices 0–24; zero page errors; no horizontal body overflow. These desktop-emulated viewport checks do **not** establish actual-phone GPU performance, reading comfort or touch behavior. Chapter requests were routed only inside the test to the compiled fixture; the user's normal M0b preview chapter was retained. Final solver audit revisions preserve the exact script bytes tested by the browser.

Private evidence remains ignored: `reports/M1c-{final4-cold,warm,audit,browser}.json`, `reports/M1c-mobile-private.png`, chapter `motionscript.json` and `cache/camera-audit.json`. Manga/text/model artifacts are excluded from Git.

## Measurements

Final adapter revision: **`camera-m1c-4`**. Earlier cache revisions were retained as development evidence; no model inference was repeated. Cold means empty application camera-stage cache for this revision, not cold disk cache. Timers exclude Python startup.

| Stage | Per-page seconds, supplied order | Mean s/page | Five-page stage elapsed | Load / unload | Sampled device peak | Sampled parent RAM peak |
|---|---|---:|---:|---:|---:|---:|
| CPU camera solver, cold | 0.0013, 0.0016, 0.0010, 0.0010, 0.0010 | **0.00118** | 1.7094 s | 0 / 0.0014 s | **0 MiB** | **21 MiB** |
| CPU camera solver, warm | five cache hits, no computation | 0 stage compute | 0.0433 s | 0 / 0 s | unmeasured | unmeasured |

Cold complete build **1.889602 s**, including **0.153413 s** Node/reader validation. Warm complete build **0.219026 s**, including **0.150015 s** validation. Memory telemetry/setup dominates the tiny CPU computation; these are single observations. Node child memory and browser/integrated GPU memory were not measured as parent RAM. Sampling interval 0.2 s can miss brief peaks. Warm peaks are `null`, not measured zero. Windows reported AC online during these observations.

| Camera measurement | Observed maximum / count | Limit |
|---|---:|---:|
| Relative scale against broad frame | 1.0800000000000003 (floating-point representation) | 1.4 |
| Analytic sustained zoom rate | 0.0678584 x/s | 0.6 x/s |
| Analytic sustained pan rate | 0.0388709 original-panel widths/s | 1.2 widths/s |
| Central-target passes | 25/25 | all |
| Within-panel geometry/numeric comfort violations | 0 | 0 |
| Shakes / whips / punch-ins | 0 / 0 / 0 | restrained M1 scope |

Output: **55,879 bytes**, five pages / 25 panels. Provisional per-panel camera extent 2 s + 0.4 s tail gives **60 s** of panel dwell; transitions add **0.8 s** for the four actual page turns before chapter end. Audio duration is **0 s**, with the reader's silent Web Audio clock still driving playback. This is not measured voice sync and not dialogue-aware Auto pacing.

## Limits and next gate

- Keep all M1b reference biases/uncalibrated metadata visible. D26 approval permits unavailable confidence; it does not prove calibration or general scene accuracy.
- Real glyph readability on the target phone remains open. Nine small-box warnings are preserved; widening would not enlarge text. No other bubbles are cropped to force a proxy pass. Actual-phone evaluation and a concrete readable-font policy remain necessary.
- Current rules produce restrained geometric motion; semantic SFX, music, perceived character depth, mobile Flow, reading-aware Auto and full camera grammar remain their planned slices.
- Existing Node/reader dependencies are required for the shared validator. Atomic publication prevents partial JSON but is not a cross-file database transaction or a universal crash/recovery guarantee. Cache checksums address accidental corruption, not hostile tampering. Unknown runtime/device behavior cannot be ruled out by five pages.
- No chapter job/Library API or automatic public preview replacement is implemented here; that integration is M1d. Stop for approval of this slice and its reported limits.

## Commits

- `0872bbd` — Compile safe v1 camera timelines and validate reader contracts: CPU compiler/adapter, bounded geometry/transitions, shared validation, public fixture and Python/Node/browser tests.
- Separate documentation commit — Record M1c evidence and approved confidence policy: measured report, D26/D28 and milestone/PRD status. Manga, transcripts, cached outputs and screenshots stay ignored.

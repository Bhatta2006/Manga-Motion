# M0b — Visual/SFX-first feel prototype

Date: 2026-10-01. Technical checklist completed for the revised scope. **User subsequently watched and said “pretty good for a v0.” Explicit static-preference/comfort judgment and next-milestone approval remain pending; M1 is not started.**

## Scope and result

The user approved M0b, then asked to prioritize sound effects, camera motion, parallax and other motion designs over speech. D20 records that authorization. Kokoro/narration was deferred; no new inference model or cloud API was used.

Built a private five-page, 25-panel PixiJS preview with restrained push-in, pull-out and horizontal drift; 320 ms panel glides; 200 ms page fades; Web Audio as the master clock, including silent panels; tap/auto playback, pause/resume/replay, original-page view, SFX mute and Reduce motion. A viewport mask keeps neighboring panels outside the chosen framing; it does not modify the original texture.

Six sparse SFX events: two visually reviewed wind accents on printed wind cues in page 1, plus four quiet page-turn accents. The owned local library also provides an unused audition chime. These are deterministic procedural preview sounds, **not realistic Foley or automatic scene understanding**. No reference transcription was substituted into OCR or narrated.

Character parallax feasibility was checked on all 30 detected character regions. **0 accepted**: 24 cross a panel/guard boundary, 6 lack uniform source-paper margins. No unsafe effect is enabled. The disabled Parallax control accurately reflects these inputs. The implementation can share/crop an original page texture into a bounded foreground plane on eligible future regions; it never paints background fill. Synthetic unit cases test that geometry only and do not establish manga quality.

## Verification and pins

See [reader dependency verification](../reader/DEPENDENCIES.md). Official docs, registry metadata/licenses and installed API declarations were read. Exact direct versions:

- PixiJS 8.21.0; Vite 8.3.2; TypeScript 5.9.3; Ajv 8.20.0.
- Test-only playwright-core 1.63.0; existing Edge 154.0.4258.48. No browser download.
- Existing pinned Pillow 10.4.0 / NumPy 1.26.4. Custom revisions: `visual-m0b-1`, `procedural-sfx-1`.

All packages, caches, profiles, downloads and task-created artifacts are configured on D. Existing system-installed Node/Edge executables are used. The `.env` is not exposed by the loopback preview server. Original pages/private metrics/screenshots are excluded from Git.

MotionScript remains **version 1**, using the PRD camera rectangles, SFX and line event shapes. Optional source-plane references use existing `director.focus` kind/ref/bbox fields. The schema describes the prototype's supported camera vocabulary; full M3 grammar is not implemented. Confidence is null where upstream APIs supply no calibrated score. Voice engines have a protocol (`tts_base.py`); the reader accepts future `line.audio` events on a separate bus and includes their durations. No voice quality or speech QA claim is made.

## Acceptance evidence

All commands run from `D:\Motion Manga` after `. .\scripts\enter-runtime.ps1`.

| Acceptance item | Evidence | Status |
|---|---|---|
| Five supplied pages / 25 panels playable in detected order | Full browser script visits indices 0–24 once by taps and once by real-duration autoplay; 5 pages, 25 panels; zero page errors | Pass |
| Original art preserved | Original files copied directly; 5/5 source/served SHA-256 and decoded RGB equal. HTTP responses compared byte-for-byte against those files, 5/5 pass | Pass |
| Tap, auto, pause, replay, classic and reduced motion | Browser asserts one tap → next index; pause clock unchanged over 250 ms; resume advances; replay restarts; original view pauses; Reduce motion state tested. Final mask smoke navigates all 25 panels again | Pass |
| Visuals and SFX use audio time | Full real sequence ends normally. Both scheduled SFX and camera sample the same output-clock timeline; nonzero SFX bus RMS observed. Silent buffer maintains output clock on silent panels | Pass for architecture; physical A/V offset unmeasured |
| SFX failures visible / mute | Missing WAV injected only in browser test → `Audio unavailable` visible. Mute sets the SFX bus gain to zero; mute observed including Playwright click/poll overhead in 51 ms | Pass |
| Parallax only for passing regions or explicit no-go | 30 candidates audited; 0 enabled; rejection reasons saved. Coverage/guard/text tests pass. No inpaint or generated art path | Pass as feasibility no-go; no working manga parallax claimed |
| No heavy-model overlap / OOM | No model loaded in this slice. Existing scheduler regression tests pass. Cold stages and browser sample record 0 MiB on NVIDIA device | Pass |
| Subjective better-than-static / comfort | User watched and gave positive initial feedback; explicit static preference/comfort score not supplied | **Pending** |

Commands and representative outputs:

```powershell
& .\.venv\Scripts\python.exe -m pipeline.m0_preview --run-label cold
# pages=5, panels=25; motion cache_hits=0, SFX cache_hits=0
# elapsed_seconds=2.2236; parallax_accepted=0; all five pixels_equal=true

& .\.venv\Scripts\python.exe -m pipeline.m0_preview --run-label warm
# motion cache_hits=5, SFX cache_hits=5; no adapter load on cached page stages
# latest measured elapsed_seconds=1.7974, including telemetry/asset checks

npm run build --prefix reader
# tsc --noEmit passes; vite build passes

npm test --prefix reader
# tests 5; pass 5; fail 0

& .\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
# Ran 18 tests in 4.522s; OK (13 existing + 5 new)

& .\.venv\Scripts\python.exe -m pipeline.preview_server
# MangaMotion preview: http://127.0.0.1:5173

& .\.venv\Scripts\python.exe -m tests.run_browser_benchmark
# full 25-panel autoplay, all 25 tapped panels, missingAudio visibly flagged,
# pageErrors=[], browser_test_exit_code=0, device_vram_peak_mib=0

node reader/tests/frame-smoke.mjs
# final viewport-mask build: all 25 panels navigated; errors=[]
# 478 rendered-frame samples, median=6.9 ms, p95=7.2 ms, max=12 ms
```

JSON artifacts are private under `reports/M0b-{cold,warm,repair,browser,frame,reader-resources,reader-ram}.json`. Screenshots captured and visually inspected at desktop 1280×900 and mobile emulation 390×844. Actual phone hardware has not been tested. Warm contract rebuilds produced the identical SHA-256:

`11b461e79f136c0977bfffd30717d176f628a5b3269f2a78c8a0da6ae79a6315`.

The app browser automation tool failed to initialize with `helper_unknown_error: setup refresh had errors`. Used verified playwright-core with installed Edge and dedicated D profiles instead. No browser installation was performed.

## Measurements

M0a detection/OCR is reused, not rerun: its real numbers remain in `M0a-optimization.md`. These measurements cover only the new preview stages.

### New per-page stages (cold)

| Page | Motion + parallax feasibility (s) | SFX cue routing (s) | Panels |
|---|---:|---:|---:|
| 1 | 0.0532 | 0.0009 | 7 |
| 2 | 0.0121 | 0.0007 | 5 |
| 3 | 0.0368 | 0.0006 | 5 |
| 4 | 0.0064 | 0.0006 | 3 |
| 5 | 0.0123 | 0.0009 | 5 |
| Mean | **0.02416** | **0.00074** | |

Motion stage wall time including telemetry/load/unload: 1.9390 s, process RAM 35→36 MiB, device peak 0 MiB. SFX routing wall time 0.1105 s, process RAM 36 MiB, device peak 0 MiB. Parallax audit is cached inside the motion stage, not a separately loaded model.

The initial batch build took **2.2236 s**, with first page exported after 2.1257 s. This is existing detections/OCR → preview, **not import-to-play streaming latency**. Subsequent observed full asset-instrumented cache runs were 0.3194, 0.7221 and 1.7974 s; the latest is preserved as warm evidence. Wall time varies and includes GPU telemetry queries plus file/PCM validation; do not mistake the 24 ms compute mean for end-to-end latency. An earlier 0.2472 s replay predates separate asset telemetry.

### Procedural audio library (latest measured validation/rebuild)

| Clip | Audio duration (s) | Generation + asset validation (s) |
|---|---:|---:|
| Wind | 0.48 | 0.001180 |
| Page turn | 0.20 | 0.000535 |
| Chime (unused) | 0.30 | 0.000723 |

24 kHz mono PCM16, deterministic seed, no clipped samples, endpoint samples zero, maximum digital peak ≤0.25 before event gain. Unit test corrupts an asset and proves deterministic repair. Page JSON caches cannot leave a missing/corrupt sound silently trusted: library assets are validated/materialized before cache replay. Asset stage process RAM 34→35 MiB; device peak 0 MiB.

### Reader

Full autoplay used Edge's **Intel UHD / ANGLE Direct3D11** renderer. NVIDIA device baseline/peak: 0/0 MiB, sampled every 0.2 s. This is global NVIDIA memory and does not measure integrated GPU shared memory. A single observation of the dedicated Edge process tree during autoplay summed 677.09 MiB working sets across 10 processes; shared pages can be counted more than once. It is **not a RAM peak or private-memory figure**.

- First reader-ready: 200.4 ms, for already generated local assets, excluding click-to-audio device startup.
- Full-sequence run before the final viewport-mask correction: rolling final 3,600 frame samples, median 6.9 ms, p95 7.2 ms, max 9.2 ms (approximately 145 fps).
- Final viewport-mask build: focused desktop/mobile render smoke and all 25 navigations, 478 active frame samples, median 6.9 ms, p95 7.2 ms, max 12 ms. Timing/navigation/audio code was unchanged by that rendering fix; no claim of a second complete final-build autoplay benchmark.
- Output-clock sample difference during a frame: maximum 0.4 ms in the full sequence. This measures software time between camera sampling and resampling, **not physical speaker/display A/V error**. The <40 ms physical A/V target remains unverified.
- Maximum sampled SFX digital RMS: 0.034787. Confirms decoded/mixed signal; perceived sound quality and actual speaker output require listening.
- Two page textures remained loaded at sequence end; eviction checks enforce the small page window. Mobile emulation body width 390 px, no horizontal layout overflow.
- Panel content durations plus tails total 140.168 s; 20 glides and 4 page fades add 7.2 s. Loading/device startup can add wall time. The diagnostics field `glides=24` counts all transitions, including fades.

## Failures fixed / deviations / remaining risks

1. First build caught an Ajv/TypeScript narrowing error; corrected and `tsc` now passes.
2. Fixed audio mute observability by setting the bus's intrinsic gain immediately. Browser checks wait for actual audio readiness rather than assuming a 450 ms startup deadline. Initial test failures were not counted as passes.
3. Visual screenshots exposed neighboring-panel spill outside the camera framing on wide screens. Added a reusable screen-space mask, then navigated all 25 panels and visually reviewed final desktop/mobile captures. Small intentional framing bleed remains; no whole neighboring panel leaks through the unused letterbox area.
4. Original M0b narration and full M3/M4 work are deferred. The user explicitly authorized this narrow visual-first scope change. No cloud director, automatic semantic SFX classification, shake grammar, review UI, ASR or character casting is implemented.
5. These are five independent mixed-series English pages, not a continuous chapter. Detected order is preserved, but no new labeled order/IoU quality claim is made. Camera recipes depend on panel index/aspect and available text length, not story understanding. Letterboxing preserves full selected framing and text; low-resolution art can look soft when enlarged.
6. Source-only rectangle parallax is deliberately conservative and **does not work on these pages**. Segmentation alone cannot restore the occluded background. Tighter verified masks or artist-provided original layers may allow a later source-only approach; never substitute inpainting under the current constraint.
7. Full PWA/offline, streaming import, semantic directing and realistic SFX library are later slices. Phone FPS, physical A/V sync, perceived SFX quality and subjective comfort remain unmeasured.

## Commits and next gate

- `2b6ecaf` — cached source-preserving visual/SFX pipeline, v1 schema, parallax gate and tests.
- `79465db` — audio-clock PixiJS reader, dependency pins, local server, browser verification.
- Final report/checklist committed separately.

Preview: **http://127.0.0.1:5173**. Controls and rebuild instructions: [reader/README.md](../reader/README.md).

User action: watch in **Auto play**, compare with **Original page**, and report feel/comfort. **Do not begin the next milestone until the user replies “approved.”**


## User feedback after viewing (2026-10-01)

“Pretty good for a v0.” User requires stronger character pop-out depth, story-aware effects plus quiet tonal music, mobile navigation without repeated buttons, and Auto timing proportional to dialogue at reading speed. Recorded in PRD v1.2 / `docs/FINAL_PRODUCT_REQUIREMENTS.md` and future milestone acceptance criteria. These are future requirements, not retrospectively passed M0 features. No next milestone or MotionScript change has started.

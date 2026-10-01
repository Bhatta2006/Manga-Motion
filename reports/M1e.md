# M1e — Reading-aware Auto (2026-10-02)

## Built

CPU reading budget and v1 end-frame holds; persisted per-series 160/240/320 wpm UI choices (API supports 80–600); page-hash/config cache invalidation; validated private text-kind labels and unknown/failed OCR fallback. Future decoded voice duration extends dwell. Silent clock carrier uses a fixed one-second loop rather than allocating the whole dwell. Existing v1 schema/types are unchanged.

## Evidence

Commands run after entering `scripts/enter-runtime.ps1`:

- `python -m unittest discover -s tests -p 'test_*.py'`: **69 tests, OK**. Monotonic genuinely empty/10/40/100-word budgets, dense 27.4 s, rate scaling, excluded kinds, flagged unknown/empty OCR, voice lower bound, music exclusion, continuous holds, API bounds/origin/failure and stale-label rejection.
- `python tests/verify_m1e_golden.py`: **5 pages, 25 panels, 243 confirmed words, 0 unknown estimated words**, 2.4–9.9 s at 240 wpm; source hashes unchanged; every generated script passes shared AJV and geometry validation. Uses existing provisional engineer class labels in ignored private `pacing-labels.json`; no automatic classification claim.
- `npm test --prefix reader`: **10 tests passed** including decoded voice/music policy and v1 compatibility.
- `npm run build --prefix reader`: TypeScript and Vite passed.
- `node reader/tests/pacing-smoke.mjs`: installed Edge **154.0.4258.48**, 390×844 viewport; first panel 5.775/4.65/4.0875 s at 160/240/320 wpm, same panel retained after rate changes. Real silent Web Audio advances automatically after its hold, pause/resume retains time; observed hold time 2.1423 s after a 2 s move. Zero page/runtime errors; body width 390 px. This is desktop mobile emulation, not phone performance.

## Measurements

RTX 4050 laptop, 6,141 MiB; CPU-only stage, AC online. Private detailed metrics: ignored `reports/M1e-golden.json` and `M1e-browser.json`.

| Run | Total compile + validation | Camera seconds/page | Peak device VRAM | Process RAM | Cache |
|---|---:|---:|---:|---:|---:|
| First 240 wpm | 0.782731 s | 0.00128 mean | 0 MiB | 43 MiB | 0/5 |
| Warm 240 wpm | 0.209251 s | 0 (reused) | no sampler on cache hits | not sampled | 5/5 |
| 160 wpm | 0.787732 s | 0.00122 mean | 0 MiB | 43 MiB | 0/5 |
| 320 wpm | 0.809310 s | 0.00118 mean | 0 MiB | 44 MiB | 0/5 |
| Restore 240 | 0.172597 s | 0 (reused) | no sampler on cache hits | not sampled | 5/5 |

Default five-page timeline: 120.75 s, previously 60 s. API speed changes do not run detection/OCR. Heavy models loaded: zero.

## Acceptance and limits

Automated timing/filtering/fallback/audio-clock items pass. **User dense-panel reading comfort remains pending.** General text classification remains unknown and reviewable; unknown estimated words can include misrecognized effects. Five mixed pages cannot establish manga reading speed or story continuity. Existing source pixel hashes are preserved. No voice generation or music event is introduced.

## Source/API verification

Existing pinned Python, FastAPI/Pydantic, PixiJS/AJV and browser dependencies reused; no installs/downloads. Verified Web Audio [loop](https://developer.mozilla.org/en-US/docs/Web/API/AudioBufferSourceNode/loop) and [scheduled stop](https://developer.mozilla.org/en-US/docs/Web/API/AudioScheduledSourceNode/stop) docs before use. The future music-policy test does not introduce a music event into v1.

Proceed to M1f under the user's explicit all-milestone authorization. Contract-change approval is retained.

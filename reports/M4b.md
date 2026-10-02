# M4b — Reader-context fixes, overview and bubble guidance

2026-10-02. Technical delivery tested on the five real pages. Actual-phone ergonomics and real-voice listening remain open.

## Built

Hold for 520 ms on a detected text crop to open **Fix bubble** with the selected original-source crop. Text, kind, panel association, speaker and confirmation reuse the canonical `corrections-v1` schema and the M4a transactional API. Both correction surfaces share schema-derived fields and pruning. Save rebuilds the affected page, then reopens the same stable panel ID in paused state. Conflicts retain inputs; Escape/Cancel close without saving. Voice emotion/re-voice is explicitly pending, consistent with the user's visual/audio priority.

Hold outside text to see the complete original page with the current panel outlined. Tap returns to the same paused scene. The existing Original page button and Escape offer accessible alternatives. Flow keeps up/next and down/previous; this deliberately resolves the older PRD swipe-down overview instruction against the later approved Flow behavior. Two-finger tap replays the current scene. Movement cancels a hold, multi-contact/cancel suppresses accidental taps, and consumed holds cancel Flow's pending selection.

Tap-paced side zones mirror RTL/LTR. A center tap during playback reaches its final camera state and pauses; the next center tap advances. Auto center taps continue to pause/resume. Flow's single tap continues its established pause/resume behavior. Existing navigation smoke now uses an explicit next-side tap when traversing playing panels.

Bubble guidance is a separate Pixi outline with no text fill or source texture mutation. It follows the existing line's `bubble` reference, `highlight` flag and **decoded audio duration** on the output clock. Missing audio/geometry hides guidance. Pause freezes its state; Reduce motion uses a constant outline. No new MotionScript fields, schema edits, model, cloud API or dependency.

## Evidence

- `node reader/tests/gestures-smoke.mjs`: passes in Edge 154.0.4258.48, 390×844. Real `text_000` targeted, controlled conflict retained edits, real save persisted and returned to `p0001_panel_000`. Simultaneous CDP touch contacts replayed without advancing. RTL/LTR tap zones, center finish/advance, overview/return and no horizontal overflow passed. Zero page errors; all five original file hashes still match the recorded source hashes. Artificial corrections restored exactly in `finally`.
- Controlled line fixture retains real art/focus boxes and a local test WAV: 2 s decoded duration deliberately differs from .2 s declared duration. Guidance stays active beyond metadata, freezes on pause, disappears after decoded end, and has alpha 1 in Reduce motion. This proves timing integration, **not actual voice quality or hardware A/V synchronization**. Actual golden chapters still have no voice events.
- `node reader/tests/flow-smoke.mjs`: all 25 real panels in both direction modes, no transport clicks, one-scene flick bounds, tap/Auto interruption and original-page return pass.
- `node reader/tests/review-smoke.mjs`: existing standalone editor, durable corrections, revert/pruning, order, conflict and retained failure inputs pass after shared-field extraction.
- `python -m unittest discover -s tests -p test_review.py -v`: 4 tests pass in 11.720 s, including source binding, selective cache invalidation and failed-publication recovery.
- `node --test reader/tests/*.test.mjs`: 20 tests pass; new tests cover decoded line timing, missing/disabled highlights, overlap hit selection and mirrored taps. Generated types check, TypeScript check and production Vite build pass.

## Measurements

Final measured gesture run: hold callback **525.1 ms**, automated correction save/reload **3.266812 s**, complete browser test **13.158377 s**. The controlled line starts at .1 s; polling first observed guidance at **.144185 s** (includes test polling; not an externally measured glow/audio delay). JS heap sample **25,502,128 bytes**, not total browser native RAM. Flow frame samples: RTL median **7 ms**, p95 **7.8 ms**; LTR median **7 ms**, p95 **7.9 ms**. Headless desktop samples do not establish 60 FPS on a phone.

Correction rebuild measurements from the real POST (four unchanged pages have zero cached run seconds):

| Stage | Changed-page seconds | Total stage seconds | Cache hits | Parent RAM peak | Device VRAM baseline/peak |
| --- | ---: | ---: | ---: | ---: | ---: |
| Camera | .0025 | .1569 | 4/5 | 65 MiB | 10/10 MiB |
| SFX | .0098 | .1844 | 4/5 | 64 MiB | 10/10 MiB |
| Music | 1.0517 | 1.2160 | 4/5 | 79 MiB | 10/10 MiB |

Full five-page compilation **2.161804 s**, contract validation **.189250 s**. No model loads. A separate sampler around the complete browser run recorded device baseline/peak **10/10 MiB**; its 19 MiB RAM is the Python wrapper, not browser RAM. GPU metrics do not include integrated-GPU browser allocations. Reader gestures/overlays are live operations rather than a per-page pipeline stage. All artifacts/profiles/temporary files are on D:.

## Acceptance and limits

- [x] Guidance follows the decoded active line in a contract-valid controlled fixture.
- [x] Original page is one hold away; current panel outline and paused return demonstrated.
- [x] Fix sheet selects the intended real bubble, saves durably, and handles conflict without losing edits.
- [x] Original art files remain byte-identical; rendering overlays never write to the source texture.
- [x] CDP touch replay and existing Flow interaction pass at mobile viewport size.
- [ ] Real voice/glow listening, actual-phone touch ergonomics and physical A/V offset remain acceptance work.

Text detector boxes are not bubble silhouettes and may overlap; smallest enclosing region wins with stable-ID tie breaking. A page with unavailable review data still supports overview; correction access remains in Library/Review. Detector geometry drift continues to reject stale corrections. No false claim of true character depth: M4c1/c2 remain next.

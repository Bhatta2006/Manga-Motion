# MangaMotion implementation milestones

Derived from §10 of [`docs/PRD.md`](docs/PRD.md), constrained by the hardware, art-fidelity, contract, and approval rules in the user request. Each lettered slice is intended to be at most about two working days and is **one execution/approval gate**. Do not begin the next slice until the user replies “approved.” The first execution slice is **M0a**, after Step 1 plan approval and the required real pages are available.

## Rules applying to every slice

- Before using a model, repository, or API, inspect current official docs/README/model card and license; record pinned revision, install path on D:, expected memory, measured memory, and API terms if relevant in `reports/<slice>.md`. Do not invent flags or functions. If a claimed fit/license/API capability fails verification, propose a change in `DECISIONS.md` and pause that dependency for approval.
- Use one heavy model at a time through the stage scheduler. Each stage loads, runs, unloads, clears the CUDA cache, and records peak VRAM and elapsed seconds per page. CPU/cloud stages record 0 GPU VRAM and latency; voice/SFX stages also record seconds per line/clip. Cache stage output by source-page SHA-256 plus input/config/model version hashes; record cold and warm cache behavior.
- Preserve original source assets; any served derivative must meet the D05 pixel-identity gate. Keep `/pipeline`, `/reader`, `/schema`, and `/library`. MotionScript v1 (§6) is the only pipeline/reader contract unless the user approves a version bump.
- Write focused tests and use only real user-supplied golden pages for quality claims. End each slice with `reports/<slice>.md`: exact commands/outputs for each acceptance item, metrics with hardware/input context, deviations, risks, and commits. A subjective user acceptance item is pending until the user actually judges it. Stop after the report.
- Pin dependencies in `pipeline/requirements.lock` and `reader/package-lock.json` (or equivalent exact lockfiles) when introduced. Keep downloaded models, `.env`, chapter contents, and private audio out of Git. M0a initializes Git because none exists now.

## Final-product additions and execution priorities

User feedback after M0b adds F01–F04 in `docs/FINAL_PRODUCT_REQUIREMENTS.md` / PRD §14. These are required final outcomes, not implemented features. New slices below keep each implementation gate near two working days. After M1 foundations, prioritize M3/M4 visual, scene-audio and depth work before M2 voice-engine work; preserve IDs for traceability and respect dependencies/approval gates. No MotionScript change is approved by this plan update.

## M0 — Feel test (PRD: approximately 3–4 days)

### M0a — Runtime, scheduler, and five-page Magi feasibility (≤2 days)

- **Goal:** prove the 4050 can run verified page understanding and measure it on five real pages.
- **Deliverables:** D:-only Python 3.11 environment/cache configuration; Git and ignore rules; model/source verification record; adapter contract; single-model stage scheduler/telemetry; Magi detections plus raw OCR JSON for each of five pages.
- **Files/modules:** `.gitignore`, `.env.example`, `pipeline/adapters/base.py`, `pipeline/adapters/magi.py`, `pipeline/runtime/scheduler.py`, `pipeline/runtime/metrics.py`, `pipeline/m0_detect.py`, `pipeline/requirements.lock`, `library/<series>/<chapter>/cache/{detections,ocr}.json`, `reports/M0a.md`.
- **Tests:** adapter contract and scheduler unload/exception tests; JSON parse and page-hash cache test; compare five outputs to manually inspected page labels without claiming a full benchmark.
- **Acceptance checklist:** [x] official Magi docs/license/revision/runtime memory recorded before download; [x] all installs/downloads/temp/cache on D:; [x] five real pages each produce panel/text/OCR JSON with confidence or explicit unsupported field; [x] no two heavy models overlap; [x] cold and warm runs complete without OOM; [x] peak VRAM and seconds/page recorded for every stage invoked.
- **Measurements:** per-page image dimensions/hash, stage load/run/unload time, peak allocated and device VRAM, RAM peak, cache hit rate, errors, and source/weight sizes.
- **Known risks:** Python absent, WSL unusable, low free RAM, Magi v3 API/license/capability unverified, 5,920 MiB actual free VRAM.


M0a checks completed on 2026-10-01; see `reports/M0a.md`. Feasibility passes, but English crop OCR quality and the ≤3 s target do not. These are documented limits, not accepted quality claims.

User-authorized M0a optimization follow-up completed on 2026-10-01: staged Magi detection + specialist Baberu OCR, 2.8480 s/page mean, all 53 crops return text. See `reports/M0a-optimization.md`. Small tuned-set quality results are not M1 acceptance. Stop for M0b approval.

### M0b — Visual/SFX-first five-page feel prototype (≤2 days)

User approved M0b and then explicitly reprioritized camera, SFX and source-only parallax over voice/dialogue. This scope supersedes the original narrator prototype; see D20.

- **Goal:** make a watchable visual motion sequence, keeping audio/voice architecture ready for later work.
- **Deliverables:** bounded push/pull/pan recipes, panel/page transitions, local procedural SFX adapter, source-only parallax safety gate with passing regions only, MotionScript v1 schema/serialization, PixiJS tap/auto reader, original-page toggle and reduce motion.
- **Files/modules:** `pipeline/motion/{fixed.py,serialize.py}`, `pipeline/layers/integrity.py`, `pipeline/adapters/{sfx.py,tts_base.py}`, `pipeline/m0_preview.py`, `pipeline/preview_server.py`, `schema/motionscript-v1.schema.json`, `reader/src/{main.ts,player.ts,camera.ts,parallax.ts}`, `reader/package-lock.json`, `library/preview/m0b/{pages,sfx,motionscript.json,cache}`, `reports/M0b.md`.
- **Tests:** v1 schema and future line event validation; camera interpolation/comfort/text visibility; deterministic PCM/timing; pause/replay/navigation; pixel/hash identity; parallax coverage/guard rejection; real browser playback and frame measurements.
- **Acceptance checklist:** [x] five pages / 25 panels playable in detected order; [x] original art preserved; [x] tap advances one panel, auto/pause/replay/classic work; [x] visuals and SFX follow Web Audio time; [x] SFX failures visible and mute works; [x] parallax enabled only on passing regions or explicit no-go (0/30 eligible); [x] zero new heavy model/OOM; [ ] user judges motion versus static (pending viewing).
- **Measurements:** motion/SFX/parallax seconds per page, VRAM/RAM, cold/warm cache, first preview latency, frame time/FPS, sampled visual-clock offset, source/served pixels, accepted/rejected parallax candidates, subjective comfort/feel.
- **Known risks:** five mixed-series samples are not one chapter. Preview recipes and accents are deterministic heuristics, not semantic directing. Source-only parallax may reject all supplied regions; no generated fill is allowed. No TTS/ASR quality claims.

M0b revised technical scope completed on 2026-10-01; evidence and limits in `reports/M0b.md`. User watched and said “pretty good for a v0,” then specified F01–F04 for the final product. Explicit static-preference/comfort judgment and next-milestone approval remain pending. Stop before M1.

## M1 — Pipeline and reader skeleton (PRD: 1–2 weeks)

### M1a — Import and page cache (≤2 days)

- **Goal:** ingest CBZ/ZIP, PDF, and folders without changing source art.
- **Deliverables:** import validation, per-series settings, lossless page-serving path, SHA-256 page index, safe archive/PDF handling, resumable stage cache.
- **Files/modules:** `pipeline/ingest/{archive.py,pdf.py,pages.py,hashes.py}`, `pipeline/cache.py`, `pipeline/store.py`, `library/<series>/<chapter>/{pages,cache}`, `reports/M1a.md`.
- **Tests:** format fixtures from user pages; path traversal/reject corrupt archive; source-versus-served decoded pixels; cache invalidation when source or settings change.
- **Acceptance checklist:** [ ] all three inputs import; [ ] original assets remain byte-identical; [ ] served raster pixels match decoded originals where applicable; [ ] page hashes stable; [ ] repeated imports reuse cache; [ ] errors name the affected page.
- **Measurements:** import seconds/page, disk bytes/page, RAM and VRAM peak (expected zero GPU), cache hit/miss counts.
- **Known risks:** PDF rendering has no source raster to compare directly; archive filenames/order may be ambiguous; disk space is about 77.6 GiB free at planning.

### M1b — Panels, reading order, and OCR (≤2 days)

- **Goal:** turn pages into ordered, confidence-scored panels and text without manual happy-path work.
- **Deliverables:** Magi adapter output normalization, reading-order logic, bubble-only OCR crop adapter, fallback only for demonstrated failures, per-stage intermediate JSON and confidence flags.
- **Files/modules:** `pipeline/adapters/{ocr.py,panel_fallback.py}`, `pipeline/vision/{panels.py,order.py,crops.py,text.py}`, `library/<series>/<chapter>/cache/{detections,ocr}.json`, `reports/M1b.md`.
- **Tests:** golden panel boxes/order/transcripts; RTL and LTR cases if supplied; ≥70% panel coverage flag; irregular/splash page cases; cache and single-model residency test.
- **Acceptance checklist:** [ ] all supplied pages have an explicit order or review flag; [ ] detected panels and dialogue OCR are scored against labels; [ ] panel precision/recall ≥95%, fully correct page order ≥97%, dialogue CER/WER ≤3% on the applicable golden subset, or slice remains open with failures documented; [ ] OCR reads crops only; [ ] no OOM.
- **Measurements:** precision/recall, order accuracy, CER/WER, flagged count, stage seconds/page, VRAM/RAM peak, cache hits.
- **Known risks:** five to ten pages produce noisy quality estimates; stylized fonts, borderless panels, and Magi output shape may require a verified fallback.

### M1c — MotionScript v1 and constrained camera solver (≤2 days)

- **Goal:** produce a valid end-to-end data contract and comfortable rule-based motion without a VLM.
- **Deliverables:** schema/types, serialized intermediate-to-MotionScript transform, fit/clamp/visibility solver, basic transitions and audio-clock pacing.
- **Files/modules:** `schema/motionscript-v1.schema.json`, `schema/examples/basic.json`, `pipeline/motion/{solver.py,rules.py,timing.py,serialize.py}`, `reader/src/types.ts`, `reports/M1c.md`.
- **Tests:** schema conformance in Python and TypeScript; camera property tests for panel bounds, active bubble visibility, max scale/pan, central focus; deterministic output by identical input hash.
- **Acceptance checklist:** [ ] reader accepts every generated file with `version: 1`; [ ] all tested camera paths satisfy §5.6 comfort/bubble constraints; [ ] no VLM needed; [ ] identical inputs reproduce identical keyframes; [ ] no unapproved contract change.
- **Measurements:** solver seconds/page, constraint violation count, timeline duration versus audio duration, output bytes/page, GPU VRAM (expected zero).
- **Known risks:** PRD sample leaves some fields underspecified; clarify validation without altering the v1 shape or seek a version bump approval.

### M1d — Chapter job and tap-paced Library/Reader (≤2 days)

- **Goal:** import and read a chapter end to end with pipeline status and panel camera moves.
- **Deliverables:** FastAPI chapter/job endpoints, SQLite job table/worker, simple Library page, tap-paced PixiJS reader and local service, integration wiring.
- **Files/modules:** `pipeline/api/{app.py,chapters.py,jobs.py}`, `pipeline/worker.py`, `pipeline/db.py`, `reader/src/{library.ts,reader.ts,api.ts}`, `reports/M1d.md`.
- **Tests:** job resume/failure integration test; full golden chapter import/play smoke test; tap navigation and direction test; local API contract test.
- **Acceptance checklist:** [ ] one import request creates a resumable job; [ ] processed pages appear in Library; [ ] the entire supplied chapter can be read in order with panel-to-panel camera; [ ] failure is visible and retryable; [ ] no stage overlap of heavy models.
- **Measurements:** chapter time, first-page availability, API latency, browser FPS and A/V offset, stage seconds/page and peak VRAM/RAM, cache speedup.
- **Known risks:** user may supply only partial chapters; mobile device/browser behavior may differ from desktop smoke test.

### M1e — Reading-aware Auto pacing (≤2 days)

- **Goal:** meet F04 independently of speech generation.
- **Deliverables:** dialogue/caption-only reading budget, adjustable initial English 240 wpm plus art/beat time, no truncating upper cap, conservative OCR-error fallback, audio-clock silent dwell and end-frame holds. Future dialogue audio can extend dwell; music cannot.
- **Files/modules:** `pipeline/motion/{timing.py,serialize.py}`, `reader/src/{player.ts,pacing-settings.ts}`, `tests/test_timing.py`, `reports/M1e.md`.
- **Tests:** monotonic 0/10/40/100-word timing; exclusion of SFX/notes; sparse/dense real panels; failed versus truly empty OCR; reading-rate scaling; future speech lower bound; long music cannot extend dwell.
- **Acceptance checklist:** [ ] more text gives more time under identical conditions; [ ] dense panels exceed 12 s when required; [ ] only dialogue/captions count; [ ] OCR failures flagged with conservative timing; [ ] audio clock preserved; [ ] user can read real dense panels without routine pauses.
- **Measurements:** words/types per panel, estimated/read-observed dwell, forced pauses/skips, computation seconds/page, VRAM/RAM, cache identity including rate/settings.
- **Known risks:** prose speed is not manga speed; visual complexity/language and OCR quality need calibration.

### M1f — Mobile Flow and Auto handoff (≤2 days)

- **Goal:** meet F03 without routine scene-advance buttons.
- **Deliverables:** one-handed vertical scroll-to-direct scene sequence, settle/snap behavior, one-start Auto, tap pause, manual interruption, accessible optional transport and original-page context. No sensor dependency.
- **Files/modules:** `reader/src/{flow.ts,gestures.ts,player.ts,reader.ts}`, `reports/M1f.md`.
- **Tests:** RTL/LTR sequence during forward/back scroll; scroll/auto races; activate each audio cue once; pause while dragging; browser zoom/touch conflicts; actual-phone chapter trial.
- **Acceptance checklist:** [ ] full supplied chapter navigable with zero required Next/Previous button clicks; [ ] no scene skips/repeated SFX; [ ] auto/manual handoff works; [ ] within-panel audio clock retained; [ ] original page and assistive controls accessible.
- **Measurements:** gestures/transport clicks, accidental skips, handoff latency, actual phone frame times/memory and one-hand comfort.
- **Known risks:** actual phone needed for usability/performance evidence; default page gestures must be reconciled with Flow.

## M2 — Voices (PRD: 1–2 weeks)

### M2a — Speaker attribution and persistent character identities (≤2 days)

- **Goal:** attach dialogue to stable characters with uncertainty visible.
- **Deliverables:** tail/conversation attribution, per-series character store, narrator/unresolved fallback, speaker confidence and intermediate JSON.
- **Files/modules:** `pipeline/voices/{speakers.py,characters.py,store.py}`, `pipeline/adapters/speaker_verifier.py`, `library/<series>/characters.json`, `library/<series>/<chapter>/cache/speakers.json`, `reports/M2a.md`.
- **Tests:** golden speaker labels, multi-speaker/caption cases, chapter-to-chapter identity persistence, low-confidence flag behavior.
- **Acceptance checklist:** [ ] ≥90% labeled lines correct before manual fixes; [ ] every wrong/unresolved line below the chosen threshold is flagged; [ ] identities persist across two supplied chapters if available; [ ] no silent high-confidence guess for unresolved speakers.
- **Measurements:** correct-speaker rate, false-confident errors, flagged rate, seconds/page, VRAM/RAM peak, store size.
- **Known risks:** enough labeled cross-chapter characters may be unavailable; Magi tail and clustering accuracy is unverified.

### M2b — Cast UI, voice cards, and locked references (≤2 days)

- **Goal:** let the user choose and preserve voices without timbre drift by redesigning each line.
- **Deliverables:** Cast screen with sample crops and audition, voice-card metadata, locked voice/reference bank with 3–4 emotions when feasible, narrator/preset mapping.
- **Files/modules:** `pipeline/voices/{cards.py,references.py}`, `reader/src/{cast.ts,voice-audition.ts}`, `library/<series>/voices`, `reports/M2b.md`.
- **Tests:** card persistence, audition/audio routing, per-character stable reference selection, source crop integrity.
- **Acceptance checklist:** [ ] user can audition and lock one voice per principal character; [ ] same character reuses the locked references; [ ] missing emotion clip falls back deterministically; [ ] no unapproved real-person cloning or cloud voice-design call.
- **Measurements:** setup time/character, clip duration/storage, audition latency, VRAM/RAM peak and seconds per generated clip if a verified local designer is used.
- **Known risks:** local 1.7B VoiceDesign may not fit 6 GB; safe references may need user input and quality may be limited.

### M2c — TTS adapters and measured engine bake-off (≤2 days)

- **Goal:** choose the lightest affordable voice route that meets quality needs on the actual laptop.
- **Deliverables:** adapter interface, verified/pinned Kokoro and Qwen3-TTS 0.6B implementations, optional permitted Fish expressive-line adapter, comparable outputs on the same real lines, routing policy.
- **Files/modules:** `pipeline/adapters/{tts_base.py,kokoro.py,qwen_tts.py,fish.py}`, `pipeline/voices/{route.py,cache.py}`, `reports/M2c.md`.
- **Tests:** adapter conformance, cache keys include text/voice/emotion/intensity/engine version, single-model residency, no key in logs/commits, audible blind samples.
- **Acceptance checklist:** [ ] at least local Kokoro and Qwen routes are verified or a documented approval gate explains why one cannot run; [ ] bake-off has matched sample lines and measured memory/time/quality; [ ] Fish used only for expressive lines when key/terms are approved; [ ] fully local fallback works.
- **Measurements:** seconds/line and per-page equivalent, peak VRAM/RAM, load/unload time, output duration/size, API bytes/cost/latency where used, user quality ratings.
- **Known risks:** current APIs, language coverage, licenses, and VRAM may differ from the PRD; Fish terms/pricing may change.

### M2d — Speech QA and chapter voice integration (≤2 days)

- **Goal:** ship consistent lines, catch hallucinations/skips, and keep the reader synchronized.
- **Deliverables:** pinned faster-whisper ASR adapter, speaker-embedding gate, retry/flag loop, loudness/silence processing, Opus encoding, chapter playback wiring.
- **Files/modules:** `pipeline/adapters/{asr.py,embedding.py}`, `pipeline/voices/{qa.py,mix.py,render.py}`, `reader/src/audio.ts`, `reports/M2d.md`.
- **Tests:** known text/audio mismatch and wrong-speaker samples, retry ceiling, loudness/peak check, voiced chapter smoke test, A/V sync check.
- **Acceptance checklist:** [ ] post-retry ASR WER ≤5% on labeled lines or failures stay flagged; [ ] speaker similarity threshold is calibrated on actual cast rather than copied from a source; [ ] voices remain consistent across chapter; [ ] timing follows audio; [ ] every failed line is reviewable.
- **Measurements:** WER, similarity distribution, retry/failure rate, LUFS/true peak, seconds/line and seconds/page, VRAM/RAM peak, A/V offset.
- **Known risks:** small golden set and strong emotion can distort WER/similarity; embedding model may need a cheaper CPU route.

## M3 — Director and camera grammar (PRD: 1–2 weeks)

### M3a — Semantic director pass (≤2 days)

- **Goal:** classify each panel's beat, shot, energy, mood, focus, and line delivery without asking a VLM for pixel coordinates.
- **Deliverables:** schema-constrained director adapter, one-page calls with continuity summary, cached intermediate JSON, local fallback interface.
- **Files/modules:** `pipeline/adapters/{director_base.py,director_cloud.py,director_local.py}`, `pipeline/director/{prompt.py,validate.py,cache.py}`, `library/<series>/<chapter>/cache/director.json`, `reports/M3a.md`.
- **Tests:** schema/ID validation, deterministic cache key, malformed-response retry/flag, no key or full chapter payload in logs, continuity cases.
- **Acceptance checklist:** [ ] every golden page yields valid semantic records tied to existing IDs; [ ] no generated coordinates replace detector boxes; [ ] cloud calls occur only through a configured, permitted provider; [ ] unresolved output is flagged; [ ] one heavy model at a time.
- **Measurements:** requests/page, latency/page, API tokens/cost, cache hits, local fallback seconds/page and VRAM/RAM peak, invalid-output rate.
- **Known risks:** provider pricing/privacy or schema behavior may have changed; local VLM may not fit or may reduce quality.

### M3b — Full move table and comfort controls (≤2 days)

- **Goal:** translate semantic beats into restrained camera grammar and presets.
- **Deliverables:** §5.6 move table/transitions, audio-tied keyframes, Subtle/Normal/Hype and Reduce motion, constraint validator.
- **Files/modules:** `pipeline/motion/{move_table.py,transitions.py,comfort.py}`, `reader/src/{camera.ts,motion-settings.ts}`, `reports/M3b.md`.
- **Tests:** each beat recipe; maximum scale/pan/shakes; bubble visibility/minimum text size; Reduce motion removes shake/whip/punch; generated transition continuity.
- **Acceptance checklist:** [ ] all specified beat classes have bounded rules; [ ] no golden-page comfort violation; [ ] Reduce motion disables prohibited moves; [ ] keyframes remain audio-clock synchronized; [ ] art pixels still match source.
- **Measurements:** constraint violations, scale/pan/shake maxima, A/V offset, dropped frames/FPS, seconds/page, VRAM peak (solver expected zero).
- **Known risks:** geometric constraints do not guarantee comfort; test on the actual reading device and collect subjective scores.

### M3c — Licensed SFX and blind feel evaluation (≤2 days)

- **Goal:** add low-cost context SFX and establish whether direction improves the experience.
- **Deliverables:** documented-license local SFX library/map, voice ducking, chapter preflight, blind static/fixed/director comparison on dialogue/action/comedy material.
- **Files/modules:** `pipeline/audio/{sfx_library.py,sfx_map.py,mix.py}`, `library/sfx/manifest.json`, `reader/src/sfx.ts`, `reports/M3c.md`.
- **Tests:** every asset has a license/source record; category-to-asset mapping; gain/ducking check; blind evaluation form; no SFX on silent-only mode.
- **Acceptance checklist:** [ ] all played assets have personal-use permission; [ ] SFX timing/category is inspectable; [ ] blind “felt directed” and “comfortable” scores average ≥4/5 on supplied test chapters; [ ] zero reported discomfort incidents; [ ] failures remain visible instead of claimed passed.
- **Measurements:** SFX routing accuracy, mix levels, seconds/page and VRAM/RAM peak, full chapter time, blind scores and discomfort count, API spend.
- **Known risks:** three full labeled chapters may not exist yet; SFX overuse can reduce quality, so default should be restrained.

### M3d1 — Music/depth contract proposal (≤1 day; approval gate)

- **Goal:** make necessary scene-spanning audio/layer metadata reviewable before changing v1.
- **Deliverables:** concrete schema/example diff, reader capability/version strategy, migration and v1 replay plan; proposal only, no feature implementation.
- **Files/modules:** `docs/proposals/motionscript-music-depth.md`, `schema/proposals/`, `DECISIONS.md`, `reports/M3d1.md`.
- **Tests:** validate proposed fixtures; show music cannot become panel reading duration; retain existing v1 fixtures and migration round trips.
- **Acceptance checklist:** [ ] exact proposed fields/events/version documented; [ ] old chapter behavior preserved; [ ] user explicitly approves any version bump before implementation.
- **Measurements:** proposed artifact size and migration scope; GPU VRAM zero.
- **Known risks:** current v1 lacks explicit persistent music/layer semantics; product-scope approval is not unseen-schema approval.

### M3d2 — Local mood music cues and library (≤2 days)

- **Goal:** prepare story/mood-aware tonal beds for F02 at low cost.
- **Deliverables:** local library/procedural provider adapter, scene mood/energy cue map, continuity/fallback rules, cached cue/audio preparation. No heavy music model or new cloud service.
- **Files/modules:** `pipeline/audio/{music_library.py,music_cues.py}`, `pipeline/adapters/music.py`, `library/music/manifest.json`, `reports/M3d2.md`.
- **Tests:** labeled scene/mood selection; uncertain-cue fallback; same-scene continuity; deterministic assets/cache; asset provenance and loop-boundary checks.
- **Acceptance checklist:** [ ] inspectable mood/scene cue map on real material; [ ] coherent bed across adjacent panels; [ ] low-confidence choices reviewable; [ ] every asset local and recorded; [ ] one-model residency preserved if the director runs.
- **Measurements:** mood/cue accuracy, uncertain rate, audio build seconds/page/clip, VRAM/RAM and cache/disk cost.
- **Known risks:** mood inference can be wrong; five mixed pages cannot prove story continuity.

### M3d3 — Tonal music mixing and immersive audio evaluation (≤2 days)

- **Goal:** make music audible but unobtrusive and synchronized with scene progression.
- **Deliverables:** separate music/ambience/SFX/voice buses, scene crossfades/looping, ducking, levels/mutes, pause/resume/manual-seek behavior, subjective device trial.
- **Files/modules:** `reader/src/{music.ts,mixer.ts,player.ts}`, `pipeline/audio/mix.py`, `reports/M3d3.md`.
- **Tests:** no resets each panel, no clicks/clipping, bus/mute/duck envelopes, pause/seek/scene-change continuity, music duration excluded from panel dwell, silent mode.
- **Acceptance checklist:** [ ] correct scene/mood bed plays locally; [ ] same-scene transitions continuous; [ ] no clicks/clipping; [ ] music never holds up reading timer; [ ] user judges it noticeable, immersive and quiet enough on actual device; [ ] independent controls work.
- **Measurements:** loudness/true peak, ducking/crossfade envelope, reader frame/CPU/memory cost, mood match and distraction ratings.
- **Known risks:** physical output level varies by device; final gains require listening. Depends on approved M3d1 contract if fields change.

## M4 — Review/Fix UX and source-only 2.5D (PRD: about 2 weeks)

### M4a — Review queue and quick correction (≤2 days)

- **Goal:** make uncertain OCR/order/speaker results visible and fast to repair.
- **Deliverables:** preflight issue list, thumbnails, speaker/text/order corrections, durable labels and selective stage invalidation.
- **Files/modules:** `pipeline/review/{issues.py,corrections.py}`, `pipeline/api/review.py`, `reader/src/{review.ts,fix-sheet.ts}`, `library/<series>/<chapter>/corrections.json`, `reports/M4a.md`.
- **Tests:** correction round-trip, cache invalidation only downstream stages, mislabeled bubble path, timed correction trials.
- **Acceptance checklist:** [ ] every low-confidence item appears in review queue; [ ] wrong speaker can be fixed and re-voiced in <10 seconds in a timed user trial; [ ] corrected labels persist across rerun; [ ] no unrelated page is recomputed.
- **Measurements:** correction seconds/item, unresolved counts before/after, invalidated stage count, reprocess seconds/page, VRAM/RAM peak.
- **Known risks:** user timing is required for the <10 s claim; touch gestures may conflict with reader navigation.

### M4b — Bubble glow and fix gestures (≤2 days)

- **Goal:** guide the eye and expose corrections directly from the reading context.
- **Deliverables:** active-bubble glow overlay, long-press fix sheet, full-page context/overview gestures, accessible visual states.
- **Files/modules:** `reader/src/{bubble-overlay.ts,gestures.ts,overview.ts,fix-sheet.ts}`, `reports/M4b.md`.
- **Tests:** overlay does not modify page bitmap; line/glow timing; gesture interaction and RTL/LTR behavior; reduce-motion accessibility smoke test.
- **Acceptance checklist:** [ ] glow follows the active line; [ ] original page is always one gesture away; [ ] fix sheet targets the intended bubble; [ ] no art pixels change; [ ] touch input remains responsive.
- **Measurements:** gesture latency, A/V/glow offset, FPS, memory use, correction time, pixel integrity.
- **Known risks:** text boxes may overlap; touch behavior on the target device needs direct validation.

### M4c1 — Source-only character masks and occlusion feasibility (≤2 days)

- **Goal:** find real panels that support clean layered character depth for F01.
- **Deliverables:** verified/pinned segmentation adapter, original-pixel masks/layer assets, per-pose coverage/occlusion proof, text-plane protection and visual audits. No inpainting or invented background.
- **Files/modules:** `pipeline/adapters/segmenter.py`, `pipeline/layers/{masks.py,integrity.py}`, `library/<series>/<chapter>/cache/layers.json`, `reports/M4c1.md`.
- **Tests:** source/layer pixel provenance, old-silhouette coverage, exposed-hole/duplicate/seam audit through motion, preserved text, sequential model residency/cache invalidation.
- **Acceptance checklist:** [ ] eligible real panels demonstrated with original-source pixels; [ ] no generated fill; [ ] no visible duplicates/holes/seams in allowed poses; [ ] uncertain/unsafe panels flagged; [ ] measured 6 GB fit. An all-panel no-go leaves F01 unmet and requires a documented next proposal.
- **Measurements:** accepted/rejected panels, mask/pose artifact counts, build seconds/page, VRAM/RAM, coverage and asset size.
- **Known risks:** hidden background is absent from scans; a mask alone cannot recover it. Original artist layers may be needed for some scenes.

### M4c2 — Pop-out depth rendering and user evaluation (≤2 days)

- **Goal:** characters visibly feel lifted from the page while remaining comfortable and faithful.
- **Deliverables:** foreground/background depth planes, bounded differential motion and perspective/scale, camera-linked motion, optional touch interaction, Reduce motion and camera-only fallback; real-panel depth evaluation.
- **Files/modules:** `reader/src/{parallax.ts,depth-controls.ts,camera.ts}`, `pipeline/layers/poses.py`, `reports/M4c2.md`.
- **Tests:** source textures unchanged, old pose fully covered, 1–2% translation cap, preserved ink/text, reduce-motion behavior, actual-phone frame/memory test and layer edge visual review.
- **Acceptance checklist:** [ ] distinct character depth demonstrated on real panels; [ ] user depth and comfort scores ≥4/5; [ ] no exposed/duplicated subject or background fill; [ ] bubble readability maintained; [ ] Reduce motion restores flat reading; [ ] unsafe panels fall back explicitly. Whole-page zoom does not satisfy this slice.
- **Measurements:** depth/comfort ratings, artifact counts, amplitude, FPS/memory cost, seconds/page and VRAM/RAM for any preparation stage.
- **Known risks:** not every scan permits clean parallax; layer metadata may require the approved contract extension. Device tilt is optional with touch fallback.

## M5 — Polish (PRD: about 1 week)

### M5a — Prefetch and offline PWA (≤2 days)

- **Goal:** make reading responsive and available without network after processing.
- **Deliverables:** ±2-page texture prefetch/eviction, next-two-panel audio prefetch, service-worker chapter cache, offline status.
- **Files/modules:** `reader/src/{preload.ts,offline.ts,sw.ts}`, `reader/public/manifest.webmanifest`, `reports/M5a.md`.
- **Tests:** offline reload, page turn with cache miss, bounded texture/audio memory, cache eviction/version update.
- **Acceptance checklist:** [ ] processed chapter reopens offline; [ ] prefetch window stays bounded; [ ] no missing audio on tested navigation; [ ] reader remains responsive on the chosen device.
- **Measurements:** first-page/next-page latency, cache bytes, reader RAM, FPS, A/V offset, stage seconds/page and VRAM if a pipeline stage is invoked.
- **Known risks:** browser storage quotas and texture limits vary by phone.

### M5b — Per-series settings and full-volume run (≤2 days)

- **Goal:** read a full volume without intervening in the pipeline on the happy path.
- **Deliverables:** persistent direction/language/motion/voice/SFX settings, chapter queue/background next-chapter processing, full-volume preflight and failure recovery.
- **Files/modules:** `pipeline/settings.py`, `pipeline/queue.py`, `reader/src/{settings.ts,library.ts}`, `reports/M5b.md`.
- **Tests:** settings survive restart; job resume after interruption; full-volume import/read test using real user-provided volume; no concurrent heavy-model jobs.
- **Acceptance checklist:** [ ] all supplied volume chapters process and appear in order; [ ] user reads the volume without manual pipeline intervention; [ ] failed chapters can resume; [ ] source art remains intact; [ ] one-model residency holds throughout.
- **Measurements:** volume/chapter time, first-page latency, stage VRAM and seconds/page, cache reuse, failure/retry count, user intervention count.
- **Known risks:** full volume may be unavailable; ~77.6 GiB free D: storage at planning may constrain originals plus outputs.

### M5c — MotionScript MP4 export and final acceptance (≤2 days)

- **Goal:** export the same motion/audio timeline to a shareable local MP4 without changing the reader contract.
- **Deliverables:** pinned/verified Remotion + FFmpeg export path, resolution/FPS controls, sync comparison, final 3-chapter A/B and acceptance report.
- **Files/modules:** `reader/export/{render.ts,config.ts}`, `pipeline/export.py`, `reports/M5c.md`.
- **Tests:** reader-versus-export timeline parity, frame sampling and source-art integrity, A/V offset, export resume/failure, three-chapter subjective A/B.
- **Acceptance checklist:** [ ] F01–F04 demonstrated on real chapters and actual mobile hardware (including real character depth, appropriate tonal music, button-free advancement and readable Auto pacing); [ ] MP4 renders from the approved MotionScript contract version; [ ] no `zoompan` micro-jitter path or regenerated art; [ ] A/V error <40 ms in tested output; [ ] 60 FPS reader target measured on device; [ ] on three test chapters the user chooses motion at least 70% of the time with no discomfort incidents, or the unmet criterion is reported honestly.
- **Measurements:** export seconds/page and peak RAM/VRAM, output size, frame/FPS stability, A/V offset, reader FPS, motion-preference percentage, chapter readiness time versus §8 targets.
- **Known risks:** Remotion/FFmpeg may be CPU-heavy; subjective targets need the user's real viewing and enough chapters.

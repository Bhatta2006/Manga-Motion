# MangaMotion implementation milestones

Derived from §10 of [`docs/PRD.md`](docs/PRD.md), constrained by the hardware, art-fidelity, contract, and approval rules in the user request. Each lettered slice is intended to be at most about two working days and is **one execution/approval gate**. Do not begin the next slice until the user replies “approved.” The first execution slice is **M0a**, after Step 1 plan approval and the required real pages are available.

## Rules applying to every slice

- Before using a model, repository, or API, inspect current official docs/README/model card and license; record pinned revision, install path on D:, expected memory, measured memory, and API terms if relevant in `reports/<slice>.md`. Do not invent flags or functions. If a claimed fit/license/API capability fails verification, propose a change in `DECISIONS.md` and pause that dependency for approval.
- Use one heavy model at a time through the stage scheduler. Each stage loads, runs, unloads, clears the CUDA cache, and records peak VRAM and elapsed seconds per page. CPU/cloud stages record 0 GPU VRAM and latency; voice/SFX stages also record seconds per line/clip. Cache stage output by source-page SHA-256 plus input/config/model version hashes; record cold and warm cache behavior.
- Preserve original source assets; any served derivative must meet the D05 pixel-identity gate. Keep `/pipeline`, `/reader`, `/schema`, and `/library`. MotionScript v1 (§6) is the only pipeline/reader contract unless the user approves a version bump.
- Write focused tests and use only real user-supplied golden pages for quality claims. End each slice with `reports/<slice>.md`: exact commands/outputs for each acceptance item, metrics with hardware/input context, deviations, risks, and commits. A subjective user acceptance item is pending until the user actually judges it. Stop after the report.
- Pin dependencies in `pipeline/requirements.lock` and `reader/package-lock.json` (or equivalent exact lockfiles) when introduced. Keep downloaded models, `.env`, chapter contents, and private audio out of Git. M0a initializes Git because none exists now.

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

### M0b — Five-page playable feel prototype (≤2 days)

- **Goal:** make the smallest watchable fixed-motion sequence and obtain the user's feel judgment.
- **Deliverables:** deterministic Ken Burns keyframes per detected panel; Kokoro narrator audio for available text; minimal MotionScript v1 serialization/validation; bare PixiJS page with tap/auto playback from audio time; five-page preview.
- **Files/modules:** `pipeline/adapters/kokoro.py`, `pipeline/motion/fixed.py`, `pipeline/motion/serialize.py`, `schema/motionscript-v1.schema.json`, `reader/src/{main.ts,player.ts,camera.ts}`, `reader/package-lock.json`, `library/<series>/<chapter>/motionscript.json`, `reports/M0b.md`.
- **Tests:** schema validation; camera bounds and active-bubble visibility on golden pages; audio/keyframe timing test; browser playback smoke test; decoded source/served page pixel comparison.
- **Acceptance checklist:** [ ] five pages playable in order with original art intact; [ ] one tap advances one beat; [ ] audio is the visual clock; [ ] narrator lines play or failed lines are visibly flagged; [ ] zero model overlap/OOM; [ ] user watches the sequence and records whether it feels better than static reading (pending user judgment).
- **Measurements:** narration synthesis seconds/line and seconds/page, peak VRAM/RAM, first playable page latency, frame time/FPS, A/V offset, page pixel comparison, subjective score/comments.
- **Known risks:** the PRD says “one chapter” but M0 inputs only five pages; preliminary feel may not generalize. Kokoro voice/language support must be verified before use.

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

### M4c — Parallax feasibility and gated implementation (≤2 days)

- **Goal:** test whether subtle parallax can use only original source pixels without artifacts.
- **Deliverables:** source-only masked layer transform prototype on a few opt-in panels; occlusion/difference audit; enable only passing panels, otherwise document a no-go and use camera-only motion.
- **Files/modules:** `pipeline/layers/{masks.py,integrity.py}`, `reader/src/parallax.ts`, `library/<series>/<chapter>/cache/layers.json`, `reports/M4c.md`.
- **Tests:** no inpaint/AI-redrawn pixel path, 1–2% translation cap, layer boundary/occlusion visual review, source-image hash unchanged.
- **Acceptance checklist:** [ ] source pixels and original files remain unchanged; [ ] no generated fill is visible; [ ] only approved panels receive parallax; [ ] disabling parallax restores exact camera-only rendering; [ ] if feasibility fails, the no-go is recorded and no compromised effect ships.
- **Measurements:** accepted/rejected panel count, displacement, visual artifact count, build seconds/page, VRAM/RAM peak, FPS impact.
- **Known risks:** a cutout can expose duplicate subject pixels beneath it; strict fidelity may make useful parallax impossible.

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
- **Acceptance checklist:** [ ] MP4 renders from existing MotionScript v1; [ ] no `zoompan` micro-jitter path or regenerated art; [ ] A/V error <40 ms in tested output; [ ] 60 FPS reader target measured on device; [ ] on three test chapters the user chooses motion at least 70% of the time with no discomfort incidents, or the unmet criterion is reported honestly.
- **Measurements:** export seconds/page and peak RAM/VRAM, output size, frame/FPS stability, A/V offset, reader FPS, motion-preference percentage, chapter readiness time versus §8 targets.
- **Known risks:** Remotion/FFmpeg may be CPU-heavy; subjective targets need the user's real viewing and enough chapters.

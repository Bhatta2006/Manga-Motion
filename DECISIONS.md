# Decisions and proposed PRD amendments

`docs/PRD.md` is the evolving source of truth; user-authorized product changes are recorded there. The original uploaded `mangamotion-prd(1).md` is preserved unchanged. “Proposed” below means **not approved**: do not implement that departure until the user approves the plan or the specific change. If source docs, licenses, memory measurements, or APIs disagree with the PRD later, add evidence here and stop before substituting a model or changing the contract.

| ID | Status | Choice and reason |
|---|---|---|
| D01 | PRD / hard constraint | Build for personal use on the 6 GB RTX 4050. One heavy model may be resident at a time. A stage scheduler owns load → run → unload → CUDA cache clear, with peak VRAM and elapsed time recorded per stage. Model implementations sit behind adapters. |
| D02 | PRD / hard constraint | Keep page images immutable in the source archive and in the reader. Camera transforms, parallax, shake, glow, and audio are overlays/effects. Cloud calls are limited to the PRD's VLM director and Fish Audio expressive lines; credentials go in an ignored `.env`. |
| D03 | PRD | Offline chapter processing produces MotionScript and audio; the PixiJS reader plays from the audio clock. Prefer open models and local processing whenever quality and the 6 GB limit permit. Fish is a selective quality option, with a fully local route. |
| D04 | Proposed — approval required | Use MotionScript **v1 from the first serialized prototype**, with one JSON Schema in `/schema`; do not create a separate “v0” as M1 §10 says. Section 6 declares v1 the pipeline/reader contract, and the user requires a version bump plus approval for changes. M0/M1 can populate the defined structure with only the events they support. No incompatible schema changes are planned. |
| D05 | Proposed — approval required | Keep original files and use pixel-identical lossless derivatives only when decoding/serving requires it. Disable the §5.1 optional upscale in v1: upscale changes art pixels and conflicts with the hard art-fidelity rule. For CBZ/folder input, compare decoded source and served image pixel hashes in tests; for PDF, keep the PDF untouched and document rasterization. |
| D06 | Proposed — approval required | Do not use the §5.9 LaMa inpaint or depth displacement path for 2.5D. Inpainting creates new art pixels. M4 may add only reversible layer transforms made from source pixels after an image-difference/occlusion feasibility test; if clean parallax cannot meet that rule, M4 records a no-go and keeps camera-only motion. |
| D07 | Proposed — approval required | Treat the PRD's “persistent warm OCR worker” as a **within-stage** optimization. At stage boundaries it must unload before another heavy model loads. “Page N OCR while page N+1 detection” is allowed only when both are proven CPU/lightweight within the VRAM/RAM budget; otherwise process sequentially. This resolves §5.3 against the stronger §8 one-heavy-model rule. |
| D08 | Proposed — approval required | Native Windows is the M0 baseline because WSL commands fail today. Use WSL2 only if a verified dependency requires it and its distro, package caches, downloads, and model files can be kept on D:. No dependency installation or download occurred in planning. |
| D09 | PRD clarification | Treat §8 speed and VRAM numbers as hypotheses, not achieved metrics. M0 records actual stage and end-to-end numbers with hardware state, input dimensions, versions, and cache state. Performance targets are reported separately from acceptance so a slow but correct prototype is visible. |
| D10 | PRD clarification | The golden set begins with 5 to 10 real pages supplied by the user. Corrections become labels; test page hashes and rights/private handling are recorded. Never substitute synthetic examples to claim OCR, speaker, or feel quality. |
| D11 | PRD clarification | The M0 “better than static” outcome is subjective and requires the user's actual viewing judgment. Automated checks can establish a playable five-page sequence, art integrity, and benchmark data; they cannot mark the subjective item passed. M0 stays open until that judgment is given. |
| D12 | PRD clarification | Use cheap deterministic defaults before paid services: Magi only after license/version/VRAM verification; Kumiko and other fallbacks only where failures justify them; local SFX assets first; no SFX generation unless separately verified and it fits. Pin exact resolved versions and checksums in lock/manifest files at each milestone. |
| D13 | PRD clarification | No Fish voice-design API call is planned. The request explicitly names cloud VLM director and Fish expressive lines; the PRD mentions a voice-design endpoint but the narrower user constraint controls. M2 auditions local or user-provided lawful reference voices, and records if quality is insufficient. |
| D14 | Planning choice | A split milestone (M0a, M0b, etc.) is an independent approval gate. Finish its tests, evidence, measurements, report, and small commits, then stop until the user replies “approved.” This keeps each execution slice near two days or less. |
| D15 | Planning choice | Keep `/pipeline`, `/reader`, `/schema`, `/library`. Put source pages and private chapter artifacts under `/library` and exclude them, `.env`, downloaded weights, caches, and reports containing private text/audio from Git where appropriate. Commit only code, schemas, non-private fixture metadata, and reviewable reports. |
| D16 | User clarification, M0a | The user confirmed this is a personal project and asked us not to worry about licensing. The Magi v3 model card explicitly allows personal use while the older GitHub README says academic research only. Record both sources, use the model for this personal project, and keep its files out of distribution. |
| D17 | Proposed for M1, not an M0a gate | The pinned Magi v3 public inference methods return thresholded associations and OCR text, but no calibrated detection/OCR confidence values. M0a records `null` confidence and an explicit reason. Before M1 confidence thresholds/review scoring, choose a measured calibration method or a verified specialist fallback; do not fabricate scores. |

## Verification gate for every model, repo, or API

Immediately before first use, read current official README/docs/model card and license; record immutable version/revision, source URL, download/install destination on D:, expected and measured VRAM, runtime compatibility, and any API cost/data terms. Do not infer callable names or flags from the PRD. A failed license, fit, or art-fidelity check becomes a proposed change here and pauses that dependency until approved.

## D18 — Real M0a feasibility and English OCR finding (2026-10-01)

Measured: five-page Magi detection/crop OCR fits the 4050 at 2,145 MiB peak and 4.3879 s/page mean after load, with 5/5 cache hits on replay. Only 14/53 crops return text, including errors. Empty results are explicitly flagged; nonempty results remain unverified. A raw-output diagnostic confirms empty generation rather than an adapter decoding loss.

Decision: retain Magi for detection feasibility and retain the PRD's planned specialist English OCR evaluation in M1. This is a measured limitation, not approval to introduce another model in M0a or change MotionScript. The PRD's ≤3 s/page target is unmet by this baseline. M0b must expose/flag failed lines and must not treat this OCR as reliable narration text. No new dependency or API was introduced.

## D19 — Approved English OCR optimization follow-up (2026-10-01)

User authorization: “hardware upgrade isnt possible, so go with optimal implementation strategies.” This supersedes D18's deferral of specialist OCR evaluation for this narrow remediation. Evaluated the PRD's Baberu locally on the same five pages and selected pinned ONNX FP16 vision on CUDA + INT8 decoder on CPU with four threads. Keep the two heavy model stages sequential: Magi detection → unload/clear → Baberu OCR → unload/clear. No MotionScript or art contract change.

Final observed inference mean is 2.8480 s/page versus baseline 4.3879 (35.1% reduction). Peak device VRAM: detection 2,145 MiB, following OCR 395 MiB. All 53 crops return text. On the private exploratory reference set, dialogue lexical WER is 0/195 and dialogue+caption WER 6/244 (2.46%), with punctuation excluded. These tuned five pages do not establish general accuracy. Caption/SFX errors and first-page >3 s latency remain. Full five-page processing including loads is 26.7928 s.

English tall-crop splitting at blank gaps recovers the demonstrated long-line truncation; it is not a Japanese vertical-text default. CPU vision remains selectable. Unsupported confidence is null. Canonical source/text-box/model/runtime/config cache identity makes all ten page-stage outputs reusable without reloading models. See reports/M0a-optimization.md for evidence and pins. M0b remains behind its approval gate.

## D20 — User-authorized visual-first M0b (2026-10-01)

After approving M0b, the user explicitly prioritized sound effects, camera motion, parallax and other motion designs, with less focus on voices/dialogue. This replaces M0b's Kokoro requirement: no TTS model, downloads or speech QA in this slice. Keep the v1 `line` event and voice adapter protocol available for later integration. Use a Web Audio clock, including silent panels, so adding speech does not change camera timing architecture.

Move a narrow part of M3/M4 feasibility into this approved slice: bounded push/pull/pan recipes, transitions, optional small SFX accents, source-only parallax eligibility. No VLM director, semantic accuracy claim, review UI, full move table or character casting. Own deterministic procedural SFX are a free local starter library behind an adapter; they are preview accents rather than realistic Foley or automatic semantic understanding.

Parallax may only copy original source pixels. A rectangular foreground region can move only if a uniform original-paper guard surrounds it, the transformed rectangle always covers its old position, it stays inside its panel, and it cannot cover text. This conservative gate avoids duplicate subjects and exposed holes without inpainting. Reject unsafe candidates and use camera-only motion; never pretend a flat camera pan is character parallax. References to eligible regions use the PRD's existing `director.focus` kind/ref/bbox fields, without new root fields or a v1 change. Record actual eligibility on the supplied pages.

## D21 — Required perceived depth (user feedback, 2026-10-01)

The final product must make character cutouts feel lifted from the page. Source-only layered depth is a required acceptance goal, not satisfied by the current uniform camera zoom or all-candidate rejection. Keep per-panel safety fallback, but F01 remains unmet until real panels demonstrate artifact-free depth and user comfort. Split M4c into mask/occlusion feasibility and rendering/evaluation. No permission for inpainting or regenerated art was given.

## D22 — Scene-aware SFX and tonal music now in scope

The user explicitly requested quiet, noticeable tonal background music that follows story mood, plus scene-based effects. This supersedes the original PRD's blanket music exclusion. Prefer local tonal stems and owned procedural audio, with adapters, scene continuity, crossfades, independent buses/mutes and ducking. No cloud music API or heavy music generation engine is authorized. Music must not determine panel reading duration. See F02 and new M3d slices.

## D23 — Mobile Flow experience

The user requires mobile scene navigation without repeated button clicks. Resolve the target-device preference to mobile first. Plan scroll-to-direct Flow mode plus one-start Auto, accessible optional controls and user interruption of Auto. Touch scrolling selects/settles a scene; within-panel visuals/audio retain the audio clock. Test an actual phone and prevent repeated SFX triggers, skipped panels and browser gesture conflicts. No sensor permission is required for core navigation. See F03/M1f.

## D24 — Dialogue-aware Auto dwell

The final timer uses dialogue/caption reading length, an adjustable initial English 240 wpm baseline plus art/beat pauses, and later the longer of reading budget or voice duration. The baseline is informed by prose research and needs manga calibration; it is not a proven manga average. Exclude non-reading text; handle OCR failures conservatively. Remove the prototype's arbitrary 12 s cap in the dedicated pacing slice. Preserve the audio master via silent time; music does not extend the dwell. See F04/M1e.

These product requirements are authorized by the user's feedback. The documentation is PRD v1.2; **MotionScript is still v1**. Any necessary music/layer contract extension needs a concrete proposal, version bump and explicit approval before implementation. No next implementation milestone was authorized by this feedback alone.

## D25 — Approved M1a import implementation (2026-10-01)

The subsequent “ok continue” authorizes the next planned slice, M1a. Import is CPU-only and takes no heavy-model residency; serialize local imports with a separate library OS lock. Copy original images and archive/PDF containers without changing bytes. Serve original image files where possible; TIFF uses a verified pixel-identical PNG under approved D05. PDFium 153.0.7999.0 through pinned pypdfium2 5.13.0 renders one page at a time, with a recorded default 144 dpi and configurable 72..300 range. This is PDF rasterization, not AI-generated art. Original containers remain immutable.

Cache identity includes source SHA-256, adapter revision, page index for PDF, and per-series settings. PNG output hashes become downstream page hashes. TIFF/PNG decoded RGB hashes must agree; image sources remain byte-identical. Corrupt/missing serving assets and malformed JSON cache records are repaired. Publish the ordered import manifest atomically only after every page validates; keep completed page caches after a failure to support retries. Old hash-addressed assets are retained rather than deleted automatically.

Use natural filename ordering with an explicit inferred-order review note, or document order for PDF. Start with RTL/English settings from the supplied sample; users can override per series. Reject animated/multipage images, unsupported decoder formats, non-identity EXIF orientation, unsafe archive names/links/duplicates/encryption and oversized inputs with a named error. Size limits mitigate accidental resource exhaustion but are not a sandbox for hostile PDF complexity.

This import manifest is independent of MotionScript. No schema change, voice model, director API, reader flow, music or depth feature is introduced in M1a. Full tests pass and measurements replace ingest assumptions in PRD §8; stop for M1b approval.

## D26 — Approved M1b confidence exception

Source verification confirms that the pinned Magi and Baberu public methods return thresholded geometry/class hints and text, **not calibrated per-panel/per-text confidence probabilities**. This is the anticipated D17 limitation. M1b cannot honestly satisfy PRD §2's numeric confidence goal from those public outputs or from five tuned sample pages. Panel/OCR accuracy measurements against labels are not per-item confidence calibration.

Approved exception: retain the existing `null` confidence representation, attach explicit detector/OCR confidence-unavailable warnings plus concrete geometry/text/order review reasons, and defer numeric calibration until a separate, independently labeled validation set exists. Do not substitute token probabilities, IoU, binary essential flags or a hand-written heuristic score as a calibrated confidence. Keep uncertain results reviewable. The implementation uses the existing adapter contract; numerical calibration remains deferred under the revised PRD principle.

Initially proposed for approval at the end of M1b. The user answered that approval request with “continue” and requested stronger error prevention, authorizing this exception and M1c. PRD §2 now permits explicit unavailable confidence with review flags when verified adapters do not return calibrated scores. Numerical calibration itself remains deferred and unachieved. MotionScript v1 remains unchanged; no cloud fallback/model substitution or voice work is introduced.

## D27 — M1b ordering and text metadata implementation

Use Magi detections behind the existing adapter; normalize only geometry/metadata. Its public method does not perform the repository's transcript/panel sort. Apply a bounded RTL/LTR page-cut solver with explicit ambiguity flags instead of the potentially unbounded graph-cycle/erosion helper. Verify against actual source frame/order annotations and disclose their provisional/non-blind status. Keep a flagged full-page geometry fallback for no detections; no new detector is needed unless measured failures justify one.

Use exact rectangle union for the PRD's 70% coverage check. Preserve original detector indices, raw associations, OCR crops and model essential flags. A binary essential flag cannot provide a final dialogue/caption/SFX/sign class; retain `unknown` kinds rather than guessing. OCR reads only detected padded text crops, rejecting whole-page crops before the engine. Direction changes invalidate only geometry/metadata. A settings change does not trigger new model inference when relevant model inputs are identical.

Measured cold inference is slower than the prior M0 observation with the same model/runtime settings. Windows reports AC offline after the run; its contribution is not isolated. Record actual timings, retain earlier measurements and add read-only power telemetry for future matched comparisons. No power settings or model versions are changed.

## D28 — M1c bounded camera and validation decisions

The user's subsequent “continue” authorizes M1c only, including preventing concrete failure modes; it cannot guarantee zero future errors. Compile M1b imports to the existing v1 schema without adding fields. Prefix local panel/text IDs by page, retain review details outside the contract, and leave unavailable confidence null under D26. Use CPU-only adapters, original serving assets and analysis-hash stage caches.

Protect the entire panel plus every assigned text box, with explicit text-overflow bleed and at most 4% additional width/height margin clipped to the source. The target is that protected union's center; it remains in the central 60%, while each text box remains visible. Restrained push/pull/pan rules do not claim scene semantics. Use analytic sustained speed/scale bounds and cuts where a 400 ms transition glide would exceed them. Hold ambiguous/fallback panels; emit no shake, whip or punch-in. Reduce motion holds the first frame.

M1c's 2 s camera extent plus existing 0.4 s tail is provisional for tap-paced playback; it does not replace M1e's reading-aware Auto requirements. Text-box height audits at named CSS viewports flag potential small text below a provisional 24 px. This is not measured glyph size or final phone readability; nine boxes are flagged at 390×600. No assertion that widening enlarges glyphs is made. Actual-device readability remains a later acceptance gate.

Use the reader's pinned AJV and unchanged shared schema from Python through a Node stdin validator, plus geometry/timing/reference checks before publication and before reader initialization. Avoid divergent schema validators. Missing Node/dependencies, stale input metadata, nonfinite/degenerate geometry, invalid paths, overlapping/discontinuous cameras and unknown speakers fail explicitly. Camera payload checksums repair accidental parseable cache damage. Recheck metadata/source hashes before atomic publication so failures keep the last complete script. These are bounded safeguards against tested failures, not a promise covering every future input/runtime.

## D29 — M1d durable local jobs and isolated worker

The user's “okayy continue” authorizes M1d only. Use minimal, pinned FastAPI/
Uvicorn packages and the built-in SQLite library; no Redis, cloud service or
resident model server. A coordinator supervises one child process per chapter.
The child takes an OS worker lock before recovering/claiming a job; heavy stages
retain their existing separate scheduler lock and load/run/unload/CUDA cleanup.
Process exit also releases framework memory. A live orphan worker's lock prevents
another API instance from treating it as interrupted. Resume once automatically
after interruption; a repeated crash needs explicit Retry to avoid a restart loop.

SQLite checkpoints retain the completed import hash and stage metrics; retries
verify the manifest and reuse page/config/model-hash caches. Requests are JSON
local D-drive paths for the existing folder/CBZ/ZIP/PDF importer, deduplicated
while active. Windows capitalization aliases cannot enqueue conflicting jobs.
Strict request fields, same-origin browser writes, loopback bind and explicit
asset allowlists protect the local import surface. No chapter source/cache/key
file is exposed through arbitrary paths.

Publish immutable, checksum-protected playback snapshots outside MotionScript
v1. The reader uses snapshot-specific image/audio URLs; opening/rerunning another
chapter does not mutate the contract or invalidate an already opened script.
Asset responses serve exactly the bytes whose SHA-256 was checked. Keep previous
valid playback available on failed reprocessing. Library jobs expose useful
status/progress/error fields rather than every private stage payload.

Current stages publish complete chapters atomically, as M1b/M1c already do. The
five-page M1d acceptance checklist passes, but **PRD incremental page streaming
is not implemented or waived**. First-page readiness is measured as complete
chapter readiness; streaming needs an approved follow-up slice before final
acceptance. Do not call the current reader a streaming reader. No new voice,
semantic SFX, tonal music, depth or reading-aware Auto feature is claimed.

## D30 — All-milestone continuation and v1 reading holds (2026-10-02)

The user explicitly answered: “Continue through all milestones; keep contract-change approval.” This supersedes per-slice stop requirements. Continue implementation with individual evidence/reports/commits; do not claim subjective or actual-device gates without user measurements. A new MotionScript version still needs approval before implementation.

Compile reading time as existing v1 end-frame camera holds. English defaults to adjustable 240 wpm, plus 2 s art time and 0.4 s tail, without an upper cap. Known dialogue/caption labels contribute confirmed words; known SFX/sign/nonverbal/watermark/translator-note labels are excluded. Unknown essential text receives a separate estimated-word budget and uncertainty margin, not an asserted class. Empty failed crops receive a conservative minimum. Private page-hash/text-ID labels from the existing provisional golden reference demonstrate filtering on the five pages; general classification remains M3a work.

Changing reading speed recompiles CPU-only camera timing and preserves immutable playback snapshots. Per-series settings and page-hash/config caches include the rate and label inputs. The reader does not depend on a pacing sidecar to interpret timing: v1 contains complete holds. Decoded future voice duration extends the audio-clock lower bound; music is excluded. A one-second looping silent buffer keeps long dwell memory bounded, using verified Web Audio loop/stop APIs. No new model, dependency, cloud call or schema change.

## D31 — Native scene Flow

Mobile defaults to a native vertical snap rail over the existing scene renderer. Settling selects at most one adjacent panel; a same-panel settle does not replay its cues. Touch/scroll interruption pauses Auto and hands control to Flow. A tap pauses/resumes, preserving scene time. The audio master remains within-panel and original art/transport remain accessible. Desktop scroll tests establish bounded navigation, not actual-phone comfort, touch conflicts or sound quality. These user gates remain pending while independent implementation continues.

## D32 — Ordered validated streaming prefixes

Publish after completed OCR pages while retaining amortized batch model loads. CPU text normalization/camera compilation and Node validation do not load another model. Stream only a contiguous page prefix, recheck source hashes and seal the readiness record. Cache camera outputs using the same page/analysis/rate/version identity as final compilation. Retry preserves a previously longer identical prefix until catches up. Old immutable snapshots and complete chapter files survive failures.

Availability/status belong to the local job API, not MotionScript timing semantics; each prefix is independently complete v1 playback. Append only if previous pages match exactly, otherwise tell the reader to reopen the changed chapter. Keep playing the same panel with the same clock and asset snapshot. Import remains atomic and detection remains batched; the first cold page cannot precede those stages. Measured warm first-page readiness improves; cold/device performance remains unmeasured.

## D33 — Measured local director and explicit semantic uncertainty

Use the PRD's local Qwen option as the default for the user's open-source/low-cost priority. Verified Qwen3-VL 4B Q4_K_M through pinned llama.cpp b11323 fits alone at a sampled 4,505 MiB on the five pages. Exact revisions/checksums are in the runtime specification. A tested 2B Q8 alternative had poor classification/scene diversity; the 4B profile improves the provisional text match to 42/52 while retaining review flags on every output. No semantic confidence is invented and no cloud calls occur. See reports/M3a.md for source verification and speed/RAM limits.

Keep one page call with interleaved detector-ID crop labels and schema-constrained output; retry malformed output once, then flag quiet/unknown fallback. Carry generated summary/series notes in cache identity, but instruct that current images/OCR override prior context. Human labels override model labels. Streaming waits for each directed page so published scenes are stable; this supersedes D32's OCR publication point. Keep MotionScript v1 unchanged. Windows sharing failures receive bounded atomic-publication retries; assigned VLM children use documented kill-on-owner-close ownership.

## D34 — Text-protected semantic framing and v1 motion limits

Focus may crop panel surroundings through camera framing, while source pixels stay unchanged. Protect the selected detector-derived region plus every assigned text box, with a maximum 1.4 scale and existing comfort bounds. Hold when no safe focused pose exists; never shrink a frame to hide dialogue. Camera segments, presets and optional semantic effect overlays share the audio clock. Shake is capped, text-edge gated and disabled by Reduce motion. See reports/M3b.md.

Existing v1 enum limits require outQuad shock and piecewise comedy approximations. Exact exponential/spring easing, semantic chase direction and blur remain tracked refinements, not falsely completed PRD details. Future real voice starts are required for demonstrated speaker following. A concrete v2 proposal will cover any necessary contract changes; current playback remains v1.

## D35 — Owned local scene-sound catalog and restrained routing

Use tiny deterministic CPU procedural assets behind a provider instead of adding an audio model. Record exact provenance/hashes and repair assets independently of cached page records. Suppress cues that conflict with human/final text kinds; inferred scene accents remain reviewable, limited to one repeated stylistic category/page and at most three cues/page. No page-turn default. This realizes zero-cost local routing while actual sound appropriateness remains a listening gate; see reports/M3c.md.

Keep user mute separate from a future voice-driven duck envelope. Publish identical SFX in streamed/final v1 snapshots and preserve reading dwell. Prepare anonymous, time/audio-matched static/fixed/directed variants for actual evaluation; never substitute preparation or Web Audio RMS for blind user scores.

## D36 — Approved v2 beds, source layers and easing

Following the requested ECC contract-first workflow, prepare the exact reviewable proposal in `docs/proposals/motionscript-music-depth.md` and `schema/proposals/motionscript-v2.schema.json`. Add scene-spanning local music/ambience, masked original-page character planes with bounded poses/hash-bound conservative safety metadata, and outExpo/outBack easing. Keep bed duration out of panel dwell; preserve v1 through explicit version dispatch and lossless flat promotion only. Old chapters/snapshots remain v1. Unknown fields/versions and unsafe paths fail visibly.

On 2026-10-02 the user explicitly answered “Approve the proposed MotionScript v2,” resolving the approval gate after automatic review rejected the ambiguous “continue.” Promote the exact schema; derive types and validate both versions. Structural fixtures do not establish real layer coverage or perceived depth; no hidden-background invention is allowed. See `reports/M3d1.md` for proposal evidence and `reports/M3d2.md` for approved local music preparation. Music playback and character rendering still require their implementation slices.

## D37 — Local scene mixer and immutable v2 publication

Publish causal music metadata identically in stream/final scripts and validate real PCM hashes/extents before sealing snapshots. Scene IDs preserve adjacent source phase; seeks use the shared reader transition timeline. Run independent user buses beneath source fades and future voice duck envelopes. Shorten existing outgoing fades on repeated navigation to bound overlap. Interruptible piecewise equal-power ramps replace native value curves after measured seek discontinuity; tests retain native audio rendering evidence. Keep quiet initial gains and expose controls pending physical-device listening. CPU owned music adds no model/API cost; exact voices and export remain separate slices. See `reports/M3d3.md`.

## D38 — Human overlays after model caches

Store strict internal correction data separately from raw OCR/detection/director outputs, binding import/page/geometry and optimistic revisions. Validate it against the canonical corrections schema; derive consumer types. Apply human kinds after model/provisional labels, rebuild only downstream page inputs, and retain causal scene dependencies. Speaker-only edits do not invalidate current visual/audio stages. Journal correction/script/audit publication so interruption restores the last usable pair. Confirmations never invent calibrated confidence; voice/re-voice remains visibly deferred. See `reports/M4a.md`.

## D39 — Shared correction fields and gesture arbitration

Reader-context fixes reuse the canonical M4a correction sidecar/API and the same generated fields as chapter review. Hold on text opens a source-bound fix sheet; hold elsewhere opens full-page context. Preserve the later Flow up/next, down/previous behavior instead of replacing its backward gesture with overview. Captured holds/multi-contact input cancel Flow selection and accidental clicks; two-finger tap replays. Tap-paced center finishes a playing scene, while RTL/LTR side zones explicitly navigate. Return to the corrected stable panel paused. Guidance follows decoded line duration on the existing output clock and is a separate outline with a static Reduce motion state. No MotionScript change. See `reports/M4b.md` for evidence and actual-device/voice limits.

## D40 — Compatible official segmenter and conservative source envelopes

Keep Torch 2.4.1 and pin the official SAM 2.1 release revision that supports it, rather than replacing the shared runtime to follow current main's video optimizations. Image inference needs no compiled connected-components extension. Measure the small model alone behind the scheduler (808 MiB sampled device peak); cache segmentation separately from CPU pose proof. Use conservative inverse source-cell envelopes with only original pixels and continuous text/panel guards. A bounded upper-character region can retain a fixed lower attachment where full-body motion is unsafe; identify that limited scope explicitly. Current five-page evidence yields one candidate and 29 rejections. Do not equate structural safety or a small cutout with broad convincing 3D depth. See `reports/M4c1.md`.

## D41 — Shared transform identity and selective alpha rendering

Generate transform hashes with the exact JavaScript consumer canonicalizer; Python numeric JSON spelling differs for integral floats. Invalidate CPU proof caches on this fix, retaining verified SAM masks. Bind inspected candidates to unchanged source geometry before final/streamed publication. Render original page TextureSource through alpha-only masks and only proved linear poses; mask RGB never supplies artwork. Reject stale preparation and visibly fall back for unavailable masks. Keep static/fixed evaluation baselines free of directed layers. One inspected upper-character prototype is supported; wider depth and user ratings remain acceptance work. See `reports/M4c2.md`.

## D42 — Explicit verified offline copies and bounded speculation

Use native browser APIs and the existing runtime rather than adding cache/PWA dependencies. Enable storage through the D-profile launcher; ordinary views do not silently initiate browser-cache downloads. Verify all snapshot assets before atomically switching the local offline pointer. Failed saves preserve the last usable copy; never cache mutation/review/key/model routes. Bound speculative textures by both ±2 pages and pixels, and next-two-panel PCM by count/bytes. Pin current resources against stale prefetch completion; serialize rapid navigation. Let shell updates wait for active readers to close. Record browser emulation separately from phone/physical audio evidence. No MotionScript change; see `reports/M5a.md`.

# Open questions and gates

The PRD's §12 questions are tracked here. Items are ordered by the first milestone they affect. Only the plan approval and real pages block M0; later preferences can be chosen when their milestone starts.

| ID | When needed | Question / current answer | Recommended default or next action |
|---|---|---|---|
| Q01 | Resolved | The user said “start with the implementation,” authorizing M0a after the Step 1 plan. | Execute M0a only, then stop for the next approval. |
| Q02 | Resolved for M0a | Five readable supplied English/RTL pages benchmarked; mixed series, not a continuous chapter. A sixth mislabeled AVIF was preserved and excluded. | See reports/M0a.md. Use independent sample order for M0; obtain a continuous chapter for later continuity evaluation. |
| Q03 | Resolved | D-only Python 3.11.9 and pinned Magi stack passed imports, pip check, five-page CUDA inference, and cache replay. | Keep exact lockfile and D cache routing; verify before upgrades. |
| Q04 | Resolved for five-page sample | Verified pinned weights fit: 2,145 MiB device peak for five-page inference, 2,415 MiB for the OCR diagnostic batch. User waived licensing approval concern for personal use. | New sizes/batches/dependencies require measurement. Magi crop OCR was poor; user-authorized Baberu optimization recovered all 53 crops with documented remaining limits. See reports/M0a-optimization.md. |
| Q05 | M1 | Source language: Japanese raw, English translation, or both? | Per-series setting as in PRD; infer the first golden-set language only for initial tests, retain both as configuration. Confirm before choosing default OCR/TTS route. |
| Q06 | Resolved: mobile first | User explicitly prioritized mobile readers and navigation without repeated button presses. | Plan Flow mode and one-start Auto; actual phone/browser still needed for device trials in M1f/M5. |
| Q07 | M2 | Are there approved reference clips for principal voices, or should the tool generate designed voices locally? | Use designed/local voices or the user's own clips. Never clone actors or third parties without explicit rights. |
| Q08 | M2 | Is Fish Audio access desired for expressive lines, and what is the acceptable per-chapter spend? | Fully local route is the baseline. Verify current price, terms, and API behavior before proposing selective Fish calls; do not require it for M2 acceptance. |
| Q09 | M3 | Which permitted VLM director provider/key should be used, and what privacy/cost limit applies to page images? | Keep an adapter and a local fallback; make no cloud call until the user configures the key and terms are verified. |
| Q10 | M3 | What is the typical content mix for camera tuning? | Normal/subtle default; calibrate on the 3 test chapters rather than assume action-heavy material. |
| Q11 | M4c1 | How can source-only character layers produce clean pop-out depth on real panels? M0b accepted 0/30 rectangles. | Find/prove safe masks/poses or use original artist layers; unsafe panels fall back, but the overall F01 requirement stays open until real depth is demonstrated. |
| Q12 | Beyond v1 | Should vertical webtoon/manhwa strips be supported? | Keep out of v1 per PRD non-goals. |

## Resolved from the supplied PRD and environment

- Hardware: RTX 4050 Laptop, 6,141 MiB total VRAM; 15.65 GiB system RAM. Exact free memory and performance vary; see `ENVIRONMENT.md`.
- Deployment: offline chapter processing, PWA reader, audio master clock, one heavy model at a time.
- Cloud scope: VLM director and selective Fish expressive lines only, subject to verified terms and configured keys.
- Art: no generative redraw or inpainted replacements under the user's hard constraint; D05/D06 need plan approval because the PRD contains conflicting optional paths.
- WSL2: installed command is not presently usable. Native Windows is the initial route, pending Q03.
- At Step 1 there was no Git repository or golden set. Git is now initialized and five real pages have been measured; see reports/M0a.md.

- English initial OCR route is now measured: Baberu hybrid GPU vision/CPU decoding. Japanese OCR and independent full-chapter quality remain unevaluated; see D19.

- M0b approved; subsequent user steering replaces narrator work with a visual/SFX-first preview. Voice work remains deferred, with interfaces/events preserved. Parallax remains gated by original-pixel fidelity; see D20 and reports/M0b.md.

## Final-product feedback recorded (2026-10-01)

- User watched M0b and said “pretty good for a v0.” This is positive prototype feedback; it does not establish an explicit better-than-static preference, comfort score or next-milestone approval.
- F01–F04 in `docs/FINAL_PRODUCT_REQUIREMENTS.md` are required final outcomes: character depth, scene SFX + quiet tonal music, mobile Flow, reading-aware Auto. No new blocking question is needed for this planning update.
- Music scope is authorized; local library/procedural stems are the low-cost default. A concrete music/layer contract proposal still needs version-bump approval if v1 must change.
- Provisional pacing is adjustable English 240 wpm plus art time; language-specific manga calibration remains future evaluation. The current 12-second prototype cap is not final acceptance.
- Actual phone model/browser and a continuous test chapter will be requested when the corresponding device/continuity trial is reached.

## M1a continuation (2026-10-01)

- User's “ok continue” authorizes M1a only. Folder/CBZ/PDF import, source preservation, settings and page cache are verified; no current import blocker needs a question. See `reports/M1a.md`.
- Initial RTL/English defaults are explicit and overridable per series; M1a does not choose an untested OCR/TTS language route. PDF resolution is recorded/configurable.
- A continuous chapter, real phone, semantic SFX/music, perceived depth and uncapped reading-aware Auto remain later acceptance work. The subsequent “continue with the next work” authorized M1b.

## M1b continuation (2026-10-01)

- M1a commits were pushed to the user-provided `Bhatta2006/Manga-Motion` GitHub repository. M1b connects imports to detection, ordered panels, crop OCR and durable intermediate artifacts; no reader/voice/contract change. See `reports/M1b.md`.
- English/RTL is the measured initial route. Other source languages fail before model loading until their adapters are evaluated. Real LTR/continuous chapters and the actual phone remain later evaluation inputs.
- **Resolved approval gate — D26:** verified Magi/Baberu APIs do not supply calibrated confidence. The user answered the M1b approval request with “continue,” approving `null` scores, explicit unavailable warnings and concrete review reasons while deferring numerical calibration to an independently labeled set. PRD §2 now records this exception; calibration itself remains unachieved.
- Provisional five-page panel/order/dialogue quality thresholds pass; independent accuracy is not established. Cold detection+OCR measured 6.53868 s/page; final fully cached replay 0.2891 s. Battery operation was observed after the cold run, without isolating the slowdown's cause.
- The same user reply authorizes M1c; no new models/cloud calls are needed.

## M1c continuation (2026-10-01)

- M1c builds v1 camera output from actual imported/analyzed pages and checks it before publication and reader initialization. Existing schema fields/version are unchanged. Failure-path/cache/property/browser evidence is in `reports/M1c.md`.
- The user's instruction to avoid future errors is addressed through concrete tested guards. It is not interpreted as a guarantee that all future inputs/dependencies/devices are error-free.
- Actual glyph size/readability needs the target phone and a measured readable-text threshold; text-box proxies flag nine small boxes at 390×600, without claiming unreadability or a font-size pass. This remains visible for the planned mobile/readability trial; no art is regenerated or other text cropped to mask it.
- M1d's chapter job/Library wiring and M1e's reading-aware Auto remain unstarted. Stop for approval of the reported M1c scope and its limits.

## M1d continuation (2026-10-01)

- The user's “okayy continue” approved the reported M1c scope/limits and authorized M1d. Local import jobs, durable checkpoints/retries, the Library and immutable reader URLs are now tested. See `reports/M1d.md`; no new model, voice or cloud call was introduced.
- Full five-page cold request-to-readable time is 52.178 s; cached repeat 4.160 s. Heavy inference averages 4.86034 s/page, still above the ≤3 s target. AC was online throughout; this is not an isolated battery/power comparison.
- All 25 panels pass desktop and mobile-viewport navigation; actual phone usability/FPS/external A/V sync remain unmeasured. Legacy SFX still plays through the new API asset URLs.
- Complete chapters publish atomically. First-page availability equals chapter availability; incremental page streaming remains an unmet final-product requirement, not a waived PRD item. Add it to an approved follow-up slice before final acceptance.
- Stop for M1d approval. M1e reading-aware Auto remains unstarted.

## Feedback after M1d (2026-10-02)

- The user correctly identifies that dialogue-based Auto timing, real character
  cutout depth and scene SFX remain missing. Current Library chapters contain
  camera events only; the older M0b sounds are a procedural preview. These are
  not completed final features. Reader controls now distinguish chapters without
  SFX and label the current Auto as a preview.
- Recorded F05/M5d for unused side-space treatment after the core experience;
  original panels must not be stretched/cropped or given invented background.
- Added M1g to give the unmet streaming requirement an explicit delivery slice.
  There are 21 remaining slices: 17 for current visual/audio/mobile scope and
  later side polish, plus four deferred voice slices. No completion-date guarantee
  follows from the count; actual-device/quality evaluation gates remain.
- This feedback is not treated as approval to begin a later milestone. M1e is
  next, under the user's original one-milestone-at-a-time approval instruction.

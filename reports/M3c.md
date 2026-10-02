# M3c — Local scene sounds and comparison preparation (2026-10-02)

## Built

Eight owned CPU procedural categories behind a replaceable provider: impact, whoosh, footsteps, door, heartbeat, rain, wind and chime. Deterministic 24 kHz mono PCM WAVs have silent edges, peak headroom, exact hashes/provenance and missing/corrupt asset repair. The global local catalog is `library/sfx/manifest.json`; chapter cue/asset audits are `cache/scene-sfx.json`. Private generated assets remain ignored by Git.

Route explicit director cues only when printed text agrees with its final kind. Restrained scene accents can follow impact/chase, tension, playful reactions or an outdoor scene summary; these are marked stylistic and unverified, not asserted literal noises. At most three cues/page and one of each inferred stylistic category/page. Quiet scenes may have none. No page-turn sound is inserted. Suppression reasons stay in the audit and contribute Library review counts.

Both streaming and final compilation append the same sorted, valid v1 SFX events from page-hash/semantic-input/version caches. Asset checks force repair before publication. A separate SFX duck gain leaves the user's mute independent; real future voice windows use decoded durations, merged overlap and 20 ms attack/120 ms release to duck SFX by 6 dB. Current golden chapters contain no voice lines, so voice ducking has functional tests but no actual cast listening evidence.

Anonymous static/fixed/directed comparison snapshots preserve source assets, panel camera extents, transition durations and exact audio events. Static shows the original whole page. Conditions are shuffled and labels withheld in the reader; a private mapping permits later scoring. See `docs/evaluations/M3c-blind-evaluation.md`. Preparation is not a blind-test result.

## Verification and measurements

No new model, repository download, cloud service or dependency. Reuse pinned NumPy and standard-library WAV support. Assets are project-generated, with no third-party recording license dependency. [W3C Web Audio automation](https://www.w3.org/TR/webaudio/#dom-audioparam-linearramptovalueattime) verified gain scheduling APIs; browser tests check actual output. One-heavy-model scheduling remains unchanged.

- `python -m unittest discover -s tests -p 'test_*.py'`: **89 tests, OK (29.586 s)**. Catalog determinism/headroom/edges, cue conflicts/cap, damaged-file repair, anonymous variant audio/time parity and existing pipeline gates pass.
- `npm test --prefix reader`: **15/15**; decoded voice duck duration, overlap merging and resume/mute separation checked. `npm run build --prefix reader`: passed.
- `python tests/verify_m3c_golden.py`: five actual pages/25 panels, full shared v1 validation, source hashes unchanged. **Four cues:** one wind each on the two outdoor pages, one chime each on two reaction pages; the quiet school conversation page stays silent. **Three conflicting whooshes and two repeated chimes suppressed.** All four choices need subjective scene review.
- Final `scene-sfx-map-2` cold page times **.0046/.0050/.0006/.0035/.0037 s**, mean **.00348 s/page**. Stage **1.6786 s** including telemetry/startup; full cached-camera + cold-SFX compile/validation **1.855908 s**. Device peak **0 MiB**, Python RAM peak **35 MiB**, AC online. Warm full compile **.208006 s**, SFX **5/5 cache hits**; warm memory unmeasured. Two unique files total **91,288 bytes** (reused across panels/pages).
- Actual file peak after gain: wind **−27.90 dBFS**, chime **−21.90 dBFS**; RMS **−42.77/−36.70 dBFS**. These are digital sample levels, not perceived device loudness or full cast true-peak/LUFS evidence. All dry categories peak at approximately −9.90 dBFS; no PCM clipping. Reading/motion timeline stays **137.75 s**, unchanged by these short cues.
- `node reader/tests/sfx-smoke.mjs`: Edge 154.0.4258.48, four expected scene panels have nonzero Web Audio output; mute silent, pause stops output, missing assets show an error while silent clock playback continues; zero page errors. This establishes output routing, not that sounds feel appropriate or immersive.
- Final integration: `node reader/tests/library-smoke.mjs` passes all 25 panels at 390/1280 CSS width, source-view access, controlled RTL/LTR keys, failed-import recovery with saved playback, and audible legacy SFX. Zero page errors; two textures at finish. These are desktop browser checks, not actual phone measurements.
- Expanded SFX smoke also opens all three anonymous snapshots, verifies camera captions and reading-speed controls are hidden, and hears actual output in each. It caught a CSS `display:flex` override of the hidden reading-speed label; the targeted hidden-label rule fixes it. Rebuilt reader and rerun: three snapshots pass, four ordinary cue panels audible, mute/pause/missing-asset checks pass, zero page errors.
- Live directed-page worker with cold chapter-local sound assets: first prefix observed **3.014228 s**, full request **4.696690 s**, worker **3.627769 s**, first worker-readable **1.807844 s**. All analysis/director caches hit; final camera/SFX reuse streamed artifacts. First-to-final source hashes unchanged. No heavy model was loaded in this warm-inference test; CPU sound sampler measured 0 MiB GPU and 71–72 MiB worker RAM. Cold VLM-resident publication memory has not been measured separately.
- `python -m pipeline.audio.evaluate --series golden-m1d --chapter chapter`: three validated anonymous immutable snapshots prepared. Five mixed pages are a functional comparison fixture, not the required three continuous chapters.

## Acceptance / remaining gates

- [x] Played assets have owned source/provenance and personal-use permission.
- [x] SFX category, timing, level and selection/suppression reasons are inspectable.
- [x] Mute/silent fallback and future voice ducking are tested.
- [x] Label-blind comparison preparation/form is available and preserves controlled audio/time inputs.
- [ ] Blind directed/comfortable averages ≥4/5 on real supplied test chapters.
- [ ] Zero user-reported discomfort established by an actual viewing trial.

Sound quality and semantic appropriateness remain provisional; procedural accents do not replace realistic recordings for every scene. No heavy Stable Audio generation is needed because the small catalog covers current supported categories; the provider can be swapped. Quiet tonal music, persistent ambience and character depth require the next concrete contract proposal. No subjective gate, actual-phone result or final scene-sound accuracy is marked passed.

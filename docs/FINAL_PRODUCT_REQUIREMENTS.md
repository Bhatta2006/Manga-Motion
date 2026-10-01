# Final-product requirements from prototype feedback

Date: 2026-10-01. Source: the user's feedback after watching M0b. These requirements amend the product plan; **they are not implemented features or approval to start another milestone**. See PRD §14 and decisions D21–D24. The original uploaded PRD is retained unchanged.

## F01 — Characters feel lifted from the page

**Required experience:** a character cutout reads as a foreground plane, with visible depth relative to the page/background. Separate foreground, middle and background motion where supported; bounded scale/perspective differences and differential motion should create a restrained pop-out effect. A uniform zoom of the whole page does not satisfy this requirement.

**Implementation constraints:** offline source-only segmentation/layer preparation behind verified adapters; retain original texture pixels and linework. No inpainting, invented background or regenerated anatomy. Keep text on a readable plane. Test occlusion, exposed holes, duplicate subjects and layer-edge seams throughout the animation. A segmentation mask alone does not recover hidden background. Eligible poses can cover the old silhouette, or use original artist-provided background/layer assets; prove the coverage rather than assume it.

**Acceptance:** demonstrate the effect on real manga panels, with source hashes intact, no visible duplicates/holes/seams, readable bubbles, bounded motion and a functioning Reduce motion control. User rates perceived depth and comfort ≥4/5 on the demonstrated set. Panels that cannot pass use camera-only motion, but a no-go on all samples leaves F01 **unmet**. M0b's 0/30 eligible rectangles is a feasibility finding, not final depth acceptance.

**Measure:** real panel eligibility, artifact counts, depth/comfort ratings, mask preparation seconds/page and peak VRAM/RAM, mobile frame times, texture memory and motion amplitude. Staged processing still permits one heavy model at a time on the 6 GB card.

## F02 — Story-aware SFX and quiet tonal music

**Required experience:** effects reflect events in the scene; a quiet, noticeable tonal music bed follows the current story mood and remains coherent across adjacent panels in the same scene. Silence is a valid deliberate cue. Do not play decorative whooshes everywhere or change tracks on every panel.

**Implementation direction:** use Director mood/energy/scene context and classified printed SFX to choose local sounds and tonal stems. Start with a small curated local library and owned procedural tones; no heavy music generation model or new cloud music API is authorized. Keep selection/rendering behind adapters. Low-confidence scene associations remain reviewable and use a restrained fallback.

Music, ambience, effects and future dialogue need separate buses. Persist the bed across panel boundaries, crossfade mood changes, duck under speech/important SFX, prevent clipping, expose independent levels/mutes and pause/resume coherently. Background music duration must **not** extend a panel's reading timer. Silent mode mutes all audio.

**Acceptance:** labeled scene cues select appropriate effects/moods on real material; no unintended loops/restarts at panel boundaries; no clicks/clipping on fades; levels/mutes/ducking work; user judges music audible, immersive and unobtrusive on the actual reading device. Procedural M0 accents do not satisfy final semantic audio acceptance.

**Measure:** cue/mood accuracy, incorrect/uncertain cue rate, crossfade continuity, loudness/true peak and ducking, cache/build cost, reader memory/CPU, subjective immersion and distraction. Exact gain/fade settings are tunable and must be evaluated rather than called universally correct.

## F03 — Mobile Flow navigation without repeated button presses

**Required experience:** read comfortably with one hand. Routine scene changes must not require finding and pressing Next/Previous buttons.

**Planned default:** a **Flow mode** where a short vertical thumb scroll progresses through the detected manga reading sequence; camera framing follows the transition and settles on the next panel. The sequence remains the correct RTL/LTR order even though the navigation gesture is vertical. This is navigation for paged manga, not expansion into webtoon import. Overscroll/scroll back exposes page context naturally. Transport buttons remain optional accessible controls.

**Hands-free option:** one start gesture enters dialogue-paced Auto; tap anywhere pauses/resumes. A user scroll interrupts Auto and selects the scene without fighting a timer. While manually dragging between scenes, pause the audio timeline; activate scene audio once after selection settles. Resume within-panel motion on the audio clock. Scrolling must not replay an effect dozens of times or cause competing clocks.

**Acceptance:** complete a supplied chapter on an actual phone without pressing Next/Previous buttons; scroll forward/back retains order; transitions do not skip scenes; auto/manual handoff, replay and original-page context work; browser scrolling/zoom and assistive controls remain usable. No sensor permission is required. Optional drag/tilt depth controls may be evaluated later with a touch fallback.

**Measure:** navigation gestures/chapter, required transport clicks (target zero for routine scene advancement), accidental skips, handoff latency, frame times on the actual phone, touch/zoom conflicts, one-handed comfort. A 390 px desktop emulation is layout evidence only.

## F04 — Auto dwell follows dialogue and reading speed

Count **dialogue and readable captions**, excluding SFX, watermarks and translator notes. Maintain correct bubble order. A silent panel receives art-inspection dwell. More text must produce more time when other inputs are equal.

Starting English default: **240 words/minute**, adjustable and subject to manga-specific calibration. Research estimates adult English prose at 238 wpm for nonfiction and 260 wpm for fiction; it does not establish manga reading speed. The default uses a rounded prose baseline, then adds visual-inspection time. Source: [Brysbaert's reading-rate meta-analysis](https://biblio.ugent.be/publication/8647789).

Planned rule:

```text
read_time = 60 × dialogue_and_caption_words / selected_wpm
reading_budget = read_time + art_inspection_time + punctuation/beat_pauses
panel_dwell = max(minimum_dwell, reading_budget, future_dialogue_audio_end + tail)
```

Only intentional scene pauses/visual inspection affect dwell; music loops do not. The audio output clock remains master, using silence for the remaining reading budget when speech is absent or finishes early. No arbitrary upper cap may truncate a dense panel. If motion finishes earlier, hold its end framing until dwell completes. Missing/uncertain OCR must be flagged and receive a conservative fallback, not silently treated as zero words. Other languages need appropriate character/token-based calibration, not blind reuse of English WPM.

**Acceptance:** monotonic duration for 0/10/40/100-word cases with identical settings; dense panels exceed the current prototype's 12-second cap when needed; captions included/non-reading text excluded; empty/error OCR handled separately; narration never cut short; speed settings produce the expected scaling; user can comfortably read real sparse and dense scenes without routine pausing.

**Current prototype limitation:** it uses all associated OCR text at roughly 180 wpm, adds a base hold and caps at 12 seconds. That heuristic does **not** meet the final F04 requirement.

## F05 — Side-space treatment after core delivery

Added 2026-10-02 from the user's follow-up.

The user's follow-up identifies inconsistent empty space around panels of
different aspect ratios. After the core experience is complete, design a coherent
surround for smaller/narrower frames. This is planned polish, not an implemented
feature or a reason to crop/stretch panels or regenerate missing artwork.

Recommended starting design: a quiet ambient gradient or subtle abstract ink
pattern in the unused space outside the art, with optional mood tint once scene
metadata exists. Keep the main panel/text clear and the surround unobtrusive;
preview the actual design before choosing it. Allow a plain surround and respect
Reduce motion. Test narrow, wide, square and irregular panels on desktop and phone.

Acceptance: the user approves visual consistency and lack of distraction; no
source pixels, camera bounds or text visibility change; no texture leak, layout
overflow or material frame-time regression. Schedule as M5d after core delivery.

## Delivery and contract gates

| Requirement | Planned slices |
|---|---|
| F04 reading-aware auto timing | M1e; future voice integration in M2d |
| F03 Flow navigation | M1f; actual-device polish in M5a/b |
| F02 scene-aware effects | M3a + M3c |
| F02 tonal music and scene continuity | M3d1 contract proposal, M3d2 cue/library preparation, M3d3 reader mixing |
| F01 source-only pop-out depth | M4c1 mask/occlusion feasibility, M4c2 depth rendering and user evaluation |
| F05 unused side-space polish | M5d, after core delivery |

After M1 foundations, prioritize visual/mood-audio/depth slices over voice engine work, consistent with the user's earlier steering. Milestone IDs stay stable for traceability; dependencies and each approval gate still apply.

MotionScript v1 is unchanged by this planning update. Scene-spanning music and explicit layer/depth metadata may need a new contract. M3d1 must produce concrete schema/example/migration changes and obtain the user's version-bump approval before any unsupported fields/events are implemented. This feedback approves product scope, not an unseen schema. Nothing weakens D-only downloads, source-art preservation, adapter boundaries or the 6 GB stage scheduler constraint.

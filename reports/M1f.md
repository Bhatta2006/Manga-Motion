# M1f — Mobile Flow and Auto handoff (2026-10-02)

## Built

Native vertical scroll rail with scene snapping, one-scene flick limit, mobile-default Flow, tap pause/resume and manual interruption of Auto. The Pixi scene keeps the existing Web Audio clock. Original-page context and accessible transport/keyboard controls remain available. Settling on the current scene does not reload/replay it. No model/dependency/schema change.

## Evidence

- `npm run build --prefix reader`: TypeScript/Vite passed.
- `node reader/tests/flow-smoke.mjs`: Edge 154.0.4258.48, 390×844 viewport. All 25 real panels visited in RTL and controlled LTR direction, **zero Next/Previous clicks**, bounded textures (2 at final scene). Forward/back scroll, oversized flick limited to one scene, same-scene settle preserves switch count; tap pause/resume, Auto interruption and original-page handoff pass. Body width 390, zero errors. LTR uses an explicit test-only direction fixture; real LTR analysis remains unverified.
- Existing M1e clock/timing behavior is retained. Flow selects scenes rather than replacing within-panel time with a scroll animation clock.

## Measurements and pending acceptance

No pipeline stage invoked: zero model loads/downloads, no pipeline VRAM allocation or preparation seconds/page. Browser GPU/RAM are not equivalent to pipeline VRAM and have not been measured on a phone. Private browser evidence is in ignored `reports/M1f-browser.json`.

Technical button-free sequence, single-scene selection and handoff checks pass on desktop emulation. **Actual phone touch/zoom/comfort/FPS and repeated real-SFX listening remain pending.** Current five-page Library fixture contains no SFX; switch-count evidence cannot establish perceptual audio quality. Phone/browser and continuous chapter requested asynchronously. This is not final mobile acceptance.

## API verification and limits

Current native [CSS scroll snap](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Scroll_snap) and [scrollTo](https://developer.mozilla.org/en-US/docs/Web/API/Element/scrollTo) docs checked before use. Existing pinned Pixi/Playwright/Edge runtime reused from D-drive profiles. No sensors or cloud calls.

Proceed to M1g incremental page publication under the user's all-milestone authorization.

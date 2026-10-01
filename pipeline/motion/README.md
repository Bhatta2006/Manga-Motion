# M1c camera compiler

Run after M1a import and M1b analysis:

```powershell
. .\scripts\enter-runtime.ps1
& .\.venv\Scripts\python.exe -m pipeline.build_motion --series my-series --chapter ch01 --run-label cold
```

This creates `library/<series>/<chapter>/motionscript.json` and `cache/camera-audit.json`. It uses original serving images in place; no copies, generated pixels, models, network requests or voice assets. It preserves M1b's panel order, prefixes local panel/text IDs by page ID and keeps calibrated confidence unavailable under approved D26. Review reasons remain in the sidecar, without new v1 fields.

The solver protects the union of the entire panel and every assigned text box. Allowed bleed is text overflow plus 4% of that union's width/height, clipped to the original page. Both camera endpoints contain that union, so linear rectangle interpolation under monotone sine easing preserves it at every time. The union center stays within the central 60%; this does not assert every bubble center is central. No art is regenerated. Missing panels/ambiguous order use a hold.

Restrained push/pull/pan recipes depend only on ordered panel index, not guessed story mood. Relative zoom is bounded against the broad frame; analytic derivative bounds enforce ≤1.4x scale, ≤0.6x/s sustained zoom and ≤1.2 original-panel widths/s pan. No shake/punch/whip is emitted. Candidate 400 ms adjacent-panel glides exceeding speed caps become cuts; page boundaries use a 200 ms fade. Full cinematic grammar belongs to M3.

Camera events last 2 s with the existing 0.4 s panel tail. This is a provisional tap-paced camera extent, **not** the later dialogue-aware Auto timer. No spoken text/audio is fabricated. Future v1 line events and decoded SFX durations remain supported by the existing audio clock; M1e replaces reading policy. Reduce motion holds the first frame; original-page access stays available.

Readability audits show text-box heights at 390×600 and 1280×700 CSS viewports, flagging boxes below a provisional 24 px. **Box height is not glyph/font size.** Some supplied boxes remain small on mobile; widening a view cannot enlarge their glyphs. Actual-device minimum readable glyph size remains unverified. Never claim font readability from a no-crop proof or silently crop other text to make this audit pass.

Every page stage is keyed by original hash, analysis content, solver revision and duration. Camera payload checksums detect parseable accidental cache damage and trigger repair. The chapter library lock serializes import/analysis/build. Input metadata and source hashes are checked again before publication. Validation failure leaves the previous complete MotionScript untouched.

Before publishing, Python checks geometry/timing and invokes the reader's already pinned AJV over stdin to validate the **unchanged** shared JSON Schema and shared reader semantic checks. Node and reader dependencies must be installed; a missing/broken validator fails explicitly before publishing. No second JSON Schema implementation/dependency was invented.

## Verified dependency usage (1 October 2026)

No installs/upgrades/downloads. Existing D: `reader/node_modules` pins/README/license records checked: AJV 8.20.0 (MIT), TypeScript 5.9.3 (Apache-2.0), Vite 8.3.2 (MIT), PixiJS 8.21.0 (MIT), Playwright Core 1.63.0 (Apache-2.0). Existing Node v24.21.0 is read from `C:\nvm4w\nodejs\node.exe`; all project, npm cache, browser profile/artifact/download/temp writes are routed to D:. No GPU model is involved; observed pipeline GPU use is in `reports/M1c.md`.

Current official docs verified: [AJV compile API](https://ajv.js.org/api.html), [TypeScript narrowing](https://www.typescriptlang.org/docs/handbook/2/narrowing.html), [Vite build](https://vite.dev/guide/build), [Pixi Container](https://pixijs.com/8.x/guides/components/scene-objects/container), [Playwright routing](https://playwright.dev/docs/api/class-browsercontext#browser-context-route), [Python JSON finite-number serialization](https://docs.python.org/3.11/library/json.html). Existing published adapter/model APIs are not invoked by this milestone.

Tests:

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
& .\.venv\Scripts\python.exe tests/verify_m1c_golden.py
npm run build --prefix reader
npm test --prefix reader
node reader/tests/camera-smoke.mjs
```

The real-page checks require the user's ignored five-page fixtures and the existing preview server on 127.0.0.1:5173. The browser test routes only its own chapter requests to the compiled fixture; it does not replace the user's preview chapter. Public `schema/examples/basic.json` supplies a contract fixture without private manga. Actual phone/continuous-chapter and subjective comfort evaluation remain later gates.

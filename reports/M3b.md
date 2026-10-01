# M3b — Bounded semantic camera grammar (2026-10-02)

## Built and checks

All ten v1 beat classes have deterministic bounded rules: establish drift, dialogue master hold, reaction/emotional focus push, reveal pull, impact/shock punch and hit-stop/eligible creep, constant-speed chase pan, comedy overshoot/settle, flashback drift/dissolve/vignette, quiet minimal push and transition hold/dissolve. Existing v1 easing/events remain unchanged. Safe focus is derived from original detector geometry (face proxy: upper 35% of a character box), with every assigned text box protected. Ambiguous order/fallback geometry holds. Unsafe focus framing falls back visibly in the audit.

Every camera segment is audited, including settles/holds. Maximum scale 1.4; sustained zoom .6/s and pan 1.2 panel widths/s; transient punches use the PRD exception. Impact shakes are bounded below 1.5% viewport × energy, decay over 250 ms, capped at three eligible panels/page, and disabled when text lacks 2% edge clearance. Subtle/Normal/Hype scale motion amplitude within solved bounds. Reduce motion disables movement, shake and flash. Soft vignette is a separate overlay; same-page dissolve blends two sprites sharing the original texture. Audio clock drives all poses/effects/transitions.

- `python -m unittest discover -s tests -p 'test_*.py'`: **85 tests, OK**, including all ten beat rules, continuity, text protection, invalid sustained speed and future line-start follow scheduling.
- `python tests/verify_m3b_golden.py`: **5 pages/25 panels**, unchanged original hashes, shared AJV v1 validation, **101 poses/segment**, **zero geometric comfort violations** and zero focus fallbacks.
- `npm test --prefix reader`: **13 tests passed**; preset bounds, three-shake cap, edge protection, decaying clock-driven effects and Reduce motion tested.
- `npm run build --prefix reader`: passed.
- `node reader/tests/motion-smoke.mjs`: Edge 154.0.4258.48 at 390×844, all 25 panels navigated; preset controls and static Reduce motion verified, zero errors, no horizontal overflow, two textures at finish. Median 6.9 ms/p95 7.2 ms across 355 samples; clock-sampling proxy max .3 ms. Actual phone and external A/V measurement remain pending.

## Measurements

Final `camera-m3b-2` CPU-only cold application-cache run: .0021/.0015/.0014/.0011/.0013 s per page, mean **.00148 s/page**; full compile/validation/telemetry **1.848334 s**. VRAM **0 MiB**, Python RAM peak **22 MiB**. AC offline, battery 89%; this is not a matched comparison with earlier AC runs. Earlier revision warm five-page compile .211794 s; final revision warm timing is not separately claimed.

Golden maximum relative scale **1.25**, sustained zoom **.15625/s**, pan **.09446786 panel widths/s**. Reading/motion timeline totals **137.75 s**; longer beat motions may extend short dialogue budgets. Nine text-box height proxies remain below 24 CSS px at 390×600; none at 1280×700. Box height is not actual glyph size and not a mobile readability pass.

## Remaining fidelity and quality gates

Technical bounded-rule, text/source integrity, Reduce motion and shared-clock checks pass. User comfort and actual-device performance are unverified. The five pages contain no independently labeled chase/impact/flashback examples; synthetic rule tests are functional evidence only.

This is a restrained **v1 realization**, not a claim that every PRD recipe is finished exactly: v1 supports neither exponential/spring easing nor explicit direction vectors/blur cues. Shock uses outQuad; comedy uses a bounded two-segment overshoot; chase uses geometry-direction pan and needs a labeled semantic vector. Speaker-follow timing is implemented as a tested line-start scheduler but cannot demonstrate cast following until the deferred voice/speaker stages supply real line events. These remaining exact-recipe details stay open for the contract proposal/next director refinements; they are not silently waived. No new model, downloaded asset or contract field was introduced.

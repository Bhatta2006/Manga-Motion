# M1d feedback follow-up — 2026-10-02

The user identifies missing dialogue-paced frame changes, character cutout depth,
scene SFX, and inconsistent unused space around differently shaped panels, and
asks how many milestones remain. These are real final-product gaps; M1d delivered
the chapter/job/reader foundation, not those features.

## Changes

- Disable/uncheck the SFX toggle and label it **No SFX** when the chapter contains
  no SFX events. Keep it enabled for chapters that actually contain effects.
- Label existing Auto **Auto (preview)**, since it does not implement M1e's
  dialogue/caption reading budget. No new pacing/depth/audio feature is claimed.
- Record F05 in the requirements/PRD and M5d in the roadmap for side-space polish
  **after core delivery**, keeping source pixels/aspect ratio/text intact.
- Add M1g for the previously documented unmet page-streaming requirement.
- Count unfinished slices directly from milestone headings: **21 total**, including
  **17 current visual/audio/mobile + later side-polish slices** and **4 deferred
  voice slices**. Outstanding actual-device/independent-quality checks remain.

## Evidence

After entering the D-drive runtime:

```text
npm run build --prefix reader
TypeScript check passed; Vite 8.3.2 built 791 modules.

npm test --prefix reader
tests 9; pass 9; fail 0

node reader/tests/library-smoke.mjs
SFX-disabled/unchecked assertions pass on camera-only chapters at both viewports.
Auto (preview) label assertion passes.
SFX-enabled assertion and nonzero Web Audio signal pass on preview/m0b.
Both viewports visit all 25 panels; RTL/LTR checks and real failure/retry pass.
pageErrors: []

Milestone heading count
remaining count 21 without deferred voice 17

git diff --check
No whitespace errors.
```

No dependency/model download or contract change. The browser failure/retry test
reuses existing page/stage caches; memory samples for cached stages are unmeasured,
not invented as zero. No new inference or audio generation is required by this
follow-up. Build/test profiles/cache/artifacts remain on D. The original attachment
is untouched. No new milestone implementation started: M1e is next and retains
the user's one-milestone approval gate.

# M4a — Review queue and durable corrections

2026-10-02. Technical review/correction implemented. Actual-user correction timing and re-voicing remain pending; voice implementation is deliberately deferred per user priority.

## Built

Library chapters now have **Review**. The queue exposes unverified text/kinds, missing speakers, uncertain ordering/geometry, semantic scenes, camera, SFX and music notes with original-source crops. Page selection limits displayed thumbnails. The mobile editor appears first; its notes list scrolls independently. Desktop editor stays alongside the notes. No new model/API/dependency/download; existing pinned local FastAPI/Pydantic/AJV are reused.

Edit text/kind/panel association/speaker, move panels earlier/later, correct scene beat/mood/energy/time-skip, confirm checked text/scenes, or revert individual targets to the original model result. Source art and raw analysis remain unchanged. Speaker IDs persist for the future voice consumer; UI/API explicitly report voices pending, with no fake re-voice operation.

`schema/corrections-v1.schema.json` is the authority for the internal versioned correction sidecar. ECC contract-first workflow derives its TypeScript shape beside the existing generated types; server validates with pinned AJV plus source/target semantics. This is pipeline user data, **not a MotionScript contract change**. v1/v2 MotionScript schemas remain unchanged.

`corrections.json` binds chapter/import hash, page hash and detector geometry hash. Unknown fields/targets, partial/duplicate orders, stale geometry, foreign imports, unsupported enums and unsafe reassignment outside a panel fail before publication. Optimistic revision checks prevent another window's edits from being overwritten. The save route retains a recovery journal for the correction/script/audit pair: failures and interrupted saves restore prior usable data; startup and review reads recover pending transactions. Old playback snapshots retain their own assets.

Overlays apply after cached model output and before camera/scene-audio compilation. Human kinds override provisional pacing labels and model classes. Corrections therefore survive normal analysis/director reruns while OCR/detector caches stay intact. Text corrections invalidate only that page's downstream inputs; speaker-only changes do not invalidate camera/SFX/music. Scene changes may necessarily propagate music state to subsequent pages; that causal dependency is not suppressed.

## Evidence

- `python -m unittest discover -s tests -p test_review.py -v`: **4 tests pass**, final focused run **10.545 s**. Real five-page correction round-trip/rebuild; four unchanged pages remain cached and identical; human kinds/order/speaker persistence; speaker-only all five camera/SFX/music hits; stale geometry/import/IDs/shape rejected; failed compilation rolls back; pending process-death journal recovered; modified crop bytes rejected; foreign-origin POST rejected.
- Full Python regression: `python -m unittest discover -s tests -p 'test_*.py'`: **99 tests pass in 54.458 s**. Existing streaming/final, stage-lock, snapshot, timing and audio behavior included.
- `npm test --prefix reader`: **18 tests pass**. `npm run build --prefix reader` and `node reader/tools/generate-contract-types.mjs --check` pass; review chunk **9.27 kB / 3.58 kB gzip**.
- `node reader/tests/review-smoke.mjs`: actual local service and five real pages in Edge **154.0.4258.48**, 390 px viewport. Text edit/confirmation survives reload; order controls publish new order; stale POST rejects; simulated save failure leaves inputs editable; zero page errors and no horizontal overflow. Transient artificial text/order edits restore exactly after the test; they are not golden truth labels. Notes **172 → 171** after one text confirmation. Missing-speaker/music quality notes remain deliberately unresolved.
- `node reader/tests/library-smoke.mjs`: all 25 panels at desktop/mobile viewport, actual failed-import/retry, original-page view, RTL/LTR controlled key mapping, audible legacy SFX; zero page errors. A test initially ran concurrently with the mutating browser test and observed its temporary fixtures; verification was corrected to run these sequentially, with restored golden data and unique correction inputs. Final full regression passes; no product failure is hidden by that test orchestration fix.

## Measurements

Final automated correction: **3.013293 s** browser save-to-result, **2.594394 s** server save/rebuild/publication. This measures automated save, **not a human finding/editing/re-voicing a bubble in <10 seconds**. Full five-page CPU compilation is measured separately in private stage metrics; unchanged pages are cache lookups, not inference. Exact per-stage times/RAM/VRAM below are from this final run.

| Stage | Changed page seconds | Stage seconds | Cache hits | Parent RAM peak | Device VRAM baseline/peak |
| --- | ---: | ---: | ---: | ---: | ---: |
| Camera | .0030 | .1749 | 4/5 | 65 MiB | 10/10 MiB |
| SFX | .0092 | .1930 | 4/5 | 65 MiB | 10/10 MiB |
| Music | 1.2065 | 1.3904 | 4/5 | 82 MiB | 10/10 MiB |

Full compilation **2.368133 s**, contract validation **.203146 s**. Remaining four page entries in each stage record **0 s cached run time**. Music verifies existing owned assets; the measured number includes lazy CPU/NumPy work and exact integrity checks. No CUDA allocator sampling because no Torch model is invoked. AC online, battery 100%, saver off. Device VRAM increments are zero in the sampled stages; this is not a model-fit or actual-phone memory claim.

No detection/OCR/VLM/TTS model loads or network API charges. Source pixels and raw model caches remain intact. Actual-phone usability, isolated browser CPU/total native RAM and user timing remain unmeasured. Tests and private artifacts use D: exclusively.

## Acceptance / remaining work

- [x] Uncertain stage items exposed with source references/crops and explicit unavailable confidence.
- [x] Durable text/kind/order/association/speaker/scene overrides and per-target revert.
- [x] Corrected overlays survive repeat compilation; unrelated pages reuse caches in the tested text correction.
- [x] Original art/raw analysis unchanged; invalid/stale/conflicting saves and interruptions preserve usable output.
- [ ] Actual-user <10 s wrong-speaker fix and re-voice trial: awaits M2 voice implementation and user measurement.

`review.ts` contains the standalone forms; reader-context fix sheet/gestures remain M4b. A changed detector geometry deliberately requires re-review/rebinding instead of silently attaching old labels to new boxes. Calibration remains unavailable even after a human confirmation. Persistent scene notes are still listening/semantic quality gates. Character masks/pop-out depth remain M4c1/c2; whole-page parallax is not counted as that feature.

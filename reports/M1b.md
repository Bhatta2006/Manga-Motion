# M1b — Panels, reading order and crop OCR

Date: 1 October 2026. Authorized by the user's “continue with the next work.”

**Status:** implementation verified; quality thresholds met on the provisional five-page reference subset. M1b remains open for approval of D26: the verified models do not supply calibrated confidence scores. PRD §2 is unchanged. Stop before M1c.

## Built

- `pipeline/analyze_chapter.py` connects M1a imports to four sequential adapters: Magi detection, CPU geometry/order, Baberu crop OCR, CPU text metadata. Each heavy model unloads and clears CUDA before another loads.
- `pipeline/vision/{panels,order,crops,text}.py` validates geometry, computes exact union coverage, orders RTL/LTR panels with bounded page cuts, assigns text to panels and preserves provenance. Invalid boxes, coverage below 70%, substantial overlaps, ambiguous order and outside-panel text produce review reasons.
- `pipeline/adapters/ocr.py` uses the already verified English Baberu hybrid configuration: GPU vision, INT8 CPU decoding, four threads, 8 px crop padding. Whole-page crops are rejected before the OCR engine. No new detector fallback was justified on this sample; a missing panel list gets a flagged full-page geometry fallback.
- Stage caches depend on page hash, pinned adapter/config and relevant input hashes. Direction changes reuse detector/OCR inference. Malformed cache JSON and mismatched page/revision headers become misses. Completed analysis publishes atomically; failed runs retain the last complete chapter and resumable stage caches.
- Analysis artifacts remain separate from MotionScript. Text kinds stay `unknown`; binary essential hints and raw associations are retained for later classification/identity work. No voice, director, music, depth or reader feature is introduced in this slice.
- Read-only Windows power telemetry records AC/battery context for future comparisons.

## Model and runtime verification

Current official model cards, installed full Baberu README/license and pinned inference source were read before use. All four weight hashes matched `pipeline/model_manifest.json`. Exact source hashes, documentation links and D: install paths are in `pipeline/vision/DEPENDENCIES.md`.

| Component | Pin / configuration |
|---|---|
| Magi v3 | `c9d0a345b07be759be61c5cd9570ce2df73ee80b`; detection only, CUDA FP16 |
| Baberu OCR | `d9cc13153e9a1cd8fdfa3b7b1cc329da2020aeae`; ONNX GPU vision / CPU INT8 decoder |
| Runtime | Python 3.11.9; Torch 2.4.1+cu121; Transformers 4.45.2; ONNX Runtime GPU 1.20.2; Pillow 10.4.0; NumPy 1.26.4 |
| Machine | RTX 4050 Laptop, 6,141 MiB VRAM; driver 610.74; 15.65 GiB system RAM; native Windows |

No downloads, installs, dependency upgrades, cloud calls or credential changes were needed. Runtime/cache/temp paths remain on D:. Personal-use provenance is recorded: current Magi card permits personal/research/noncommercial use; Baberu records Apache-2.0.

## Acceptance evidence

Commands run from `D:\Motion Manga` after `. .\scripts\enter-runtime.ps1`:

```powershell
& .\.venv\Scripts\python.exe -m pipeline.analyze_chapter --series golden-m1b --chapter chapter --run-label cold
& .\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
& .\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_vision.py'
& .\.venv\Scripts\python.exe tests/verify_m1b_golden.py
& .\.venv\Scripts\python.exe -m pip check
git -c 'safe.directory=D:/Motion Manga' diff --check
```

Full suite: **40 tests in 27.039 s, OK**. After the final page-level OCR warning/revision update, the focused suite passed again: **9 tests in 4.093 s, OK**. `pip check`: **No broken requirements found**. `git diff --check`: no errors.

| Acceptance item | Evidence / result |
|---|---|
| Every supplied page has explicit order or review flag | Five real RTL pages, 25 explicitly ordered panels; zero order ambiguity flags on this set. Controlled tests cover LTR, interlocking layouts and missing panels. Real LTR/splash accuracy remains untested. |
| Panels and dialogue OCR evaluated against labels | One-to-one panel matching at IoU ≥0.5: 25 TP, 0 FP, 0 FN; precision/recall 100%. Complete-page order 5/5. Dialogue lexical WER 0 edits / 195 words across 35 dialogue crops, 0 missing crops. See reference limitations below. |
| Applicable subset meets ≥95% panel precision/recall, ≥97% complete order, ≤3% WER | All three thresholds met **on this provisional subset only**. This does not establish independent chapter accuracy or calibrated confidence. |
| OCR reads crops only | 53 detected text crops, 55 inference segments; padded/segmented boxes validated inside source images with full pixel coverage. Zero whole-page OCR calls. A fake-engine test additionally checks actual images passed to the engine and rejects a whole-page crop. |
| No OOM / one heavy model at a time | Both cold heavy stages completed with no error. Magi peak 2,145 MiB; Baberu baseline 121 MiB after Magi unloading, peak 393 MiB. Scheduler tests verify sequential lifecycle and release on failure. |
| Cache and original art integrity | Final warm replay: 20/20 stage-page hits with both heavy `load()` methods patched to fail if called; neither called. Exact analysis hash unchanged. All five originals and served copies match their baseline SHA-256. |
| PRD numeric confidence goal | **Open.** Both verified APIs omit calibrated confidence. Final output has five detector-unavailable flags, five OCR-unavailable flags and one outside-panel translator-note flag. D26 requires approval; no invented scores. |

Golden evaluator output summary:

```text
warm_cache_hits: [5, 5, 5, 5]
warm_seconds: 0.2891
original_and_served_hashes_unchanged: 5
text_crops: 53; inference_segments: 55; whole_page_ocr_calls: 0
sequential_heavy_stage_memory_checks: PASS
analysis_hash_unchanged: true
panel TP/FP/FN: 25/0/0; fully correct page order: 5/5
dialogue reference words / edits: 195 / 0
```

Private evidence: `reports/M1b-{cold,normalization-update,metadata-update,warm,quality,audit}.json`, `library/golden-m1b/reference.json`, and chapter `analysis.json` / per-page intermediates. These and the manga pages remain ignored by Git; transcripts are not included in this public report.

Final analysis SHA-256: `b4ef3362aec537604c0663c57ea9d48ea2f85fabab94cbe5847732fdd2c57ab8`.

## Measurements

Cold means empty application stage caches, not cold OS disk caches. Timers exclude Python startup. Device/process memory sampled every 0.2 s may miss brief peaks; these are observations, not maximum-memory guarantees. Device VRAM includes process CUDA context. Process RAM is sampled working set, unlike M1a's OS lifetime peak.

| Stage / observation | Page seconds, in supplied order | Mean s/page | Load / unload s | Device baseline / peak MiB | Process RAM peak MiB |
|---|---|---:|---:|---:|---:|
| Magi, initial cold | 5.6621, 3.4197, 3.1400, 2.5013, 2.9995 | 3.54452 | 36.0131 / 0.1395 | 0 / 2,145 | 2,804 |
| CPU geometry revision 1, initial cold | 0.0017, 0.0015, 0.0016, 0.0009, 0.0013 | 0.00140 | 0 / 0.1087 | 121 / 121 | 1,407 |
| Baberu, initial cold | 2.9117, 3.7127, 3.4893, 2.8222, 2.0349 | 2.99416 | 1.0862 / 0.1402 | 121 / 393 | 1,818 |
| CPU text revision 1, initial cold | 0.0012, 0.0009, 0.0009, 0.0009, 0.0010 | 0.00098 | 0 / 0.1002 | 123 / 123 | 1,675 |
| CPU geometry revision 2, separate cache-miss update | 0.2026, 0.0012, 0.0072, 0.0020, 0.0017 | 0.04294 | 0 / 0.0058 | 0 / 0 | 38 |
| CPU text revision 2, separate cache-miss update | 0.0012, 0.0011, 0.0008, 0.0012, 0.0010 | 0.00106 | 0 / 0.0075 | 0 / 0 | 47 |

The initial all-stage cold run took **72.6336 s for five pages**. Combined heavy inference averaged **6.53868 s/page**, so the PRD ≤3 s detect+OCR target is **unmet in this run**. Peak Torch allocation/reservation was 1,909/2,042 MiB during Magi and 8/18 MiB during Baberu; Baberu ONNX memory is captured by device sampling rather than Torch accounting. CPU stages allocate no model; their initial 121–123 MiB device reading reflects remaining CUDA context.

After cold verification, a whole-page crop guard changed geometry revision 1→2 and explicit OCR warnings changed text revision 1→2. Only CPU-dependent caches were recomputed: geometry update elapsed 1.3957 s; final text update 2.1139 s. Existing heavy outputs were reused. The final revision's fully warm replay took **0.2891 s**, with 20/20 hits and no model loads. Warm memory sampling was skipped and peaks are `null`, not measured zero.

Earlier M0 optimization observed 2.8480 s/page combined inference and 26.7928 s total. Current model/runtime/settings remain the same, but current inference and Magi loading are slower. Windows reported AC offline **after** the cold run and during later CPU/warm runs. Power telemetry was added afterward; cold power conditions and the cause of this regression are not isolated. Retain both observations. A matched plugged-in benchmark is future diagnostic work, not a proven fix or a hardware upgrade requirement.

Page union coverage: 88.75%, 93.30%, 85.22%, 93.22%, 74.80%. No coverage-under-70% flags on this set; controlled tests exercise that gate.

## Reference limitations, deviations and remaining risks

- Panel boxes/order are provisional engineer visual annotations made after prior detector coordinates had been seen. They are **not blind or independently user-confirmed**. OCR references were visually transcribed before inspecting Baberu predictions, but the sample has already been used for crop tuning. These five mixed-series pages do not establish accuracy on unseen chapters.
- WER counts normalized lexical words, retaining apostrophes and excluding other punctuation differences. It covers labeled dialogue crops; SFX, captions, notes and full-page text-detection recall are separate concerns. No numerical confidence calibration is claimed.
- D26 proposes `null` confidence with explicit review flags until an independent calibration set exists. Approval is needed to close this PRD §2 exception. No change to §2 or MotionScript v1 was made.
- Magi's public detector method does not perform the upstream transcript sorter. The bounded local order solver and review flags are documented in D27. No separate fallback model was introduced without a demonstrated failure. Text class/identity and a review UI remain later work.
- OCR uses the previously authorized D19 hybrid route and published single-crop calls, not an invented batched GPU decoder or simultaneous heavy-model stages. Cache reuse reduces repeat work; current cold speed still misses the target.
- Real LTR, borderless/splash pages, Japanese/Chinese OCR, continuous-story evaluation, phone behavior and longer chapter memory/time require additional material at their relevant milestones.
- Final character depth, semantic SFX, tonal music, mobile Flow and uncapped reading-aware Auto remain planned requirements. This slice prepares metadata/cache foundations; it does not demonstrate those outcomes.

## Approval gate

Approve D26's confidence exception and this milestone before M1c starts: keep confidence unavailable with explicit review reasons, and defer calibrated numeric scores to an independent labeled validation set. No M1c work has started.

## Commits

- `b8fa919` — Connect imported chapters to ordered panels and crop OCR: adapters, cache/scheduler changes, focused tests and verified dependency notes.
- Separate documentation commit — Record M1b measurements and pending confidence exception: this report, PRD observations, decisions and milestone gates. Private manga/model/cache artifacts are excluded.

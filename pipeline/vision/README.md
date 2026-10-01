# M1b chapter analysis

Analyze an M1a-imported English chapter:

```powershell
. .\scripts\enter-runtime.ps1
& .\.venv\Scripts\python.exe -m pipeline.analyze_chapter --series my-series --chapter ch01 --run-label cold
```

Pipeline: Magi detection -> unload/clear -> CPU geometry/order -> Baberu detected-crop OCR -> unload/clear -> CPU text metadata. Defaults retain measured CUDA FP16 vision, INT8 CPU decoder and four threads. `--vision-device cpu` and `--threads 1|2|4|8` remain explicit options. Other source languages fail before model loading until separately evaluated; no automatic model substitution occurs.

Each unique page hash is analyzed once, even if repeated in the chapter. Page-stage keys include revision/config and relevant dependency hashes. Direction changes rerun order/metadata while retaining identical detector/OCR results. Changed text geometry invalidates OCR. Cache JSON must be an object with matching page hash/revision; malformed or mismatched records are misses. Model timers and caller filenames do not determine semantic cache identity.

Outputs stay under `library/<series>/<chapter>`:

- `cache/stages/<stage>/<key>.json`: resumable scheduler caches.
- `cache/pages/<page-sha>/{detections,geometry,ocr,text-metadata}.json`: per-page model/normalized artifacts.
- `cache/{detections,ocr}.json`: aggregated intermediate indexes.
- `analysis.json`: atomic complete chapter result, separate from MotionScript.
- `cache/analysis-last-failure.json`: named stage failure and measurements; last completed `analysis.json` is retained.
- `reports/M1b-<run-label>.json`: ignored private metrics, including current power context.

Bounding boxes are page coordinates. Invalid/nonfinite boxes are flagged; only <=2 px detector edge roundoff is clamped. A missing detector panel list becomes one full-page **fallback with a review flag**, never counted as a correct model detection. Exact rectangle-union coverage avoids double-counting overlaps; <70% coverage and substantial panel overlap are flagged. A text detection whose padded crop spans the entire page is rejected/flagged before OCR. Original sources and serving images are rehashed; no image pixels are changed.

Ordering recursively splits horizontal bands, then RTL/LTR columns, using 2% internal erosion solely to tolerate overlapping detector borders. Returned boxes are unchanged. Unsplit interlocking layouts receive a deterministic provisional order **and a review flag**. Real five-page tests are RTL; controlled LTR tests establish algorithm behavior, not accuracy on real LTR manga.

Text retains OCR provenance, original detection index, crop/segment boxes, raw text, normalized whitespace/NFC text, panel assignment and essential-model hints. Binary essential flags are not semantic dialogue/SFX labels. Text `kind` remains `unknown`; translator notes outside panel bounds are review items, not automatically counted as reading candidates. Speaker associations remain raw provenance; character identity/voices are deferred.

Confidence remains `null`/uncalibrated because the verified public inference APIs do not provide calibrated probabilities. Page-level detector/OCR warnings are explicit; this is **not numerical confidence calibration**. The user approved D26's documented exception when authorizing M1c. Numeric calibration remains deferred. Quality scores against supplied labels are separate from per-item confidence.

Quality evaluation uses maximum-cardinality one-to-one panel matching at a declared IoU threshold, complete-page order equality, and dialogue lexical WER. Fallback panels do not score as successful detections. Missing dialogue crops count as deletions. Metrics explicitly disclose reference method, unlabeled crop count and the fact that crop WER does not measure full-page text-detection recall.

Verification:

```powershell
. .\scripts\enter-runtime.ps1
& .\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
& .\.venv\Scripts\python.exe tests/verify_m1b_golden.py
```

The golden evaluator needs ignored `library/golden-m1b/reference.json` and the supplied original pages. Visual panel labels are provisional engineer annotations made after prior detector boxes had been seen. OCR labels were visually transcribed before viewing Baberu predictions, but are not independently user-confirmed. Do not present the small tuned set as independent/general accuracy or confidence calibration.

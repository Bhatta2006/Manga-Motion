# M0a optimization follow-up — complete

Authorized by the user on 2026-10-01: hardware upgrades are unavailable; proceed with optimal implementation strategies. Scope is remediation of measured English OCR failures and efficiency on the existing five-page set. M0b playback/voices and later product features remain behind their milestone gates.

## Verification before first use

- Baberu: [current official model card](https://huggingface.co/genshiai-daichi/baberu-ocr) and full README, license, inference source, ONNX source, config and quantization report read on 2026-10-01. Current immutable revision: `d9cc13153e9a1cd8fdfa3b7b1cc329da2020aeae`. Apache-2.0. Pin the author's FP16 vision + INT8 decoder release, 241,979,934 bytes of ONNX weights. This is disk size, not RAM or VRAM. CPU-only inference measured 0 MiB sampled device usage. Final selected GPU-vision/CPU-decoder stage measured 395 MiB device peak; see the results below.
- Source review is saved under `.runtime/model-review/baberu-d9cc13153e9a`. Files downloaded on D before any code execution. Only reviewed self-contained `onnx_infer.py` will be imported; do not execute training scripts.
- The Torch config names Transformers 5.5.3. Use the author's self-contained ONNX route to preserve Magi's verified Transformers 4.45.2 environment.
- [ONNX Runtime thread documentation](https://onnxruntime.ai/docs/performance/tune-performance/threading.html) checked. Pin CPU `onnxruntime==1.23.2`, MIT, Python >=3.10; official PyPI metadata confirms CPython 3.11 Windows x64 wheel, 13,468,349 bytes, SHA-256 `902c756d8b633ce0dedd889b7c08459433fbcf35e9c38d1c03ddc020f0648c6e`. Dependency dry run saved on D. Exact transitive pins were specified during installation and are recorded in `pipeline/requirements.lock`. The CPU distribution was later replaced by the verified GPU distribution below.
- All packages and model snapshots use the existing D-only virtual environment and cache script. Expected model location: `.runtime/cache/huggingface/hub/models--genshiai-daichi--baberu-ocr/snapshots/<revision>`.
- Author's public ONNX API: `BaberuOnnxOCR(onnx_dir, tokenizer_dir, vision)` and `__call__(image, max_new_tokens=128, repetition_penalty=1.2, max_content_run=12)`. Preprocessing preserves the full crop during inference resize, rather than center-cropping. Decoding is greedy with a KV cache and content-only repetition guard. This resize applies to an in-memory OCR input, never stored source art.

## Acceptance for this follow-up

- Compare specialist OCR against the existing Magi outputs on the exact same 53 detected crops; retain sources and detection evidence.
- Record manually transcribed private reference labels and reproducible English error metrics; distinguish dialogue from notes, SFX, signs and watermarks.
- Measure page latency, load/unload, sampled VRAM/RAM, and cache replay; choose a tested thread/provider configuration. No claim of a global optimum.
- Cache by source/detection/model/config version; keep one model at a time and unload at stage boundaries.
- Test failure cleanup, invalidation, input/crop integrity and unchanged source hashes. Flag empty/truncated/unsupported-confidence results.
- Commit changes and finish this report, then stop. Do not start M0b.

## CUDA comparison verification before installation

Official ORT CUDA compatibility table lists 1.20.x with CUDA 12.x/cuDNN 9, compatible with PyTorch >=2.4.0. The existing D-drive torch 2.4.1+cu121 supplies these DLLs. Newer ORT 1.21+ builds require CUDA 12.8 per current docs; do not download a toolkit. The attempted 1.20.1 metadata endpoint returned HTTP 404 on this run; release enumeration confirmed 1.20.2, which was verified and pinned instead. Official PyPI metadata: MIT, Windows CPython 3.11 GPU wheel 279,697,437 bytes, SHA-256 d0eafd873e4336949c89e6c7429a68e7e1d0233d9cb363e9780ca76c3c6f865c. Its exact dependency plan reuses the installed pins. ONNX vision file starts with IR version 8. GPU comparison uses only the vision session on CUDA, INT8 decoder sessions on CPU, a 512 MiB CUDA arena limit (not a total GPU cap), and fails explicitly if the CUDA provider cannot initialize. Only one ORT distribution may be installed.

## Implemented changes

- `pipeline/adapters/baberu.py` wraps the pinned author's ONNX inference code. FP16 vision runs on the GPU; both INT8 decoder graphs run on CPU with four threads, idle spinning disabled, greedy generation, and the published repetition guards. CUDA initialization failure is explicit. CPU vision remains selectable.
- `pipeline/m0_detect.py` now runs Magi **detection only**, unloads it and clears CUDA, then loads Baberu for the five pages, and unloads again. The original Magi OCR route remains available through its adapter for baseline comparison. Each model loads once per stage, not once per crop.
- Tall English crops (height > twice width, height >=150 pixels) split once near the middle only if a three-row blank gap exists in the inner text area. Segments cover the entire original crop without dropped or duplicated rows. The author's 224×224 inference resize remains in memory. No source art file is rewritten. This fixed the long truncated dialogue in page 1.
- Specialist output includes per-crop text, segment coordinates, timing, explicit unverified/empty/token-limit states and `null` unsupported confidence. A nonempty string is not a confidence score.
- Cache identity includes original source SHA-256, model revision, adapter/runtime/settings and a canonical hash of the upstream text boxes. A changed page's text boxes invalidate only its OCR. Source mutation during inference fails before storing output.
- Scheduler now resets PyTorch allocator peaks at stage boundaries and records stage elapsed time. ONNX allocations are tracked by sampled device usage, not the PyTorch allocator.
- Added private reference scoring and integrated artifact audit. Private text, page bytes and model files remain excluded from Git.

## Quality comparison on the supplied five pages

References were visually transcribed from the source crop sheets before inspecting Baberu predictions. References have 35 dialogue crops (195 lexical words), nine caption crops, three nonverbal crops, three SFX crops, a watermark, a translator note, and a sign. Engineer labels are not independently verified by the user. Metric normalization: Unicode NFKC, case folding, punctuation ignored except apostrophes inside words, whitespace/newline tokenization. Word error rate is summed Levenshtein word edits divided by summed reference words, with no cross-crop alignment.

| Route | Nonempty / all 53 crops | Dialogue WER | Dialogue + caption WER | Lexically exact dialogue crops |
|---|---:|---:|---:|---:|
| Original Magi crop OCR | 14 / 53 | 77 / 195 = **39.49%** | 126 / 244 = **51.64%** | 10 / 35 |
| Baberu CPU, whole crops (ORT 1.23.2) | 53 / 53 | 4 / 195 = **2.05%** | 10 / 244 = **4.10%** | 34 / 35 |
| Baberu CPU, tall splitting (ORT 1.23.2) | 53 / 53 | 0 / 195 = **0%** | 6 / 244 = **2.46%** | 35 / 35 |
| Baberu CPU, tall splitting (ORT 1.20.2) | 53 / 53 | 0 / 195 = **0%** | 5 / 244 = **2.05%** | 35 / 35 |
| Final integrated GPU vision / CPU decoder (ORT 1.20.2) | 53 / 53 | 0 / 195 = **0%** | 6 / 244 = **2.46%** | 35 / 35 |

The selected route recovered all scored dialogue words on this small set. **This does not establish perfect OCR or the general M1 ≤3% WER gate.** Punctuation differences are excluded; splitting was tuned after observing a failure in these same five pages, so this is an exploratory comparison, not a held-out benchmark. Detection recall is outside this metric. No text corrections or reference-label substitution are applied to predictions.

Remaining lexical errors occur in four stylized captions on page 2, two SFX crops on page 1, and the watermark on page 4. CPU and CUDA vision differ on one caption word; CPU has slightly better caption WER here but is substantially slower. The GPU route is selected for dialogue processing and efficiency; captions remain explicitly unverified. All nonverbal/SFX/note/sign/watermark handling still needs the PRD's later text classification. There is no automatic narration or fabricated confidence in this follow-up.

## Configuration measurements

Same source bytes, same 53 text boxes, 8 px crop padding. Baberu cap increased from the author's default 128 to 256 character tokens to avoid a configured short output limit. No weights are trained or changed. CPU thread count is bounded, not unlimited. Measurements are single comparative runs on the i5-13420H / RTX 4050, subject to load and thermal variation.

| OCR-only configuration | Mean page run | Load / unload | Sampled device peak | Process RAM peak |
|---|---:|---:|---:|---:|
| CPU ORT 1.23.2, 1 thread, whole crops | 6.0273 s | 1.5081 / 0.0479 s | 0 MiB | 943 MiB |
| CPU ORT 1.23.2, 4 threads, whole crops | 2.7457 s | 1.5821 / 0.0478 s | 0 MiB | 920 MiB |
| CPU ORT 1.23.2, 4 threads, tall splitting | 2.6751 s | 1.2897 / 0.0462 s | 0 MiB | 924 MiB |
| CPU ORT 1.20.2, 4 threads, tall splitting | 3.2255 s | 0.7213 / 0.0490 s | 0 MiB | 1,051 MiB |
| GPU vision ORT 1.20.2, 4 CPU decoder threads, tall splitting | 1.0537 s | 3.4339 / 0.0757 s | 355 MiB | 1,110 MiB |

CPU baseline is useful if CUDA is unavailable, but GPU vision + CPU decoding is the measured choice for this machine. No 2/8-thread or decoder-GPU optimum is claimed; further tuning is deferred because the observed route already removes the concrete quality failure and substantially lowers latency within the hardware budget. No additional CUDA toolkit or external API was used.

## Final integrated cold and warm measurements

Cold means a fresh stage-result cache in `library/golden-opt-final`, with model files already local and the OS file cache warmed. It excludes downloads and does not claim cold disk performance.

| Page | Magi detection | Baberu OCR | Combined page run |
|---|---:|---:|---:|
| 1 | 2.6509 s | 1.1406 s | 3.7915 s |
| 2 | 1.5661 s | 1.3294 s | 2.8955 s |
| 3 | 1.5286 s | 1.3165 s | 2.8451 s |
| 4 | 1.2583 s | 1.1219 s | 2.3802 s |
| 5 | 1.4828 s | 0.8448 s | 2.3276 s |
| Mean | 1.6973 s | 1.1506 s | **2.8480 s** |

Baseline mean was 4.3879 s/page. Final mean is **35.1% lower**; the earlier integrated run was 2.7763 s/page. Four of five final pages meet ≤3 s inference, page 1 does not. Full five-page pipeline is **26.7928 s including load/unload and instrumented stage I/O** (~5.36 s/page amortized), measured inside the Python runner; interpreter startup is outside that timer. Therefore the ≤3 s goal is not claimed for end-to-end processing including loads.

| Stage | Load | Unload + cleanup | Device baseline → peak | Process RAM peak | Torch allocated / reserved peak |
|---|---:|---:|---:|---:|---:|
| Magi detection | 10.0231 s | 0.1026 s | 0 → **2,145 MiB** | 2,671 MiB | 1,909 / 2,042 MiB |
| Baberu OCR after Magi unload | 0.4340 s | 0.1022 s | 121 → **395 MiB** | 1,815 MiB | 8 / 18 MiB |

OCR's 121 MiB baseline reflects residual CUDA/runtime context after Magi, not a second resident heavy model. Magi model references are released and CUDA cache cleared before OCR loads. Peak reset prevents the preceding Torch stage from contaminating the next allocator metric. Device sampling every 0.2 seconds can miss brief peaks; ORT memory is not represented by Torch allocator counters. Sampled device values include other processes. No OOM occurred.

Final warm replay: **5/5 detection + 5/5 OCR cache hits**, no model loads, no inference, runner elapsed **0.7676 s**. Both stages retain the exact source hashes. The first attempted replay exposed a bug: JSON key ordering changed detection-file byte hashes and reran OCR. The fix hashes canonical OCR inputs (detector revision + ordered text boxes), independently of export formatting. A regression test proves formatting/unrelated panel changes do not invalidate OCR, while text-box changes do. Earlier failure records are preserved in ignored private reports.

## Acceptance evidence and reproducible commands

Run from `D:\Motion Manga`, first dot-source the runtime script. Exact pages are listed in `reports/M0a.md`. The integration command run twice with `--run-label cold` then `--run-label warm`:

```powershell
. .\scripts\enter-runtime.ps1
& '.\.venv\Scripts\python.exe' -m pipeline.m0_detect --chapter golden-opt-final --run-label cold `
  'library/incoming/5LYzTBVoS196gvYvw3zjwLMiUQTmoGgNMIlLgJBfye8.jpg' `
  'library/incoming/dede2a66b7b6581533631087558b682b.jpg' `
  'library/incoming/english.jpg' `
  'library/incoming/never-set-foot-jean-karlo.png.jpg' `
  'library/incoming/ttkxwb26bt9e1.jpg'
& '.\.venv\Scripts\python.exe' '.\tests\verify_ocr_pipeline.py'
& '.\.venv\Scripts\python.exe' '.\tests\evaluate_m0a_ocr.py' --chapter golden-opt-final --candidate ocr.json --label pipeline-final
& '.\.venv\Scripts\python.exe' -m unittest discover -s tests -v
& '.\.venv\Scripts\python.exe' -m pip check
```

Observed final outputs:

```text
Cold: detection cache_hits 0; OCR cache_hits 0; error null
Warm: detection cache_hits 5; OCR cache_hits 5; loads 0; error null
Artifact audit: PASS; sources_unchanged 5; crops 53; inference_segments 55
Quality: dialogue 0/195 word edits; dialogue+caption 6/244
Ran 13 tests in 4.628s — OK
No broken requirements found.
Post-inference nvidia-smi used/free: 0, 5920 MiB
```

Comparative OCR CLI: `python -m pipeline.ocr_benchmark --threads 4 --vision-device cuda --run-label <label>`; `--vision-device cpu` selects CPU, `--no-split-tall` selects whole crops. Original comparison runs used the pinned revisions/runtime versions listed above. Preparation command: `python -m pipeline.prepare_baberu`, verified all three ONNX sizes and SHA-256 hashes. Exact hashes/versions are in `pipeline/model_manifest.json` and `pipeline/requirements.lock`.

| Acceptance item | Evidence | Status |
|---|---|---|
| Verified pinned specialist behind adapter, D-only downloads | Source review above; checksum preparation; exact dependency lock; D cache script | PASS |
| Compare same 53 crops to source references | Saved private reference before specialist output review, scoring script and tables | PASS; small exploratory set only |
| Measure quality, latency, memory and replay | Cold/warm stage JSON, quality reports, per-crop timing, configuration tables | PASS |
| One model at a time, load/unload/cleanup | Sequential scheduler calls, lifecycle and thread/process lock tests, OCR baseline well below Magi footprint | PASS |
| Input/version/config cache and source integrity | Canonical box hash + page SHA, page-specific invalidation test, source mutation failure test, artifact audit | PASS |
| Errors explicit, confidence honest | Output status fields, token cap checks, confidence null; no automatic narration | PASS; confidence calibration deferred |
| Small commits and report | Code commits below; report committed separately | PASS |

Private evidence: `reports/M0a-opt-*.json`, `library/golden-m0/ocr-reference.json`, `library/golden-opt-final/{ocr-reference.json,cache/...}`, `.runtime/baberu-verification.json`. Original baseline remains preserved under `library/golden-m0`. Sources remain in `library/incoming` and are ignored by Git.

## Deviations, remaining limits, and gate

- User authorized this focused optimization before M0b; specialist OCR evaluation originally scheduled for M1 was brought forward only to remediate M0a's demonstrated failure. No reader, voices, classification UI or MotionScript change was introduced.
- English uses hybrid GPU/CPU inference instead of full GPU batched OCR. The official fixed-batch ONNX inference runs crops sequentially with cached decoder state; measured speed/memory justify this choice on the target laptop. No heavy model overlap.
- Tall splitting is English-focused and untested on Japanese vertical text. Do not apply it as an unverified JP default. Higher-resolution pages, full chapters and other languages require new measurements.
- All text remains unverified; style/SFX/caption errors and punctuation differences remain. Token-limit length is a warning heuristic, not calibrated confidence or a guarantee against early EOS truncation.
- The five pages are used for implementation tuning and evaluation; obtain fresh pages for an independent quality gate. No general accuracy guarantee or completed M1 claim.
- First-page latency and full processing including loads exceed 3 s/page. More than one heavy model was never resident to hide load cost. Reader/audio milestones are not started.
- Keep original art immutable; in-memory crop resizing does not change source files. No cloud call, API key, CUDA toolkit install or C-drive download occurred.

Code commits: `8bd7258` (pinned Baberu adapter/runtime) and `e2a0c9b` (staged integration, cache fixes, audits and tests).

**This follow-up is complete. Stop for the user's approval before M0b.**

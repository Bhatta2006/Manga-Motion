# M0a report — feasibility checks complete

Measured on 2026-10-01. All M0a engineering acceptance checks passed on five real supplied pages. This establishes local detection/OCR execution and caching on the 4050; **OCR quality is poor and is not accepted for narration**. M0b has not started. Stop for user approval.

## Source and environment verification

| Item | Verified evidence | Pinned / path / status |
|---|---|---|
| GPU | `nvidia-smi` on 2026-09-30: RTX 4050 Laptop, 6,141 MiB total, 5,920 MiB free, driver 610.74, CUDA driver API 13.3 | Baseline only, not model peak |
| Python | [Python Windows documentation](https://docs.python.org/3.11/using/windows.html#the-nuget-org-packages) describes the portable NuGet package; [NuGet package page](https://www.nuget.org/packages/python/3.11.9) lists 3.11.9 | Package SHA-256 `9283876D58C017E0E846F95B490DA3BCA0FC0A6EE1134B2870677CFB7EEC3C67`; runtime `.runtime/python-package/tools/python.exe`, venv `.venv`, both on D: |
| Magi v3 model | [Official model card](https://huggingface.co/ragavsachdeva/magiv3) and [author's README](https://github.com/ragavsachdeva/magi) checked; model card states personal use is permitted, repo README has older academic-only wording; user confirmed personal project | Revision `c9d0a345b07be759be61c5cd9570ce2df73ee80b`; weights 1.67 GB on disk per model file listing; five-page inference peak **2,145 MiB** (diagnostic batch peak 2,415 MiB) |
| Magi v3 API | [Pinned model source](https://huggingface.co/ragavsachdeva/magiv3/blob/c9d0a345b07be759be61c5cd9570ce2df73ee80b/modeling_florence2.py) defines `predict_detections_and_associations(images, processor)` and `predict_ocr(images, processor)` | Detection yields panels/texts/characters/tails and thresholded associations. OCR has text/boxes, no confidence score in these public methods. Adapter records `null` instead of inventing scores. |
| Transformers | Pinned Magi `config.json` and `generation_config.json` both name 4.45.2 | Installed `transformers==4.45.2`; pinned custom config loads as `florence2` |
| PyTorch | [Official previous versions page](https://pytorch.org/get-started/previous-versions/) lists PyTorch 2.4.1 with CUDA 12.1 wheels for Windows | Installed `torch==2.4.1+cu121` and `torchvision==0.19.1+cu121`; CUDA available and RTX 4050 detected |
| Install/cache route | `scripts/enter-runtime.ps1` points `TEMP`, `TMP`, pip, Hugging Face, Torch, npm, and Python bytecode caches into `.runtime` on D: | No project download or cache is intentionally directed to C:. Files under `.runtime`, `.venv`, `library` are ignored by Git. |

## What was built

- D-only portable Python 3.11.9, virtual environment, complete exact dependency lock, process cache/temp routing, ignored private library and model files.
- Swappable Magi adapter and one-heavy-model scheduler with an OS file lock across threads/processes, error-safe unload, CUDA synchronization/cache release, sampled device VRAM and process RAM.
- SHA-256 stage cache keyed by source bytes, model revision, and config. Five-page CLI exports detection and OCR JSON, with unavailable confidence explicitly `null`.
- Empty OCR is marked `empty_needs_review`; nonempty text is marked `text_returned_unverified`. Neither is silently treated as correct. Invalid chapter names are rejected before writing library output.
- Golden artifact audit checks source hashes, JSON/box validity, crop bounds, output consistency, and five warm cache hits.
- Source art was only read. Review overlays were saved as separate private PNGs; originals retain their pre-inference SHA-256 hashes.

## Input set and manual inspection

`library/incoming` contains six files. The following five decodable images were used as independent English/RTL samples, in filename order for the benchmark. These are mixed-series pages, **not a continuous five-page chapter**. The extra `Page-129.jpg` has an AVIF header despite its extension; pinned Pillow 10.4.0 cannot decode it. It was preserved and excluded, without installing another codec or changing it.

| Page / filename | Pixels | Source bytes | Visible / detected panels | Detected text crops | Crops returning text |
|---|---:|---:|---:|---:|---:|
| 1 / `5LYzTBVoS196gvYvw3zjwLMiUQTmoGgNMIlLgJBfye8.jpg` | 1066 × 1600 | 301,121 | 7 / 7 | 13 | 2 |
| 2 / `dede2a66b7b6581533631087558b682b.jpg` | 736 × 1040 | 230,632 | 5 / 5 | 11 | 2 |
| 3 / `english.jpg` | 831 × 1170 | 142,380 | 5 / 5 | 12 | 5 |
| 4 / `never-set-foot-jean-karlo.png.jpg` | 492 × 600 | 85,358 | 3 / 3 | 10 | 4 |
| 5 / `ttkxwb26bt9e1.jpg` | 1080 × 1428 | 208,540 | 5 / 5 | 7 | 1 |

All five source pages and their panel/text overlays were visually inspected. Panel counts match the 25 visible panels. This is a manual count comparison, **not** a labeled IoU or coverage benchmark. Page 1 has a shared bubble crossing the bottom panel boundary; page 4 has a bubble extending above the detected right-panel rectangle. Later camera framing must include active bubbles rather than rely only on panel rectangles.

Text detection broadly follows visible text. It also detects SFX, a watermark (page 4), and a translator note/sign (page 5); these must not automatically become dialogue. Character/speaker correctness and reading order were not graded in M0a.

Only **14/53 crops (26.4%)** returned any OCR text; **39/53 (73.6%)** were empty. This rate is not accuracy. Manual comparison also found misspellings, wrong names, and truncated lines in nonempty OCR. No EN WER/CER claim is made without full dialogue transcription. A two-crop diagnostic captured the raw generated tokens for clear failed crops: both consisted only of start/end tokens, and the processor parsed empty strings. The empties originate in model generation, not discarded adapter text.

## Real-page measurements

Cold means empty **stage output cache**, with the already downloaded model snapshot and warmed OS file cache. It does not mean a fresh model download or cold disk cache.

| Page | Detection | Crop OCR | Whole page run |
|---|---:|---:|---:|
| 1 | 3.3946 s | 3.0061 s | 6.4226 s |
| 2 | 1.5996 s | 2.6348 s | 4.2454 s |
| 3 | 1.4999 s | 3.0901 s | 4.5971 s |
| 4 | 1.2160 s | 2.5060 s | 3.7261 s |
| 5 | 1.4668 s | 1.4718 s | 2.9481 s |
| Mean | 1.8354 s | 2.5418 s | **4.3879 s** |

One combined Magi stage owns detection and OCR; it holds the same model for all five pages, then unloads. Crop OCR runs serially to bound memory. Whole-page run includes image decode/adapter work; scheduler cache write and model load are separate.

| Stage/run | Load | Unload + CUDA cleanup | Device baseline → sampled peak | Torch allocated / reserved peak | Process RAM baseline → sampled peak |
|---|---:|---:|---:|---:|---:|
| Five-page Magi detection + OCR | 16.6212 s | 0.1158 s | 0 → **2,145 MiB** | 1,909 / 2,042 MiB | 19 → 2,781 MiB |
| Two-crop OCR diagnostic, batch of 2 | 11.5794 s | 0.1042 s | 0 → **2,415 MiB** | 2,216 / 2,312 MiB | 33 → 2,774 MiB |
| Five-page cache replay | 0 s | 0 s | Not sampled; no model loaded | Not applicable | Not sampled |

Diagnostic run time was 0.7950 s for two crops (not a full-page rate). Both inference runs completed without OOM. Post-run `nvidia-smi` reported `0, 5920` MiB used/free. Device measurements sample every 0.2 s and can miss brief spikes; PyTorch allocator peaks supplement them. Device usage includes other GPU processes. Peaks cover loading/inference/unloading and do not isolate each crop or detection call.

Five-page inference sum: 21.9393 s. Load + page runs + unload sum: 38.6763 s, excluding scheduler/CLI I/O overhead. Warm replay: 5/5 hits, zero inference seconds, zero model loads. No total CLI wall-time claim is made.

The measured 4.3879 s/page replaces the PRD's ≤3 s estimate **for this configuration and sample set**; four of five pages exceed that target. The 2,145 MiB measured peak replaces the estimated 2–3 GB for this five-page run only. Higher resolutions, other pages, batching, or dependency changes require new measurements.

## Acceptance evidence

Commands below were run from `D:\Motion Manga` after `. .\scripts\enter-runtime.ps1`.

```powershell
& '.\.venv\Scripts\python.exe' -m pipeline.m0_detect --chapter golden-m0 `
  'library/incoming/5LYzTBVoS196gvYvw3zjwLMiUQTmoGgNMIlLgJBfye8.jpg' `
  'library/incoming/dede2a66b7b6581533631087558b682b.jpg' `
  'library/incoming/english.jpg' `
  'library/incoming/never-set-foot-jean-karlo.png.jpg' `
  'library/incoming/ttkxwb26bt9e1.jpg'
```

Cold output: `pages_total: 5`, `cache_hits: 0`, `error: null`, `device_vram_peak_mib: 2145`. Saved as `reports/M0a-cold-metrics.json`. Exact same command replay: `cache_hits: 5`, `load_seconds: 0.0`, `unload_seconds: 0.0`, all five `run_seconds: 0.0`, `error: null`; saved as `reports/M0a-warm-metrics.json`.

```powershell
& '.\.venv\Scripts\python.exe' -m unittest discover -s tests -v
& '.\.venv\Scripts\python.exe' '.\tests\verify_m0a_golden.py'
& '.\.venv\Scripts\python.exe' -m pip check
nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader,nounits
```

Observed output:

```text
Ran 7 tests in 3.973s — OK
Golden audit: checks PASS; source_hashes_unchanged 5; cache_replay_hits 5
No broken requirements found.
0, 5920
```

| M0a acceptance item | Evidence / result |
|---|---|
| Official docs, license, revision, expected/measured memory recorded | Source table above; pre-download source review, pinned weight verification; measured peaks now recorded. PASS. |
| Project installs, downloads, temp and caches on D | Runtime script validates D paths; model/venv/lock/cache locations recorded above. No new dependency was downloaded during this benchmark. PASS. |
| Five pages produce panel/text/OCR JSON, confidence or explicit unsupported field | Five `cache/pNNN-<hash12>/{detections,ocr}.json` exports; confidence `null`; empty/unverified states; golden audit PASS. Execution passes, OCR accuracy remains poor. |
| No two heavy models overlap | Thread and two-process lock tests, unload-on-error test, one model in actual run. PASS. |
| Cold and warm complete without OOM | Both CLI runs exit 0, error null, 0/5 then 5/5 cache hits. PASS. |
| Peak memory and seconds/page for stages invoked | Combined Magi and OCR diagnostic tables above; timing fields from private stage cache. PASS. |
| Source untouched and JSON/crop integrity | Golden audit recomputes source hashes against cold pre-inference hashes, checks all coordinates and JSON/cache consistency. 5/5 unchanged. PASS. |

Private evidence is ignored by Git: `reports/M0a-{cold-metrics,warm-metrics,golden-audit,ocr-diagnostic}.json`, `library/golden-m0/cache/stage/magiv3/*.json`, exported page JSON, and `review-overlay.png` files. Full hashes, dimensions, timing breakdown and source sizes are in the golden audit. Model preparation evidence remains `.runtime/magiv3-verification.json`.

## Deviations and remaining risks

- Confidence is unsupported by pinned Magi public methods, so `null` is retained (D17). No confidence-gated product feature or MotionScript change was introduced.
- Serial crop OCR instead of batching is intentional for M0a memory feasibility; combined detection + OCR runs within one model stage. There is no detection/OCR model overlap.
- Magi alone is not a usable English crop OCR route on these samples. The PRD already plans specialist English OCR; retain that evaluation for M1. Do not voice erroneous or empty lines as accepted text. No extra model or cloud fallback was introduced into M0a.
- All five samples are English; Japanese OCR and continuous chapter identity/order are untested. The extra mislabeled AVIF is an import-format case for M1.
- Panel count agreement does not prove safe bubble framing or speaker attribution. The shared/overflow bubbles and watermark/note cases are recorded for later milestones.
- Transformers 4.45.2 is pinned. Its warning about generation changes in 4.50+ is outside this lockfile; upgrades need verification. Windows lacks compiled flash attention in this Torch build.
- Device peaks are sampled, not an absolute bound. Only one real five-page inference run was measured; no repeatability confidence interval or larger-page fit claim.
- Scheduler/telemetry live together in `pipeline/runtime/scheduler.py`; a separate `metrics.py` is unnecessary for this slice.
- Git requires per-command `-c 'safe.directory=D:/Motion Manga'` because sandbox/user ownership differs. No global Git config on C was changed.

## Commits and gate

Earlier setup commits: `100c553`, `94a7741`, `fa3e495`, `4321ae0`. Real-output validation and failure flags: `97ec1c6`.

M0a engineering feasibility is complete. **Stop here. M0b requires the user's “approved.”** OCR quality must remain visible as a limitation in any later prototype.

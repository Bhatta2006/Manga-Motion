# M0a report — in progress

This report is deliberately incomplete until five real user-provided pages are processed and acceptance checks are measured. No page quality, runtime VRAM, or seconds-per-page result is claimed yet.

## Source and environment verification

| Item | Verified evidence | Pinned / path / status |
|---|---|---|
| GPU | `nvidia-smi` on 2026-09-30: RTX 4050 Laptop, 6,141 MiB total, 5,920 MiB free, driver 610.74, CUDA driver API 13.3 | Baseline only, not model peak |
| Python | [Python Windows documentation](https://docs.python.org/3.11/using/windows.html#the-nuget-org-packages) describes the portable NuGet package; [NuGet package page](https://www.nuget.org/packages/python/3.11.9) lists 3.11.9 | Package SHA-256 `9283876D58C017E0E846F95B490DA3BCA0FC0A6EE1134B2870677CFB7EEC3C67`; runtime `.runtime/python-package/tools/python.exe`, venv `.venv`, both on D: |
| Magi v3 model | [Official model card](https://huggingface.co/ragavsachdeva/magiv3) and [author's README](https://github.com/ragavsachdeva/magi) checked; model card states personal use is permitted, repo README has older academic-only wording; user confirmed personal project | Revision `c9d0a345b07be759be61c5cd9570ce2df73ee80b`; weights 1.67 GB on disk per model file listing; runtime VRAM **unverified** |
| Magi v3 API | [Pinned model source](https://huggingface.co/ragavsachdeva/magiv3/blob/c9d0a345b07be759be61c5cd9570ce2df73ee80b/modeling_florence2.py) defines `predict_detections_and_associations(images, processor)` and `predict_ocr(images, processor)` | Detection yields panels/texts/characters/tails and thresholded associations. OCR has text/boxes, no confidence score in these public methods. Adapter records `null` instead of inventing scores. |
| Transformers | Pinned Magi `config.json` and `generation_config.json` both name 4.45.2 | Installed `transformers==4.45.2`; pinned custom config loads as `florence2` |
| PyTorch | [Official previous versions page](https://pytorch.org/get-started/previous-versions/) lists PyTorch 2.4.1 with CUDA 12.1 wheels for Windows | Installed `torch==2.4.1+cu121` and `torchvision==0.19.1+cu121`; CUDA available and RTX 4050 detected |
| Install/cache route | `scripts/enter-runtime.ps1` points `TEMP`, `TMP`, pip, Hugging Face, Torch, npm, and Python bytecode caches into `.runtime` on D: | No project download or cache is intentionally directed to C:. Files under `.runtime`, `.venv`, `library` are ignored by Git. |

## Built so far

- Initialized Git in `D:\Motion Manga`.
- Created a Python 3.11.9 virtual environment on D: and D-only cache setup script.
- Added a swappable page-adapter contract, page/version/config hash cache, cross-process heavy-model file lock, load/run/unload scheduler, CUDA cache cleanup, device VRAM sampler, pinned Magi adapter, and five-page CLI.
- The Magi adapter uses detected text crops with 8 px padding for OCR, never full-page OCR. It retains the raw output and notes unavailable confidence explicitly.
- `pipeline/requirements.lock` now pins the complete resolved Python environment. `pipeline/prepare_magi.py` fetched the exact snapshot and verified `model.safetensors`: 1,665,460,218 bytes, SHA-256 `922cf0a84284cfa3ddf7f487482040afce2d976c363070c5c13cccb4d62c6469`.

## Acceptance evidence so far

Command: `. .\scripts\enter-runtime.ps1; & '.\.runtime\python-package\tools\python.exe' -m unittest discover -s tests -v`

Result: 7 tests passed: cache key invalidation, cache hit skipping model load, unload and lock release after failure, heavy stages do not overlap within or across processes, load-only probe lifecycle, OCR crop bounds. The first overlap test run found a Windows lock-file race; it was fixed and the suite then passed. A later Windows 64-bit RAM API signature error was also caught and fixed by these tests.

Command: `. .\scripts\enter-runtime.ps1; & '.\.venv\Scripts\python.exe' -m pip check`

Result: `No broken requirements found.`

Command: `. .\scripts\enter-runtime.ps1; & '.\.venv\Scripts\python.exe' -m pipeline.m0_probe`

Result: load-only probe succeeded, with no page inference or quality claim:

| Measure | Observed |
|---|---:|
| Model load | 44.4967 s |
| Unload plus CUDA cleanup | 0.1847 s |
| Device VRAM baseline → observed peak | 0 → 1,677 MiB |
| PyTorch peak allocated / reserved | 1,589 / 1,604 MiB |
| Process RAM baseline → observed peak | 18 → 2,874 MiB |

Device VRAM was sampled through `nvidia-smi` every 0.2 s; PyTorch's allocator peak is separately recorded. This establishes weight residency only. Inference may use more memory.

Command: `. .\scripts\enter-runtime.ps1; & '.\.venv\Scripts\python.exe' '.\tests\smoke_magi.py'`

Result: **synthetic API smoke only** (one generated 768×1024 page, excluded from all golden metrics). Magi detection and crop OCR completed without OOM; one panel and one text region were returned, but OCR text was empty. The stage took 3.6077 s after a 34.2075 s model load. Detection was 3.2078 s and crop OCR 0.3845 s. Device VRAM peak was 2,079 MiB, PyTorch allocated/reserved peaks were 1,909/1,976 MiB, and process RAM peak was 2,701 MiB. These values do **not** replace the PRD's real-page targets.

## Pending acceptance and measurements

- Five real pages have not yet been provided. Detection/OCR JSON, golden-page inspection, page-hash cache replay, seconds/page, peak **inference** VRAM/RAM, and inference OOM behavior remain unmeasured.
- Final acceptance and completed report are pending the real pages.

## Risks and deviations

- Magi v3's public methods do not expose calibrated confidences; see proposed D17 for the later review threshold work.
- The model's 1.67 GB weight size is **not** a VRAM requirement. Weight loading measured 1,677 MiB device peak; inference fit remains unverified.
- The pinned Transformers version emits a warning about generation behavior in 4.50+, which is outside this exact lockfile. Do not upgrade without re-verifying Magi.
- The synthetic crop produced no OCR text; this is expected to be unrepresentative and requires real-page assessment.
- Git initialized under the sandbox account, so ordinary Git commands from the Windows user report “dubious ownership.” Per-command `git -c 'safe.directory=D:/Motion Manga'` works; changing ownership was denied. No global C: Git configuration was changed.
- No synthetic page will be used to claim a real-page quality or performance result.

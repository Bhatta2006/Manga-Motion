# M1a — Chapter import and page cache

1 October 2026. User authorized continuation with “ok continue.” Scope: import only. **All six M1a objective acceptance items pass. Stop for approval before M1b.**

## Built

- Folder, CBZ/ZIP and PDF import CLI with per-series direction/language/PDF-resolution settings.
- Immutable, content-addressed originals; SHA-256 ordered page index and lossless serving assets. Most images retain original bytes; TIFF receives verified lossless PNG. PDF containers remain intact, with PNG rasterization recorded separately.
- Hash/revision/settings cache identity, cache integrity checks/repair, atomic complete manifests and resumable per-page work after failure.
- Bounded streaming, archive validation, named page errors, folder link/reparse rejection, separate library OS lock and swappable CPU PDF rasterizer.
- Explicit original-pixel rule in PRD §5.1 and measured ingest results in §8. MotionScript v1 and the M0b reader remain unchanged.

Code commit: `7099ebe`. A following report/documentation commit includes small documentation/formatting corrections. New modules: `pipeline/ingest/{chapter,archive,pdf,pages,hashes}.py`, `pipeline/store.py`, `pipeline/import_chapter.py`. The shared RAM probe additionally exposes Windows process-lifetime peak without changing existing sampler defaults. Pins and source/API/license review: `pipeline/ingest/DEPENDENCIES.md`. Usage: `pipeline/ingest/README.md`.

## Evidence

Commands executed from `D:\Motion Manga`, after dot-sourcing `scripts/enter-runtime.ps1`:

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
# Ran 31 tests in 20.732s; OK (13 new import tests, 18 existing regressions).

& .\.venv\Scripts\python.exe tests/verify_m1a_golden.py
# Folder, CBZ, PDF: five pages each; cold 0 hits / 5 misses, warm 5 hits / 0 misses.
# Original five source hashes unchanged: true.
# Private evidence: D:\Motion Manga\reports\M1a-golden-metrics.json

& .\.venv\Scripts\python.exe -m pip check
# No broken requirements found.
```

Benchmark invokes the actual CLI in six fresh Python processes. Example of the exercised entry point:

```powershell
& .\.venv\Scripts\python.exe -m pipeline.import_chapter library/fixtures/m1a/golden.cbz --series m1a-benchmark-093d300a --chapter cbz
```

The private fixtures copy/embed the **five real user JPEGs**, retaining original JPEG streams in the PDF; two pages are grayscale and three RGB. These mixed-series pages are a format/fidelity set, not a continuous story. No private manga pixels or text enter Git. The extra mislabeled AVIF is not part of this five-page golden set; unsupported decoder inputs fail with a named error rather than silently disappearing.

| Acceptance | Evidence | Result |
|---|---|---|
| All three input types import | `test_folder_and_cbz_original_bytes_pixels_and_order`, `test_pdf_lossless_render_and_original_preservation`; CLI benchmark records five pages for each format | Pass |
| Original assets byte-identical | Test byte comparisons for all five image originals, CBZ container and PDF container; benchmark rehashes supplied sources; original uploaded PRD hash also unchanged | Pass |
| Serving raster fidelity | Image byte/RGB-hash equality; TIFF-to-PNG decoded pixel equality; all five PDF PNGs compared pixel-for-pixel with direct pinned PDFium renders at identical settings. Visual review of all five PNGs found no new cropping, color inversion, missing content or illegible rendering | Pass under the documented PDF definition |
| Stable page hashes | Cold/warm manifest equality, hashes agree with real source inventory for folder/CBZ; same PDF output reused; setting/source mutations tested | Pass |
| Reimports reuse cache / resume | Warm tests deliberately forbid raster decoding and PDF rendering; 5/5 hits for each. Deleted/corrupt assets and bad JSON repair. After a page-3 failure, completed page-1/2 caches survive and retry reports 2 hits / 3 misses. One changed source yields 4 hits / 1 miss | Pass |
| Errors name the affected page | Malformed image, ZIP CRC failure and forced PDF render failure assert the exact source/page label. Unsafe ZIP paths, duplicate names, links, oversized inputs and corrupt containers reject. Previous manifest remains byte-identical on failed import | Pass |

Additional risk checks: Windows junction pointing back into the input folder is rejected without recursion; PDF over-limit dimensions are rejected before `PdfPage.render`; changing PDF dpi invalidates all five render records and changes output dimensions. A 72-dpi render is an explicit setting change, not an automatic fallback. Animated/multipage images and non-identity EXIF are rejected pending an explicit policy.

Initial test failures were fixed before acceptance: RGB-only PDF fixture rejected grayscale originals; Windows ZIP writing normalized a backslash attack fixture; benchmark script needed the project root on its Python path. Final suite and CLI benchmark both passed. These failures were not marked complete while unresolved.

## Measurements

Machine: RTX 4050 Laptop / 6,141 MiB, 15.65 GiB RAM, native Windows 11. Python 3.11.9, Pillow 10.4.0, pypdfium2 5.13.0, PDFium 153.0.7999.0. Models loaded: **none**. Cloud calls: **none**. New download: pinned 3.9 MB PDFium Windows wheel; installation/cache/temp/fixtures/evidence all on D.

Latest private run: series `m1a-benchmark-093d300a`. Cold = empty application cache. OS disk caches were not flushed. Single observations; no percentile/general chapter claim.

| Input / cache | Mean page work (s) | Five-page elapsed (s) | Hits / misses | Process lifetime peak RAM (MiB) | Sampled VRAM peak (MiB) |
|---|---:|---:|---:|---:|---:|
| Folder cold | 0.030713 | 1.906695 | 0 / 5 | 58 | 0 |
| Folder warm | 0.004808 | 0.673019 | 5 / 0 | 36 | 0 |
| CBZ cold | 0.029288 | 0.865751 | 0 / 5 | 58 | 0 |
| CBZ warm | 0.004589 | 0.187170 | 5 / 0 | 37 | 0 |
| PDF cold, 144 dpi | 0.146580 | 1.034257 | 0 / 5 | 63 | 0 |
| PDF warm | 0.002915 | 0.703983 | 5 / 0 | 41 | 0 |

Per-page work includes stream copy/hash, decode or PDF render when cold, asset verification/publication and cache writes. Elapsed includes initial/final `nvidia-smi` sampling, container setup/copy, final source verification, manifest/settings publication and disk counting; excludes Python process startup. Telemetry/setup dominates these small imports, so elapsed is not simply five times page work. Earlier single observations were slower (folder cold 2.677687 s, CBZ 0.955453 s, PDF 1.695159 s); the latest values above are measurements, not promised latency.

GPU baseline and peak were both 0 MiB in all six observations. Import makes no CUDA calls. Memory is sampled at 0.2 s, with page-boundary RAM samples; interval peaks can miss short allocations. Windows process-lifetime peak is also recorded, rounded to MiB, and captures them in these fresh processes. Cold interval RAM baseline/peak: folder 34/36 MiB, CBZ 34/36 MiB, PDF 34/56 MiB; lifetime peaks 58/58/63 MiB. No CUDA allocator metric is invented for a CPU-only stage.

| Input | Serving page bytes, total / mean | Complete chapter disk bytes / mean per page |
|---|---:|---:|
| Folder | 968,031 / 193,606 | 1,944,582 / 388,916 |
| CBZ | 968,031 / 193,606 | 2,913,580 / 582,716 |
| PDF | 4,911,273 / 982,255 | 5,891,097 / 1,178,219 |

Chapter totals include original copies, serving assets, container where applicable, page cache JSON and import manifest; exclude the separate fixture inputs, series JSON and shared runtime. Warm runs do not increase chapter size. Original and serving image copies are separate files intentionally. D free space observed: 65.87 GiB before report publication.

## Deviations / limits / remaining risks

- Approved D05 supersedes original §5.1's blanket WebP/upscale path: exact originals or proven lossless derivatives; no art generation, upscale or inpaint. PDF rasterization has no single source raster to claim byte equivalence against. Default 144 dpi is recorded and configurable; fixtures happen to match native JPEG dimensions at that dpi.
- Import uses a small on-disk manifest store; FastAPI/SQLite jobs/library screen remain M1d. There is no new reader UI in M1a.
- Filename order is deterministic but unverified story order. The importer flags that inference; M1b/Review handle page/panel order quality.
- Conservative size/count/ratio limits reject some unusually large legitimate inputs. They do not bound adversarial vector-PDF complexity; no hardened public upload service claim.
- Corrupt or interrupted imports can retain unused original/cache artifacts. Revisions retain old immutable assets. Automatic cleanup is deferred; PDF PNGs cost more disk than original JPEGs.
- Non-identity EXIF, animated/multipage images, unsupported AVIF decoding and TIFF modes not safely representable as PNG need an explicit future policy. No silent fallback, color conversion or quality loss is used.
- Full-chapter speed, independent OCR confidence/order, actual phone performance, semantic SFX/music, perceived character depth and uncapped dialogue pacing are not established by import tests. They remain planned acceptance gates.

**Next planned slice: M1b (panel/order/OCR normalization). Await the user's “approved” before starting it.**

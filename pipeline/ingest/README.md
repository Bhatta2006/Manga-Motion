# M1a chapter import

Import validates and stores pages. Detection, MotionScript generation, library UI, and reader integration belong to later approved slices.

```powershell
. .\scripts\enter-runtime.ps1
& .\.venv\Scripts\python.exe -m pipeline.import_chapter 'D:\manga\chapter.cbz' --series my-series --chapter ch01 --direction rtl --source-language en --target-language en --metrics reports/M1a-my-chapter.json
```

The positional source can be a folder, `.zip`, `.cbz`, or `.pdf`. All outputs must reside on D. Defaults are RTL, English source/target language, and PDF 144 dpi. Omitted options inherit `library/<series>/series.json`; chapter manifests snapshot their settings. Explicit setting changes invalidate affected import cache entries. `--pdf-dpi` accepts 72..300 and records the chosen rasterization resolution.

Outputs:

- `library/<series>/series.json`: per-series settings.
- `library/<series>/<chapter>/sources/<sha256>.*`: byte-identical originals, including archive/PDF containers. Image originals use `.image`; decoding identifies the actual format.
- `pages/<sha256>.<format>`: exact original image bytes; PDF pages are lossless PNGs of the recorded PDFium render.
- `cache/ingest/*.json` and `cache/ingest-pdf/*.json`: page verification/render records, keyed by source hash, adapter revision and settings.
- `import.json`: ordered page index with byte hashes, decoded RGB pixel hashes, sizes, source names, fidelity mode and cache keys. This is an **import manifest**, separate from MotionScript v1.

Folder/archive pages use natural filename ordering (`page2` before `page10`); PDF uses document order. Filenames do not prove story order, so the manifest flags inferred ordering for review. Duplicate content can appear at multiple positions while sharing the same content-addressed asset. Non-image files are listed as ignored; an image with an unsupported decoder/format is a named failure, never silently omitted.

Repeated imports hash inputs and verify cached serving bytes, but skip image decoding/PDF rendering on hits. Deleted or corrupt page assets and malformed JSON cache records are repaired. A failed import leaves completed page caches available for retry and preserves the last complete `import.json`. Previous content-addressed assets are retained; no automatic deletion occurs when inputs/settings change.

Limits: 2,000 pages; 8,000 folder/archive entries; 128 MiB per image/member; 2 GiB container; 4 GiB folder images/archive expanded members; 40 million pixels per raster. Archive absolute/traversal/backslash/drive paths, symlinks, duplicate names ignoring case, encrypted members and extreme compression ratios are rejected before image decoding. Folder symlinks/reparse points are rejected. Animated/multipage image files and non-identity EXIF orientation need an explicit future policy and currently fail by page name.

PDF fidelity means PNG pixels match the rasterizer output, **not** that a PDF has a single original raster. PDFium renders the page's geometry, crop, vector art and forms; it does not regenerate manga art. The source PDF stays byte-identical. PDF decoding/rendering can produce different pixels from Pillow's JPEG decoder even when a PDF embeds the same JPEG.

Verification (requires the private M0a inventory and five originals):

```powershell
. .\scripts\enter-runtime.ps1
& .\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
& .\.venv\Scripts\python.exe tests/verify_m1a_golden.py
```

Benchmark fixtures embed/copy the five real pages without re-encoding. They exercise formats; they are not a continuous manga chapter or a test of scene understanding. Every benchmark uses a new private series and fresh processes for cold/warm observations, with raw evidence in ignored `reports/M1a-golden-metrics.json`.

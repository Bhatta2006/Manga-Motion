# Import dependency verification

Verified 1 October 2026 before first use. Import loads no AI models and uses no cloud APIs.

| Dependency | Pin / install path | Evidence and choice | Memory |
|---|---|---|---|
| Python standard library `zipfile`, `hashlib`, `pathlib`, `json` | Python 3.11.9, `.runtime/python-package/tools` | [ZIP documentation](https://docs.python.org/3.11/library/zipfile.html); explicit member enumeration and bounded streaming, no `extractall` | CPU only |
| Pillow | 10.4.0, `.venv/Lib/site-packages/PIL` | Previously verified in M0; [Image API](https://pillow.readthedocs.io/en/stable/reference/Image.html). Decode for validation/hash; TIFF gets a verified lossless PNG for browser decoding. Originals are copied without conversion. HPND/Pillow license | One page at a time; 40 million pixel limit |
| pypdfium2 / bundled PDFium | 5.13.0 / 153.0.7999.0, `.venv/Lib/site-packages/pypdfium2` and `pypdfium2_raw` | [README](https://github.com/pypdfium2-team/pypdfium2), [API](https://pypdfium2.readthedocs.io/en/stable/python_api.html), [release](https://pypi.org/project/pypdfium2/5.13.0/). BSD-3-Clause or Apache-2.0; PDFium and bundled third-party notices included in wheel. Pinned non-V8 wheel; installed signatures/source checked for `PdfDocument`, `init_forms`, `get_size`, `render`, `to_pil`, `close` | CPU rasterization, no CUDA allocation; measured VRAM/RAM in M1a report |

Wheel: `pypdfium2-5.13.0-py3-none-win_amd64.whl`, SHA-256 `47dcca2a8d507b5fd24f94c3c9d48fb379430f097bc20f01beff6c963ffbcedb`. Wheel and metadata review live under ignored `.runtime/ingest-review` on D. All package/cache/temp writes used `scripts/enter-runtime.ps1`; `pip check` passed.

Install from D after verifying the wheel checksum:

```powershell
. .\scripts\enter-runtime.ps1
& .\.venv\Scripts\python.exe -m pip install --no-index --no-deps .runtime/ingest-review/pypdfium2-5.13.0-py3-none-win_amd64.whl
```

PDFium is behind `PdfRasterizer`; it can be replaced without changing the import manifest or MotionScript. PDFium is not thread-safe, so the library import lock serializes imports. Each PIL image/bitmap/page/document is explicitly closed. No heavy-model scheduler lock is taken by this CPU stage.

Known boundary: byte-size, page-count, and raster-size limits do not bound pathological PDF vector complexity. This is a local personal importer, not a hardened public upload service. Renderer replacement/upgrades require renewed verification and a new adapter revision.

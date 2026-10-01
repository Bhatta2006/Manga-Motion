# M1d local API dependency verification — 2026-10-01

Exact versions are in `pipeline/requirements-api.lock`, included by the main lock.
Install directory: `D:/Motion Manga/.venv/Lib/site-packages`. Pip cache, metadata
resolution report and temporary files use the existing D-drive runtime. No GPU
libraries or models are added by these packages; expected additional VRAM is 0.

| Package | Pin | Provenance / checked API | License |
| --- | --- | --- | --- |
| FastAPI | 0.142.2 | [README](https://github.com/fastapi/fastapi), [lifespan](https://fastapi.tiangolo.com/advanced/events/), installed router/TestClient source | MIT |
| Uvicorn | 0.54.0 | [README](https://github.com/Kludex/uvicorn), installed `uvicorn.run` signature (loopback, port, proxy_headers) | BSD 3 clause |
| Starlette | 1.7.0 | [responses](https://starlette.dev/responses/), installed middleware and StaticFiles source | BSD 3 clause |
| Pydantic | 2.13.5 | [models](https://docs.pydantic.dev/latest/concepts/models/), installed ConfigDict/Field | MIT |
| HTTPX | 0.28.1 | [README](https://github.com/encode/httpx), installed TestClient transport compatibility | BSD 3 clause |
| SQLite | 3.45.1, Python 3.11.9 builtin | [Python docs](https://docs.python.org/3.11/library/sqlite3.html), parameter binding, short transactions, WAL | public domain SQLite |

Licenses confirmed in each installed wheel's dist-info/licenses, not inferred from
the current repository alone. All resolved transitive versions pinned. Minimal
base packages only: no standard extras, CLI watchers, multipart upload, telemetry
SDK, exporter or new browser download. FastAPI's base dependency includes
OpenTelemetry API 1.45.0 (Apache 2.0); no provider/exporter is configured. The API
does not send chapter data to a cloud service. Model/runtime pins are unchanged.

Resolution: `python -m pip install --dry-run --report .runtime/api-resolve.json
fastapi==0.142.2 uvicorn==0.54.0 httpx==0.28.1`;
installation: `python -m pip install -r pipeline/requirements-api.lock`;
`python -m pip check` reports no broken requirements.

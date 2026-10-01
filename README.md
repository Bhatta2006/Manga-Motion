# MangaMotion

Personal, local manga-to-motion reader. Original page pixels are preserved.
The source specification is [docs/PRD.md](docs/PRD.md); progress and approval gates
are in [MILESTONES.md](MILESTONES.md). Voice work is deferred in favor of visuals
and scene audio. MotionScript v1 remains the pipeline/reader contract.

## Run the Library

From PowerShell in `D:\Motion Manga`:

```powershell
. .\scripts\enter-runtime.ps1
npm run build --prefix reader
& .\.venv\Scripts\python.exe -m pipeline.api.app --port 5174
```

Open <http://127.0.0.1:5174/>. Choose **Import a chapter**, enter a D-drive folder,
CBZ/ZIP or PDF path, a series/chapter identifier, and reading direction. English
OCR is the verified route. The Library shows processing stages and any failure;
**Retry processing** retains completed hash caches. **Read chapter** opens the
tap-paced reader. Tap the art to advance; arrows, replay, Original page and Reduce
motion are available. Current Auto is provisional; reading-aware dwell is M1e.

The API stays on loopback. Phone access, mobile Flow, offline PWA behavior, final
scene SFX/music and character pop-out depth have later acceptance gates. The
existing `preview/m0b` chapter retains the original procedural SFX prototype;
new M1d chapters currently contain camera events only.

## Runtime and data

- Python, packages, model weights, SQLite jobs, logs and caches live on D:
  (`.venv`, `.runtime`, `library`). Existing Node/Edge binaries may be read from C;
  do not install or download anything there.
- Install exact dependencies with the existing D-drive Python:
  `python -m pip install -r pipeline/requirements.lock` and `npm ci --prefix reader`
  **after** entering the runtime. Model preparation/provenance is documented in
  the milestone reports; no model download is triggered by starting the API.
- One worker process runs a chapter, then exits. It holds an OS worker lock;
  heavy adapters additionally use the existing scheduler lock and CUDA cleanup.
  SQLite resumes one interrupted attempt automatically; repeated interruption
  becomes a visible failure requiring Retry. Do not delete caches to retry.
- Playback uses immutable validated snapshots and checks asset hashes. Earlier
  completed playback remains available while a new import runs or fails.
- Private pages, models, `.env`, database and generated chapter artifacts are
  ignored by Git. API keys belong only in `.env`; M1d makes no cloud calls.

## Verify

```powershell
. .\scripts\enter-runtime.ps1
& .\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
npm test --prefix reader
npm run build --prefix reader
& .\.venv\Scripts\python.exe -m pip check
```

With the API running and the private five-page fixtures present:

```powershell
# Choose a fresh series for a genuine cold application-cache measurement.
& .\.venv\Scripts\python.exe tests\verify_m1d_golden.py --series golden-new-run
node reader\tests\library-smoke.mjs
```

The browser smoke expects the measured `golden-m1d/chapter` and `preview/m0b`
chapters. It uses installed Edge and writes its profile/artifacts only on D.
Reports distinguish desktop emulation from actual-phone evidence and clock
sampling from externally measured A/V synchronization.

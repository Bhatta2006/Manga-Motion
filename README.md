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
# Once, before the first semantic analysis (downloads only to D:):
.\scripts\install-director.ps1
& .\.venv\Scripts\python.exe -m pipeline.api.app --port 5174
```

Open <http://127.0.0.1:5174/>. Choose **Import a chapter**, enter a D-drive folder,
CBZ/ZIP or PDF path, a series/chapter identifier, and reading direction. English
OCR is the verified route. The Library shows processing stages and any failure;
**Retry processing** retains completed hash caches. **Read chapter** opens the
reader. Mobile defaults to **Flow**: swipe up/down between scenes and tap to
pause/resume. **Auto** uses adjustable dialogue/caption reading time. Arrows,
replay, Original page and Reduce motion remain available.

The API stays on loopback. Phone access, actual-device validation, offline PWA behavior, final
music listening quality and character pop-out depth have later acceptance gates. Scene sounds now
route locally, with uncertain choices flagged for review. The
existing `preview/m0b` chapter retains the original procedural SFX prototype;
new directed chapters include restrained local SFX. Local scene interpretation
uses the measured 4B Qwen profile and stays flagged for review; it is not a claim
of reliable semantic accuracy. Cache hits avoid model loading entirely.

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

Directed chapters now include local mood music and ambience using approved
MotionScript v2. Open **Sound levels** for independent music/ambience/voice/SFX
controls. **Silent auto** follows reading time with audio muted. Adjacent scenes
sharing a music bed preserve loop phase; pauses and replay are supported.
All inferred moods remain reviewable. See `reports/M3d3.md` for measured audio
and limitations. Character cutout depth is still a later implementation slice.

Use a chapter’s **Review** link to correct text, kinds, panel order, associations
and scene cues. Fixes are saved separately from original art/model outputs and
reused on rerun. Speaker IDs can be assigned for the later voice stage; re-voicing
is pending. Another window’s edits or changed detection geometry are rejected
before publication. See `reports/M4a.md` for measured saves and recovery tests.

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
node reader\tests\music-smoke.mjs
node reader\tests\review-smoke.mjs
```

The browser smoke expects the measured `golden-m1d/chapter` and `preview/m0b`
chapters. It uses installed Edge and writes its profile/artifacts only on D.
Run these integration scripts sequentially: they temporarily exercise imports
and corrections before restoring the golden chapter, so concurrent fixture
reads are not independent.
Reports distinguish desktop emulation from actual-phone evidence and clock
sampling from externally measured A/V synchronization.

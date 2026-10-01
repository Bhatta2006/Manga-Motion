# MangaMotion visual preview

M0b uses five independent supplied pages, 25 detected panels, restrained camera motion and sparse local SFX. Narration is deferred. Character parallax is enabled only where the source-only guard test passes; none of these five pages passes. The original page is always available with **Original page**.

From PowerShell in `D:\Motion Manga`:

```powershell
. .\scripts\enter-runtime.ps1
npm ci --ignore-scripts --no-audit --no-fund --prefix reader
& .\.venv\Scripts\python.exe -m pipeline.m0_preview --run-label warm
npm run build --prefix reader
& .\.venv\Scripts\python.exe -m pipeline.preview_server
```

Open **http://127.0.0.1:5173**. If the preview server is already running, open the URL directly. It exposes only the built reader and generated preview chapter on loopback.

- **Play / Pause:** start or pause the current panel. **↻:** replay.
- **Tap the art / →:** next panel; **←:** previous. Keyboard arrows respect RTL; Space toggles playback.
- **Tap paced:** wait at the panel end. **Auto play:** continue through all pages.
- **Original page:** pause and show the full source page; **Motion view** returns.
- **SFX:** mute effects. **Reduce motion:** hold the initial framing and disable parallax/fades/glides.

## Boundaries for later integration

`schema/motionscript-v1.schema.json` validates the PRD v1 envelope. The prototype implements its camera, line and SFX events; only cameras and SFX are generated now. The camera recipe vocabulary is the M0 subset, not the complete director grammar. Confidence fields are null where model APIs provide no calibrated scores.

`pipeline/adapters/tts_base.py` defines the future voice interface. The reader already schedules `line.audio` on a separate voice bus and extends panel duration from `line.dur`. Add a verified engine and page-stage wrapper later; no voice engine is currently installed or loaded. Do not change v1 fields without the user's contract approval.

`player.ts` owns the Web Audio clock and pause/resume/cancellation; `camera.ts` fits/clips framing; `parallax.ts` shares source textures for eligible planes. No model executes in the browser. `pipeline/adapters/sfx.py` can be replaced by a local asset adapter. Current accents are procedural placeholders, not realistic Foley or semantic directing.

## Verification

```powershell
npm test --prefix reader
& .\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
& .\.venv\Scripts\python.exe -m tests.run_browser_benchmark
node reader/tests/frame-smoke.mjs
```

Browser tests require the running preview server and installed Edge; they use D-only profiles. The full test plays real panel durations (about 2½ minutes). Screenshots and metrics remain private under `reports`, excluded from Git. See `reports/M0b.md` for evidence and limitations.

# Motion and sound evaluation

Run after processing three continuous chapters, with dialogue/action/comedy represented:

```powershell
. .\scripts\enter-runtime.ps1
& .\.venv\Scripts\python.exe -m pipeline.audio.evaluate --series my-series --chapter chapter-01
```

Open the returned anonymous A/B/C URLs against the running Library (`http://127.0.0.1:5174`). Each preserves the same source art, panel dwell and exact audio events. Static shows the whole original page, fixed uses the old geometric recipe, directed uses current semantic framing. Condition mapping stays in ignored private chapter cache; do not reveal it before collecting scores. A viewer can recognize static imagery, so this is label-blind, not perceptually indistinguishable. No results are fabricated by the preparation tool.

Use the same actual phone, output volume and headphones/speaker throughout. Randomize sample order independently per chapter. Score before revealing condition names.

| Chapter / sample | Felt directed (1–5) | Comfortable (1–5) | Sound fits scene (1–5) | Sound distraction (1–5, lower better) | Discomfort incident / time | Prefer over static? |
|---|---|---|---|---|---|---|
| 1 / A | | | | | | |
| 1 / B | | | | | | |
| 1 / C | | | | | | |
| 2 / A–C | | | | | | |
| 3 / A–C | | | | | | |

Record source chapter IDs, device/browser, viewing mode, volume/output, cue corrections and sample mapping after scoring. Acceptance requires directed/comfortable means ≥4/5 and zero discomfort incidents; final three-chapter preference target is ≥70%. Five mixed pages, automated RMS tests and engineer impressions do not satisfy these subjective gates. Retain failures and specific cue/motion timestamps for correction.

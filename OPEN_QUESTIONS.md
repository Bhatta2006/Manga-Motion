# Open questions and gates

The PRD's §12 questions are tracked here. Items are ordered by the first milestone they affect. Only the plan approval and real pages block M0; later preferences can be chosen when their milestone starts.

| ID | When needed | Question / current answer | Recommended default or next action |
|---|---|---|---|
| Q01 | Resolved | The user said “start with the implementation,” authorizing M0a after the Step 1 plan. | Execute M0a only, then stop for the next approval. |
| Q02 | Before M0b model evaluation | Which 5 to 10 real manga pages form the private golden set, ideally spanning dialogue, action, and comedy? Need originals and their correct reading direction/language. | User supplies the pages; start with five for M0 and extend to ten by M1/M2. No fabricated quality scores. |
| Q03 | Partly resolved | Official Python 3.11.9 NuGet runtime and a virtual environment run from D:. CUDA/model dependency compatibility is still under test. | Keep installs and caches on D:; verify the full Magi stack before claiming this resolved. |
| Q04 | M0a/M0b | Do current Magi v3 weights and dependencies retain personal-use permission and fit in 5,920 MiB free VRAM with this driver? | Verify official source and model card before download. If not, propose a documented alternative in `DECISIONS.md` and wait for approval. |
| Q05 | M1 | Source language: Japanese raw, English translation, or both? | Per-series setting as in PRD; infer the first golden-set language only for initial tests, retain both as configuration. Confirm before choosing default OCR/TTS route. |
| Q06 | M1 | Reading device: phone, tablet, or desktop first? | Phone-first responsive layout because §4 describes phone access; validate on the user's actual device when available. |
| Q07 | M2 | Are there approved reference clips for principal voices, or should the tool generate designed voices locally? | Use designed/local voices or the user's own clips. Never clone actors or third parties without explicit rights. |
| Q08 | M2 | Is Fish Audio access desired for expressive lines, and what is the acceptable per-chapter spend? | Fully local route is the baseline. Verify current price, terms, and API behavior before proposing selective Fish calls; do not require it for M2 acceptance. |
| Q09 | M3 | Which permitted VLM director provider/key should be used, and what privacy/cost limit applies to page images? | Keep an adapter and a local fallback; make no cloud call until the user configures the key and terms are verified. |
| Q10 | M3 | What is the typical content mix for camera tuning? | Normal/subtle default; calibrate on the 3 test chapters rather than assume action-heavy material. |
| Q11 | M4 | Can source-only layer parallax be visually clean without inpainting or hiding source pixels? | Feasibility gate; if not, use camera-only motion and log the limitation. |
| Q12 | Beyond v1 | Should vertical webtoon/manhwa strips be supported? | Keep out of v1 per PRD non-goals. |

## Resolved from the supplied PRD and environment

- Hardware: RTX 4050 Laptop, 6,141 MiB total VRAM; 15.65 GiB system RAM. Exact free memory and performance vary; see `ENVIRONMENT.md`.
- Deployment: offline chapter processing, PWA reader, audio master clock, one heavy model at a time.
- Cloud scope: VLM director and selective Fish expressive lines only, subject to verified terms and configured keys.
- Art: no generative redraw or inpainted replacements under the user's hard constraint; D05/D06 need plan approval because the PRD contains conflicting optional paths.
- WSL2: installed command is not presently usable. Native Windows is the initial route, pending Q03.
- No Git repository or golden images existed at Step 1, so neither commits nor quality measurements are possible yet.

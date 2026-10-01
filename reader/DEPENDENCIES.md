# M0b dependency verification — 2026-10-01

Exact direct versions and all transitive versions/integrities are in `package-lock.json`. Install location is `D:\Motion Manga\reader\node_modules`; npm cache/temp are routed by `scripts/enter-runtime.ps1` to D. No global package installation or browser download.

| Dependency | Pin | Verification / reason |
|---|---|---|
| PixiJS | 8.21.0, MIT | [Application docs](https://pixijs.com/8.x/guides/components/application), [Graphics docs](https://pixijs.com/8.x/guides/components/scene-objects/graphics), tagged license and installed `.d.ts` source read. `Application.init`, `Assets.load/unload`, `Sprite`, shared `TextureSource`, `Graphics` masks verified. One original texture per loaded page; affine camera transform; reuse one mask geometry. |
| Vite | 8.3.2, MIT | [Official guide](https://vite.dev/guide/) and installed `LICENSE.md` read. Requires Node 20.19+ / 22.12+; installed Node 24.21.0 satisfies it. `vite build` verified locally. |
| TypeScript | 5.9.3, Apache-2.0 | [Tagged license](https://github.com/microsoft/TypeScript/blob/v5.9.3/LICENSE.txt) and exact official registry metadata read. Conservative pin; no need for a newer compiler/runtime. `tsc --noEmit` passes. |
| Ajv | 8.20.0, MIT | [Getting started](https://ajv.js.org/guide/getting-started.html), installed license and official registry metadata read. Local draft-07 schema compiled; no remote schema fetch. |
| playwright-core (tests only) | 1.63.0, Apache-2.0 | [BrowserType docs](https://playwright.dev/docs/api/class-browsertype), official license/registry metadata read. Uses installed Edge 154.0.4258.48, with profile/download/artifact paths on D. It downloads no browser. |

Raw exact registry metadata is saved under `.runtime/reader-review/` on D, excluded from Git. Existing Node and Edge binaries are used from their existing system install locations. All task-created packages, profiles and artifacts are on D.

No new model or inference API is used. Motion/parallax checks use existing pinned Pillow 10.4.0 and NumPy 1.26.4. SFX is owned deterministic PCM synthesis (`procedural-sfx-1`), not a downloaded asset or model. Expected additional model VRAM: 0. Measured stage/device memory and integrated-GPU reader results are in `reports/M0b.md`.

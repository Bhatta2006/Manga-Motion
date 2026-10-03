# M5a — Bounded prefetch and explicit offline reading

2026-10-03. Technical gates pass on the five supplied pages in installed desktop Edge with a 390×844 viewport. Actual-phone responsiveness/PWA installation and larger chapter quotas remain unverified.

## Built and dependency verification

Native Service Worker, Cache Storage, StorageManager estimate and Web Locks APIs; no new npm/Python dependency, model, API key, browser download or cloud call. Reviewed current primary docs for [worker lifecycle](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers), [Cache.put](https://developer.mozilla.org/en-US/docs/Web/API/Cache/put), [storage estimates](https://developer.mozilla.org/en-US/docs/Web/API/StorageManager/estimate) and [storage locks](https://developer.mozilla.org/en-US/docs/Web/API/LockManager/request). Existing pinned Pixi 8.21.0, TypeScript 5.9.3, Vite 8.3.2 and playwright-core 1.63.0 remain unchanged. Observed Edge auto-updated to **154.0.4258.53**; no browser version was silently reported as the earlier .48 run.

`scripts/open-reader.ps1` opens installed Edge using a dedicated **D-drive profile and disk cache**, enabling offline storage. Ordinary browser views do not automatically install a worker or open the offline index; Save offline is unavailable until the launcher/controlled profile enables it. This prevents this app initiating offline downloads in an uncontrolled default C-drive profile. All exercised profiles, cache, artifacts and temp files are on D:. Manga content remains ignored/private.

`reader/src/preload.ts` prefetches ±2 pages in current/+1/−1/+2/−2 priority, capped at five wanted textures and **32 Mi-pixels aggregate** (about 128 MiB RGBA before renderer overhead). The necessary current page remains available if it exceeds that budget; neighbors are skipped. At most one speculative texture load runs, required loads share in-flight work, and the current texture is pinned against stale completion eviction. An outgoing crossfade can retain one extra source (six transient textures). Navigation is serialized while loading. Old sources unload explicitly.

`AudioTimeline` retains current panel clips and a separate current/next-two-panel speculative window: at most 32 prefetched clips / **32 MiB decoded PCM**, with one speculative worker and shared in-flight requests. Scene music retains its existing bounded mixer. A speculative miss does not claim successful playback; current preparation exposes actual missing audio.

An explicit Save offline action validates the unchanged v1/v2 contract, seals a complete chapter using the provider's immutable asset-hash manifest, checks every downloaded byte digest, then commits a single local index pointer. One asset is fetched/verified/stored at a time; per-asset limit **32 MiB**, total saved-chapter budget **512 MiB**, additional quota reserve **16 MiB**. Incomplete chapters cannot be saved. Failed refreshes retain the previous complete copy; orphan staging is cleared on the next save. Browser tabs serialize writes/removals with an origin lock. Removal deletes that copy, not originals.

The worker precaches the complete built shell, serves immutable saved assets by exact URL, uses network-first current playback/navigation, and exposes only saved chapters when offline. Build-specific shell caches retire on activation after old clients close; updates do not force a reader reload mid-scene. API mutations, `.env`, model/cache internals and review data are never cached. Offline review/timing edits are unavailable; saved timing still drives reading. Manifest, original project-owned geometric PNG icons and explicit routes support PWA metadata. Native installation UI itself has not been tested.

## Evidence / measurements

- `python -m unittest discover -s tests -p 'test_*.py'`: **108 tests, 73.470 s, OK**. Then the added build-change test plus manifest/path test: **2 focused tests, .563 s, OK**. Manifest exposes sealed asset hashes only; fixed public routes ignore a malicious `leaf` query; changed build changes shell cache identity. A non-failing upstream Starlette test-client deprecation warning remains; production/test dependencies were not upgraded without verification.
- `node --test reader/tests/*.test.mjs`: **25 pass**. Current pin versus stale speculative completion, old-window release, shared acquisition and pixel-budget clamps included. TypeScript, Vite production build and generated v1/v2/corrections type `--check` pass.
- `node reader/tests/offline-smoke.mjs` through D-only telemetry wrapper: online first ready **792.4 ms**, saving **.4300 s**, **3,973,895 bytes** saved. Offline reload **219.7 ms**. All **25 panels** navigate offline; native audio graph reports music, ambience and SFX energy, actual cutout loads. Offline Library lists one saved chapter; import/timing edits disabled; removal clears the saved cache. Zero page errors.
- Same run: failed 503 manifest and failed declared asset SHA preserve the previous copy, and incomplete staging disappears. Prefetch observed max **5 textures**, **230,400 PCM bytes**. Offline navigation median **33.43 ms**, p95 **81.12 ms** (includes test/UI turn costs). JS heap **14,848,690 bytes**. Full smoke **5.165752 s**; sampled **discrete device VRAM 0/0 MiB** baseline/peak; wrapper RAM **17 MiB**, not browser RSS. WebGL/iGPU memory is not separately measured. No pipeline/model stages ran, so no new inference seconds/page claim is made.
- Depth smoke after prefetch: **314 frames**, median **6.9 ms**, p95 **7.1 ms**, mask release/pause/Reduce/404/corruption still pass. Frozen comparison at the new viewport: **14,202** changed character pixels; all three text regions/outside-envelope changes **0**; rest pose maximum channel rounding delta **1**. Original five source hashes remain unchanged.
- Flow smoke: RTL and LTR each visit **25 panels with zero transport-button clicks/errors**, 390-pixel width; median frame **6.9/7.0 ms**, p95 **7.9/9.8 ms**. This is desktop emulation, not phone FPS or externally measured A/V sync.

## Acceptance and remaining risks

- [x] Complete processed chapter reopens and navigates offline, including actual audio/layer assets.
- [x] Speculative page/audio windows bounded and old resources released in unit/browser checks.
- [x] No missing audio on tested offline navigation; corrupted downloads fail before committing.
- [x] Tested viewport remains responsive with explicit device scope above.
- [ ] Actual-phone install/storage/reading comfort, real chapter/volume size and physical A/V trials.

Browser storage can be cleared/evicted by the browser or OS; the explicit offline status describes the saved copy rather than promising permanent storage. Required current textures/audio can exceed speculative budgets on unusually large inputs. The service remains loopback-only; this slice does not expose the processing API over LAN. Broader character-depth coverage, camera recipe refinements, settings/volume, export and deferred voices remain additional work.

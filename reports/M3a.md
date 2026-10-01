# M3a — Local semantic director (2026-10-02)

## Built

A pinned Qwen3-VL adapter through stage-owned llama.cpp, one page plus panel crops per call, temperature zero and an ID-keyed constrained output. Output cannot introduce coordinates: focus refers to detector/text IDs and the compiler resolves original boxes. Previous generated summary and optional series notes enter cache identity. Invalid responses retry once, then become explicit quiet/unknown reviewable fallback; fallback is not cached as successful inference. Human pacing labels override model text classes. Library displays semantic review notes.

The worker unloads OCR before directing, then publishes each completed directed page as validated v1 playback. This changes M1g's publication point from OCR completion to director completion so previously streamed scenes cannot change underneath the reader. New jobs cannot reuse an old job's stream. MotionScript fields/version are unchanged. No cloud provider is configured or contacted.

## Verified sources and pins

- [Official Qwen GGUF model card](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF): Apache-2.0; revision `1cd86afb9a95c410a6038ab3b40d8b578c892266`. Q4_K_M language weights 2,497,281,664 bytes and Q8 vision projector 453,974,304 bytes. SHA-256 values are in `pipeline/director/local-runtime.json`; installer and adapter verify them.
- [llama.cpp b11323 release](https://github.com/ggml-org/llama.cpp/releases/tag/b11323): MIT; commit `f11d642a27b921cf22b6a8beb1b899f960fedcde`, Windows CUDA 12.4 build. Installed `.runtime/llama-b11323`; model `models/qwen3-vl-4b-q4`. Runtime archives and model downloads, caches/logs/temp remain on D:. Reparse paths are rejected by the installer.
- [Pinned server source](https://github.com/ggml-org/llama.cpp/blob/f11d642a27b921cf22b6a8beb1b899f960fedcde/tools/server/server-common.cpp) verified the actual nested `response_format.json_schema.schema` API after the README example failed. [Grammar docs](https://github.com/ggml-org/llama.cpp/blob/f11d642a27b921cf22b6a8beb1b899f960fedcde/grammars/README.md) explain that schemas constrain sampling but are not injected into prompts. The explicit format and interleaved crop IDs are therefore part of prompt revision 7.
- [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-createjobobjectw) and [limit fields](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information): verified child ownership and kill-on-owner-close APIs. Tests confirm an abruptly terminated owner cannot leave its assigned subprocess alive. Assignment failure fails the stage and unloads it.

Verified `llama-server --help`, health and chat endpoints before inference. Context 8,192, image token limit 256, one slot, four CPU threads, flash attention, all GPU layers. No library upgrade or second resident heavy model.

## Evidence and measurements

Five existing real pages, 25 panels, 52 assigned text records; plugged into AC. Application director caches empty for the final run; OS filesystem cache was warm.

| Measurement | Actual |
|---|---:|
| Page inference seconds | 32.6125 / 23.9922 / 22.0338 / 16.2369 / 18.3394 |
| Mean inference seconds/page | 22.64296 |
| Load / unload | 4.838 / 0.4761 s |
| Complete director pass | 119.218977 s |
| Sampled device VRAM peak | 4,505 MiB |
| Parent RAM peak / server peak working set | 75 / 6,001 MiB |
| Valid page calls / rejected outputs | 5 / 0 |
| Total reported input+output tokens | 25,670 |
| Warm director pass | 0.061495 s; 5/5 hits; zero loads/requests |
| First CPU camera compilation | 1.878722 s including validation/sampling startup |
| CPU camera inference seconds/page | .0016 / .0012 / .0015 / .0010 / .0012 |
| CPU camera device peak / RAM peak | 0 / 46 MiB |
| Live warm job first observed directed prefix | 1/5 pages at 3.440789 s, status running |
| Live warm full job / worker duration | 4.452596 / 3.340768 s |
| Worker first readable directed page | 2.333544 s |
| Cloud calls / API spend | 0 / 0 |

Warm runs do not sample GPU/RAM; their peaks are unmeasured, not zero. GPU memory is device-wide sampled memory, not a universal input-independent fit guarantee. External llama.cpp does not expose Torch allocation peaks. Server working-set peak is measured separately from Python RAM.

- `python tests/verify_m3a_golden.py`: **5/5 director cache hits without loading**, semantic ID checks, unchanged source hashes, full AJV v1 validation: 5 pages/25 panels. Human-reviewed timing remains 120.75 s. Private measured JSON is ignored by Git.
- `python tests/verify_m1g_golden.py` with `MANGAMOTION_JOB_REPORT=M3a-job.json`: live worker above, all 20 analysis cache hits, 5 director hits, 5 camera hits; immutable original hashes preserved.
- `python -m unittest discover -s tests -p 'test_*.py'`: **81 tests, OK (25.268 s)**. Malformed-output, ID/enum/coordinate rejection, dependent-summary cache, callback-failure cleanup, human override, new-job identity and concurrency tests pass. Publication tests reproduced then fixed Windows read/write sharing errors; persistent failure preserves the previous valid file.
- `npm test --prefix reader`: **10/10**. `npm run build --prefix reader`: passed. `pip check`: no broken requirements.
- `node reader/tests/library-smoke.mjs`: all 25 panels navigated at widths 390 and 1280, zero page errors; steady frame median 6.9 ms/p95 7.2 ms, clock-sampling proxy 0.4 ms. These are Edge desktop emulation, not phone FPS or external A/V evidence.

## Acceptance and limits

- [x] All golden pages yield valid semantic records tied to existing IDs.
- [x] Detector coordinates remain original; no generated coordinates or art.
- [x] Cloud call policy: zero calls, no configured key/provider; no hidden API fallback.
- [x] Unresolved output is flagged; all five successful outputs also retain `semantic_accuracy_unverified` review flags.
- [x] Scheduler serializes heavy stages, loads once on misses and unloads/clears CUDA; cache hits avoid load. Assigned Windows child processes terminate with their owner.

**Semantic accuracy is not final acceptance.** Final prompt matches **42/52 (80.8%)** provisional, non-blind engineer text labels. Earlier 2B Q8 prompt matched 26/52 and flattened all beats to dialogue. The selected 4B prompt produces 7 dialogue, 14 reaction, 3 reveal and 1 establish tags, but descriptions still contain errors (for example, a ship scene described as a motorcycle). One prior-context contamination was reproduced and reduced by the revised prompt; a continuous chapter has not been supplied. No calibrated semantic confidence or independent beat/mood accuracy is claimed. Review/correction remains necessary.

The local director prioritizes zero recurring cost and measured fit; it is much slower than PRD's optimistic cloud latency estimates. Five varied pages cannot demonstrate full-story continuity. Camera grammar, scene sounds, music and real character masks are subsequent slices. No schema change or cloud/Fish implementation is included.

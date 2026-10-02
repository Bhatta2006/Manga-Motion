# MotionScript v2 proposal — music and source-only character depth

**Status: proposed, awaiting the user's explicit contract approval.** No production v2 reader, compiler, music or character-layer feature is enabled by this proposal. The current production contract is still v1.

## Boundary and ownership (ECC contract-first)

The Python pipeline provides chapter data. The PixiJS reader and future Remotion exporter consume it. The user approves contract/version changes; the engineer implements and verifies both sides. After approval, the authoritative artifact will be `schema/motionscript-v2.schema.json`; the draft currently lives at `schema/proposals/motionscript-v2.schema.json`. Prose explains behavior, and examples are fixtures; neither independently redefines field shapes. Resolve schema references locally only, with no remote `$ref` fetch.

Consumer jobs requiring the extension:

1. Keep quiet music/ambience playing across adjacent scenes without replaying a clip each panel or delaying reading.
2. Render a real character plane from original page pixels and an alpha mask; apply only approved safe transforms.
3. Replay/export the same timeline with explicit easing, timing and assets, without hidden playback sidecars.

## Exact scope of the change

| Location | Change / meaning |
|---|---|
| Root `version` | Exactly `2`; v1 remains supported separately. |
| Root `scenes` | Required map of scene IDs to `{mood, beds}`; `{}` means no persistent beds. |
| Panel `scene` | Optional reference to a scene ID. Absent means no bed for this panel; no implicit inheritance. Adjacent panels referencing the same ID share playback. |
| Scene `mood` | Array of up to eight short tags; empty means no known mood. Informational; the reader plays the selected assets, not a model. |
| Scene `beds` | Zero to two beds; at most one `music` and one `ambience` bus. |
| Bed | Required `id`, `bus`, `file`, `sha256`, `duration`, `loop`, `gain_db`, `fade_seconds`, `duck_db`. |
| Panel `layers` | Optional array, maximum three character layers. Absent/empty means flat source art. |
| Layer | Required `id`, `kind`, `source_page`, `source_bbox`, `mask`, `anchor`, `depth`, `poses`, `safety`. |
| Camera `ease` | Add `outExpo` and `outBack`; existing values remain. No new event type. |
| Assets | Add role-specific `music/`, `ambience/`, `layers/` allowlists; flat filenames only. Existing page/voice/SFX roles retained. |

Unknown fields and nulls are rejected where not declared. IDs remain strings. Bed IDs are unique within a scene; layer IDs within a panel. Scene references must exist. Page/panel IDs keep the existing uniqueness checks.

No new cloud API, heavy music model, generated background, depth displacement, voice engine, database schema or arbitrary effect-event framework is proposed.

## Persistent audio semantics

- `bus` is `music` or `ambience`; `file` must use that exact directory. SHA-256 binds the asset bytes. `duration` is the prepared decoded duration in seconds; preflight checks it against actual audio within one decoded sample. The loop is `[start_seconds, end_seconds]`, with `0 <= start < end <= duration`. PCM/seam checks must pass during asset preparation.
- `gain_db` is −60 to −6 dB, applied to a normalized source asset. Initial quiet targets are around −24 dB music / −30 dB ambience, subject to actual listening. `fade_seconds` is .05–3 s and no longer than the loop. `duck_db` is −24–0 dB, added during real voice windows, with 20 ms attack / 120 ms release. User gain/mute stays separate from duck automation. Full mix clipping/true peak is tested in M3d3; schema limits alone do not prove it.
- One shared Web Audio context remains the clock. Bed playback begins only after the user's audio-unlock gesture. Same-scene sequential advancement preserves the current loop phase, including a manual early advance; it does not recreate bed sources. Auto naturally carries time through the incoming transition. A changed/absent scene crossfades the previous bed out and the new bed in using equal-power envelopes; a silent scene fades to zero. Crossfade envelopes belong to bed buses, not panel dwell.
- Pause freezes scene offset and panel clock; resume continues both. Classic and Silent modes mute/stop beds. User music/ambience/SFX/voice controls are independent and persist through ducking/navigation. Replay or nonadjacent/backward navigation seeks to the deterministic canonical scene offset, using at least a 50 ms seek fade to avoid an abrupt discontinuity. Same-scene early Next is continuous; that interactive skipped timeline is intentionally different from a full Auto export.
- Canonical seek/export offsets sum the preceding panels' existing reading/speech/SFX playback extents and incoming transitions in the current contiguous scene run. A noncontiguous return to the same scene ID starts a new run. Offline metadata contains actual asset durations; the preflight/export builds the same duration table as the reader. Decoded voice or SFX can finish before a panel ends; music/ambience **never** enters the duration table used for panel completion.
- A panel's existing complete camera holds encode its reading budget. Later speech may extend it as v1 already permits. A 12-second or day-long looping music clip cannot lengthen that budget. Music is not inserted into the panel event timeline.
- Missing/corrupt bed bytes disable that bed and show a visible warning; camera and reading clock continue. Invalid schema/reference/loop metadata fails preflight before publication. No missing sound is silently marked successful.

## Character-plane semantics and art integrity

- `kind` is exactly `character`. `source_page` must equal the containing page ID. `source_bbox` is `[left, top, right, bottom]` in original page pixels, nondegenerate and contained in the current panel. The renderer samples the **original page texture**, never a replacement character bitmap.
- `mask` is a local PNG alpha mask matching the source crop dimensions. The renderer ignores mask RGB; alpha selects original source pixels. Mask generation may use a verified segmentation adapter, but does not invent art. Binary masks are the initial preparation target; any edge feather must pass the same seam/coverage tests.
- `anchor` is `[x_fraction, y_fraction]` within the source crop, each 0–1. `depth` is .01–1: normalized foreground ordering/interaction weight, not a physical depth map. Sort ascending depth with original array order as the stable tie-breaker. Original page is the background plane. Flat protected text from original source is composed last where necessary; no bubble hiding/redrawing.
- `poses` has 2–16 knots `{u, scale, offset}`. `u` runs strictly from 0 to 1; first pose must be `{u:0, scale:1, offset:[0,0]}`. `scale` is 1–1.06. `offset` is `[dx,dy]` measured as fractions of the panel width/height, each bounded to ±.02. Interpolate scale and offsets **linearly** between knots. Apply uniform scale around the source anchor, then page-coordinate translation. This is bounded 2.5D, not a regenerated 3D mesh.
- `u = clamp(panel_local_time / camera_end_time, 0, 1)`, excluding the incoming transition; camera end includes compiled reading holds. If a future speech clip extends panel playback, the final layer pose holds. Page/camera transform is applied after each layer's local transform. Pause freezes it. Reduce motion/Classic uses the single flat original page, with all character motion disabled.
- `safety` requires `method:"conservative-mask-envelope-v1"`, SHA-256 of original page bytes and mask bytes, `transform_sha256`, and `max_uncovered_pixels:0`. The transform hash is UTF-8 SHA-256 of recursively key-sorted compact JSON `{source_bbox,anchor,poses}`. It binds the checked motion configuration; it is **not evidence by itself**.
- Preparation must prove that the transformed original-pixel foreground covers the old character silhouette throughout every permitted interpolated pose, and protects all original text. Use a conservative continuous transform-envelope proof, then dense rendered-frame seam/duplicate/text audits. Finite sampling alone is not a mathematical proof of all intervening poses. The reader validates asset hashes and approved envelope metadata before enabling a layer; runtime interaction must stay inside that same envelope. No extra motion outside it is authorized by `depth`.
- If the proof/visual audit fails, omit the layer and retain a review reason. If bytes/hash fail at playback, disable that layer, show the reason, and continue the original camera-only view. No inpainting, generated fill, background replacement or whole-page zoom is substituted for successful character-depth acceptance.

**Feasibility remains open:** hidden background is absent from scans. A cutout alone can expose the old silhouette or double limbs. This proposal defines safe transport; it does not demonstrate clean depth on a real panel. M4c1 must find real eligible panels and M4c2 must show convincing depth. An all-panel rejection leaves F01 unmet and requires a further concrete proposal; it is not a completion result.

## Camera easing and remaining motion work

For normalized `u` in [0,1]:

```text
outExpo(u) = (1 - 2^(-10*u)) / (1 - 2^(-10))
outBack(u) = 1 + 2.70158*(u-1)^3 + 1.70158*(u-1)^2
rect(u)    = from + (to-from)*ease(u)   # per coordinate
```

The normalized exponential reaches both endpoints continuously. `outBack` peaks at about 1.1000, so its intermediate overshoot must be included in camera/text/scale bounds; endpoint checks alone are insufficient. The solver audits extrema and sustained derivatives, with only the existing short-punch comfort exception. If the overshoot cannot preserve art/text/comfort constraints, use a safe bounded recipe and record why. Reduce motion disables both.

M3b's semantic chase direction/blur, earned action transitions, radial accent and demonstrated real voiced speaker-follow remain refinements. Direction can be encoded in solved camera endpoints without adding a contract vector. Shared reader/export effect functions can derive a restrained blur from existing keyframes/beat metadata; their exact implementation and evidence remain future work, not delivered by this proposal.

## Versioning, migration and streaming

1. Keep v1 schema/types/parser immutable. Version dispatch accepts explicitly supported 1 or 2; unknown versions produce a clear unsupported-version message.
2. After approval, promote the draft schema to its production path/ID, derive consumer types from that artifact using a verified/pinned tool, implement provider serialization and consumer validation against it, then wire feature output. Do not maintain another hand-written payload authority.
3. Pure flat promotion is a deep copy, `version:1 -> 2`, plus `scenes:{}`. No new panels, assets, layers, events or timing. Reversing only this flat promotion is lossless. Enriched v2 cannot be silently downgraded; keep the original saved v1 snapshots rather than stripping music/layers/eases.
4. Whole chapter and streaming prefix each contain every referenced scene and asset. Publish a used scene's immutable bed metadata before its first panel; later appends may add scene IDs but cannot change previously referenced entries or completed pages. Review corrections produce a new immutable snapshot and a visible reopen requirement if the existing prefix differs.
5. Snapshot/API/PWA/export asset collection adds the three roles explicitly; hashes, role directories, filenames, source integrity and D-drive write rules remain enforced. Asset requests cannot fetch arbitrary paths, URLs, `.env` or caches. Full-volume export and offline replay use the same validated script; preparation audits stay private sidecars, not required hidden playback instructions.

## Concrete examples and verification

The draft and fixtures are under `schema/proposals/`:

- `v2-flat.example.json`: flat v1-equivalent chapter.
- `v2-music-depth.example.json`: two adjacent panels sharing one scene; two beds and one character layer.
- `v2-spring.example.json`: proposed spring easing.
- `verify-v2.mjs`: pinned AJV shape checks, shared common-geometry checks, invalid-path/reference/loop/motion/hash cases, easing overshoot check and v1 preservation/flat round trip.

**The files, page, mask and hashes in these examples are structural placeholders. No example audio/mask exists, no real coverage proof was measured, and these fixtures must not be presented as playable music/depth.** The production validator intentionally rejects them as v2.

```powershell
. .\scripts\enter-runtime.ps1
node schema/proposals/verify-v2.mjs
# Optional real-script flat migration checks; reads without rewriting chapters:
node schema/proposals/verify-v2.mjs library/golden-m1d/chapter/motionscript.json library/preview/m0b/motionscript.json
```

## Implementation affected after approval

| Slice | Modules / evidence |
|---|---|
| M3d2 | `pipeline/adapters/music.py`, `pipeline/audio/{music_library,music_cues}.py`, cached scene assets/provenance; structural schema/type/dispatch and snapshot role support before publication. |
| M3d3 | `reader/src/{music,mixer,player}.ts`, common timing/seek functions, per-bus controls and mix tests; actual music/ambience continuity/duck/headroom/listening evidence. |
| M4c1 | `pipeline/adapters/segmenter.py`, `pipeline/layers/{masks,integrity,poses}.py`, source hashes/conservative pose proof, text protection and real-panel audits. |
| M4c2 | `reader/src/{parallax,depth-controls,camera}.ts`, mask/original-texture rendering, source/pose guards, Reduce motion and actual perceived-depth/device evidence. |
| M5a/c | Explicit bed/mask offline assets, shared frame/pose/seek/effect functions and reader/export parity. |

## Requested approval

Approve **MotionScript v2 exactly as proposed above and in the draft schema**: persistent local music/ambience beds, original-source character layers with bounded verified poses, and `outExpo`/`outBack` camera easing. This approval permits the corresponding provider/reader implementation; it does not waive source-art rules, device limits, real depth/audio evaluation or future contract approvals.

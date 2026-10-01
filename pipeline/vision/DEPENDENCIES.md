# M1b verification record

Verified 1 October 2026 before inference. No downloads, dependency upgrades, new weights, new API providers or credentials were used. User has already confirmed personal use and waived a licensing approval concern; license facts remain recorded for provenance.

| Adapter | Immutable pin / install | License and current docs | Previously measured device peak |
|---|---|---|---:|
| Magi v3 detection | `c9d0a345b07be759be61c5cd9570ce2df73ee80b`; `.runtime/cache/huggingface/hub/models--ragavsachdeva--magiv3/snapshots/<revision>` | [Current model card](https://huggingface.co/ragavsachdeva/magiv3/blob/main/README.md) allows personal/research/noncommercial use. Older upstream repository's research-only language was documented in M0. The current card is a later documentation revision; retain verified weight/code pin. | 2,145 MiB |
| Baberu ONNX, FP16 vision + INT8 decoder | `d9cc13153e9a1cd8fdfa3b7b1cc329da2020aeae`; `.runtime/cache/huggingface/hub/models--genshiai-daichi--baberu-ocr/snapshots/<revision>` | [Current card/README](https://huggingface.co/genshiai-daichi/baberu-ocr), local full README and `LICENSE` read. Apache-2.0 code/weights. Author documents one detected crop per call; published ONNX greedy decode and preprocessing retained. | 395 MiB after Magi unload |

All four weight-file SHA-256 values rehashed successfully against `pipeline/model_manifest.json`. Install roots, version pins and CPU/CUDA providers were checked. Runtime versions unchanged: Python 3.11.9, Torch 2.4.1+cu121, Transformers 4.45.2, ONNX Runtime GPU 1.20.2, Pillow 10.4.0, NumPy 1.26.4, Hugging Face Hub 0.36.2. New measured peaks and times: `reports/M1b.md`.

Pinned source files reviewed:

| File | SHA-256 |
|---|---|
| Magi `modeling_florence2.py` | `1f96fe814deaaf251c9a8d97ccad27430f80bc12ea8934afdfa835615a79a93e` |
| Magi `processing_florence2.py` | `98dfe5335b62f811ae37c04b2c48f02c54e725c362fdbd8e6503d8a1cd79947e` |
| Magi `utils.py` | `c4550b748f82318fcbede5be6cb8a87365e450432f3cecc797c401b3cb1c5fd7` |
| Baberu `onnx_infer.py` | `1a7737e6583715be2359807bda92f53ea16091ed186569c7a85f8b82d294373f` |

Magi's verified `predict_detections_and_associations` returns generated boxes, thresholded essential flags, associations and clusters. It does **not** call `utils.sort_panels`, expose calibrated detection/OCR probabilities, or distinguish dialogue/caption/SFX/sign. No invented API/keyword was added. Upstream `sort_panels` iterates graph cycles and geometric erosion; M1b uses an independent bounded cut solver with explicit ambiguity flags instead of invoking that potentially costly helper.

Baberu's verified `BaberuOnnxOCR.__call__` takes a single image crop and `max_new_tokens`, `repetition_penalty`, `max_content_run`. It returns text, not calibrated confidence. Existing tested 4-thread CPU decoder, no worker spinning, and CUDA vision arena configuration remain unchanged. No claimed batch interface or hidden confidence output is invented. English tall-crop splitting retains all crop pixels; JP/Chinese routes still require their own evaluation.

Magi loading is local-only and pinned. Baberu loading is also local-only and pinned. Scheduler enforces stage load/run/unload/CUDA clear and OS-wide heavy-model exclusion. Library import/analysis uses a separate lock to prevent publication races. CPU normalization and metadata adapters allocate no model.

Windows power telemetry uses the read-only [`GetSystemPowerStatus` structure](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-system_power_status): AC `0` offline, `1` online, `255` unknown. It is diagnostic metadata, not a setting change. Power queries added after the initial cold run; battery status was observed after that run, so no exact cold-run power attribution is claimed.

# Part B laptop gaze-target prototype

**November 4 physical prototype update:** actual INMO AIR2 → CPH2611 Android phone → laptop video and local MTGS inference now work over PAL3.0. A 114.5-second physical walking recording (640 × 480, 916 encoded frames at 8 fps) and native report screenshots are saved locally. Twelve prospective stationary PAL3.0 trials saved 24 measured minutes, with 7.455 fps received and 7.273 fps inferred. Two preliminary optional pacing checks approached 8 fps capture/receive and 7.60 fps inference. These results and latency/traffic tradeoffs are under `Bonus-PartC/` and `Bonus-PartD/`. This establishes physical operation under the tested conditions; it does not establish gaze accuracy, all-scenario 8 fps delivery, full Part C coverage, or the required in-class demo. No `BONUS-PartB` completion tag is claimed. The October 21–22 downloaded-video and simulated-relay results below remain separate evidence.

## October 22 speed and resolution update

The viewer now has an **MTGS input** selector (224 × 224 or 448 × 448). Choose a resolution and click Apply settings while inference is running. The incoming camera/video resolution and 224 × 224 head crops are unchanged. Applying a resolution change invalidates the current overlay and in-flight result before publishing predictions in the new setting. The same control works with file input or a phone relay. Runtime inference logs record the selected settings and precision for each processed frame.

CLI options are `--scene-size 224|448` and `--precision float32|float16`; defaults remain the native 448/FP32 reference. FP16 is currently supported on MPS only and affects MTGS, while the head detector stays FP32. Changing precision requires restarting the runner. Non-finite model output is rejected. **224 is reduced-resolution inference with the existing 448 checkpoint, not a separately trained 224 checkpoint**; published 224-model accuracy must not be attributed to this configuration.

MTGS now warms model shapes for one through four detected heads before opening the interactive viewer. Previously, an unseen head count could trigger seconds of GPU compilation during playback. New resolutions or more than four configured heads may still cause initial shape warm-up delays. Offline validation exposes `--warm-all-head-counts` to record this startup separately. The worker uses fixed-cadence scheduling to avoid accumulating receive/scheduler jitter and keeps latest-frame buffering under overload.

Measured **full decoding + head detection + gaze + rendering + video write** times, four-head maximum, after all-count warm-up:

| Configuration / clip | Actual offline processing fps | Mean / p95 processing ms | Samples over 125 ms |
| --- | ---: | ---: | ---: |
| 224 / FP32, classroom | **11.66** | 79.8 / 90.5 | 0 / 105 |
| 224 / FP32, walking | **28.14** | 34.7 / 66.2 | 1 / 488 |
| 448 / FP16, classroom | **10.16** | 92.8 / 103.0 | 0 / 105 |

Walking includes 269 no-head samples; its head-containing frames averaged 58.4 ms (p95 66.6 ms). Its one outlier was approximately 218 ms. These are finite downloaded-video runs, not an across-scenario 8 fps guarantee. Videos remain encoded at 8 fps independently of these throughput numbers.

Compared with the original 448/FP32 predictions on identical classroom samples and the same 354 matched heads, 224/FP32 agreed on in/out classification **78.53%** of the time. Its mean heatmap-peak shift was 0.1026 in normalized x/y coordinates. On walking it agreed on in/out **96.55%** of the time across 348 heads. Out-of-frame peaks can be arbitrary and should not be treated as valid target locations. 448/FP16 agreed on in/out **100%** on classroom, with mean absolute in-frame score change 0.00056 and mean peak shift 0.00145. This is agreement with a reference prediction, **not ground-truth accuracy**. Keep 448/FP16 as a promising detail-preserving option; evaluate both settings with annotated glasses footage before choosing a final deployment setting.

The official MTGS `main` commit and static VSGaze checkpoint revision were checked on October 22 and still match our pinned versions. This is the updated DINOv2-based static model, not the original paper's older backbone. The official temporal checkpoint is a separate model, not enabled here.

Reproduce the 224 run and launch the selectable viewer:

```sh
.tools/gaze-env/bin/python laptop-viewer/gaze_video.py \
  --video output/part-b/inputs/classroom.mp4 \
  --output output/part-b/224-recheck --scene-size 224 --warm-all-head-counts \
  --source-url https://raw.githubusercontent.com/yakhyo/gaze-estimation/main/assets/in_video.mp4

.tools/gaze-env/bin/python laptop-viewer/gaze_viewer.py \
  --video output/part-b/inputs/classroom.mp4 --loop --scene-size 224

# The same inference path with the phone relay and the detail-preserving FP16 option.
.tools/gaze-env/bin/python laptop-viewer/gaze_viewer.py \
  --source http://PHONE_IP:8081 --scene-size 448 --precision float16
```

To reproduce the half-precision offline benchmark, use `--scene-size 448 --precision float16 --warm-all-head-counts`. Timing and per-frame prediction artifacts are under `output/part-b/optimization-2026-10-22/`; summaries and prediction comparisons are tracked under `docs/evidence/part-b-*-2026-10-22.json`. Use `tools/compare_gaze_predictions.py --reference BASELINE_FOLDER --candidate NEW_FOLDER --output comparison.json` for matched-sample agreement checks.

The updated 224 simulated-relay integration received 161 frames and completed **160 inferences in 20.005 seconds (~8.00 fps)**. Resolution switching, pause/resume, stop, disconnect clearing and reconnect all passed. One frame was skipped in the cumulative status (including test startup/session-loop effects); the pipeline remains bounded. This is downloaded-video software simulation, not physical network or glasses evidence. Six Part B unit/integration tests passed after these changes.

## Architecture and model

The intended final input is the outward-facing INMO glasses camera, received and relayed by the existing Android phone app. **All AI inference runs locally on the laptop.** Phone-side inference is future work. No changes to the Part A apps, protocol, viewer or transport were required.

`gaze_viewer.py` accepts either `--video` or `--source`. Both inputs publish into the same latest-frame `Hub`; the same worker and model process its JPEG frames. There is one input frame slot, one inference operation and one annotated result slot. The worker targets at most 8 fps, consumes the newest available frame and counts skipped input frames. It does not accumulate a queue when inference takes longer than 125 ms. The viewer receives the exact annotated image associated with each prediction, rather than drawing an older prediction on a newer raw image.

The default model is **MTGS `mtgs-static-vsgaze`**, from the [official Idiap repository](https://github.com/idiap/MTGS). The downloaded checkpoint matches its current DINOv2 architecture with strict state-dictionary loading: 448 × 448 scene input, 224 × 224 head crops, no temporal context. The adapter uses the official preprocessing, normalization and dummy-person token convention. DINOv2 architecture is created without downloading separate pretrained weights; the MTGS checkpoint supplies all network weights. Static inference requires no future video frames or person tracker.

Head detection uses **YOLOv5m CrowdHuman**, as in the official demo. The original Google Drive download was unavailable; a [pinned public mirror](https://huggingface.co/MK-CUPIST/crowdhuman_yolov5m/tree/ed73865c731033a1b48f61de3894f074e2acf4e1) supplies the checkpoint. The script selects the `head` class, filters tiny boxes, expands boxes by 10% and squares crops. The default settings retain up to four largest heads above confidence 0.6. This may omit other people; displayed indices are frame-local ranks, not tracked identities.

MTGS predicts a target heatmap and an in-frame score per head. A score ≥0.8 is displayed as an estimated in-frame target with an arrow and circle; otherwise it is labeled out-of-frame, with its gaze-vector arrow. Only the largest head's heatmap is blended into the video; **every selected head's full heatmap, peak, vector, box and in/out score is saved** in `frames.jsonl`. These are estimates, not exact fixation locations or calibrated probabilities. They do not measure the glasses wearer's gaze. Accuracy on glasses footage has not been evaluated.

The optional **MobileGaze MobileOne-S0 / Gaze360 + RetinaFace MobileNet-0.25** baseline outputs direction angles, not scene targets. Select it with `--model mobilegaze`; it is not the primary deliverable.

## Setup and downloaded inputs

From `Bonus_Project/`, with `uv`, `git`, `curl` and `shasum` available:

```sh
sh tools/setup_gaze.sh
```

The script installs Python 3.12 into `.tools/`, syncs `tools/gaze-requirements.lock`, checks out pinned MTGS/DINOv2 revisions, and downloads and verifies model/video checksums. Downloads, environments, videos and raw inference results remain outside Git. The MTGS checkpoint is approximately 1.7 GB including training state. Models need no network connection after setup. The first RetinaFace initialization downloads its checksum-verified model into `.tools/gaze-models` for the optional baseline. The H.264 writer and Apple MPS GPU were verified on this Mac; availability/performance on other platforms is not established. Use `--device cpu` to force CPU inference.

Public videos:

| Input | Source and credit | Original duration / fps |
| --- | --- | --- |
| `output/part-b/inputs/classroom.mp4` | [MobileGaze input sample](https://github.com/yakhyo/gaze-estimation/blob/main/assets/in_video.mp4); upstream credits [Yan Krukau / Pexels](https://www.pexels.com/video/male-teacher-with-his-students-8617126/) | 13.16 s / 25 fps |
| `output/part-b/inputs/walking.mp4` | [OpenVINO public demo test video](https://storage.openvinotoolkit.org/data/test_data/videos/face-demographics-walking.mp4) | 61 s / 12 fps |

Model sources: [MTGS checkpoint](https://huggingface.co/Idiap/mtgs-static-vsgaze/tree/dc0e35b2f37bd594cccdd5177ea9317a6e131d02), [MTGS code](https://github.com/idiap/MTGS/tree/a2ce45f44ed73d86e89e16bffb6be7a9567e3052), [DINOv2](https://github.com/facebookresearch/dinov2/tree/7764ea0f912e53c92e82eb78a2a1631e92725fc8), [MobileGaze](https://github.com/yakhyo/gaze-estimation), [UniFace](https://github.com/yakhyo/uniface). MTGS code is GPL-3.0-only and its checkpoint is CC-BY-NC-4.0; YOLOv5 source has GPL licensing, DINOv2 uses Apache-2.0. Preserve upstream attribution and consult their licenses before redistribution. No pretrained weights or source clips are added to Git.

## Reproduce offline video validation

Each output directory must be new; choose another name to preserve previous runs.

```sh
.tools/gaze-env/bin/python laptop-viewer/gaze_video.py \
  --video output/part-b/inputs/classroom.mp4 \
  --output output/part-b/mtgs-classroom-recheck \
  --source-url https://raw.githubusercontent.com/yakhyo/gaze-estimation/main/assets/in_video.mp4

.tools/gaze-env/bin/python laptop-viewer/gaze_video.py \
  --video output/part-b/inputs/walking.mp4 \
  --output output/part-b/mtgs-walking-recheck \
  --source-url https://storage.openvinotoolkit.org/data/test_data/videos/face-demographics-walking.mp4
```

Input timestamps select 8 samples per second, without running inference on intervening source frames. Each output folder contains `annotated.mp4`, `frames.jsonl`, `summary.json`, and preview JPEGs. Every output video was decoded completely and its frame count checked. Source/model hashes and runtime configuration are included in the summary. All saved videos are H.264 at **8 encoded fps**.

Timing definitions:

- `pipeline_ms`: head detection, preprocessing, synchronized gaze inference, postprocessing and heatmap/arrow rendering. GPU execution is synchronized before timing completes.
- `processing_ms`: additionally includes input video decoding (including skipped source frames since the prior sample), HUD drawing and the output video write call. Writer finalization overhead is included in wall time.
- `actual_processing_fps`: sample count divided by the timed whole processing loop and writer finalization, including JSON serialization/writes. Model construction and one warm-up frame are excluded; `warmup_s` is recorded separately. This is an offline throughput measurement, not a measured live display refresh rate.
- Receiver `local_receive_to_result_ms`: laptop receive time to annotated JPEG completion; includes laptop scheduling/processing, and excludes glasses capture, Wi-Fi and phone transit. No end-to-end glass-to-display latency is claimed.

Initial October 21 MTGS results on this Mac, MPS, native 448/FP32, four-head maximum (before the optimizations above):

| Input | Samples / with heads | Actual offline fps | Full processing mean / p95 | Head-containing frames mean | Frames over 125 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Classroom | 105 / 105 | **4.34** | 224.3 / 218.8 ms | 224.3 ms | 105 / 105 |
| Walking | 488 / 219 | **13.00** | 75.9 / 167.7 ms | 149.7 ms | 219 / 488 |

The classroom mean exceeds its p95 because the maximum was 1.75 s. Initial GPU shape compilation can still occur after the single warm-up when the number of detected heads changes; these costs remain included. Walking's aggregate rate benefits from 269 no-head frames, where gaze inference is skipped. **This initial native 448/FP32 configuration did not reliably sustain inference at 8 fps when people were present.** An 8 fps input therefore triggers frame dropping. Optimization or a lighter gaze-target model remains future work; direction-only MobileGaze is not an equivalent replacement.

The optional direction-only baseline measured 29.2 fps offline on classroom (pipeline mean 28.5 ms) and 98.1 fps on walking (pipeline mean 8.6 ms, many no-face frames). These initial baseline processing timings did not charge intervening source-frame decode time to each sample; their whole-loop throughput does include it. The saved baseline results are not MTGS results or target-localization accuracy measurements.

Tracked summaries are under `docs/evidence/part-b-*-2026-10-21.json`; complete annotations/results are local under `output/part-b/`.

## Interactive downloaded-video viewer

```sh
.tools/gaze-env/bin/python laptop-viewer/gaze_viewer.py \
  --video output/part-b/inputs/classroom.mp4 --loop
```

Open `http://127.0.0.1:8000`. Click **Start inference**. Pause/Resume/Stop affect inference; raw input continues while paused/stopped. Apply settings to change target inference rate (0.5–8 fps), maximum heads (1–8) or detector confidence (0.5–0.99). Applying settings invalidates old overlays. Model loading precedes server readiness and Start; Stop retains weights for quick restart. Ctrl+C closes the viewer and input reader.

The dashboard and controls are loopback-only. No video, model outputs or pairing codes are sent to external AI services. Inference results have source session/frame identity; the phone pairing code never enters the browser or logs. JSONL inference logs and Part A-format input traces are written under `data/raw/` by default (`--log-dir` changes it).

## Switch to the final glasses stream

When the glasses are available, start the unchanged Part A glasses and Android receiver apps. Confirm video on the phone and use the **phone relay address and phone pairing code**:

```sh
.tools/gaze-env/bin/python laptop-viewer/gaze_viewer.py \
  --source http://PHONE_IP:8081
```

Enter the phone code at the terminal prompt and click Start inference in the same dashboard. The engine is identical to file mode. Optional USB forwarding for debugging remains available using the Part A README instructions.

If the source disconnects or stalls, its raw frame and overlay expire after at most the existing 2.5 s freshness limit. A receiver clear invalidates in-flight results immediately, even if reconnect reuses the same camera session. A session change, pause, stop or settings change prevents an old inference result from reappearing. Reconnection consumes fresh input through the same receiver.

The existing Part A viewer remains available independently:

```sh
python3 laptop-viewer/viewer.py --source http://PHONE_IP:8081
```

## Verification and remaining validation

```sh
# Original Part A tests; Python standard library only.
python3 -m unittest discover -s tests -p test_streaming.py -v
# Optional Part B tests: race handling, bounded overload, freshness and controls.
.tools/gaze-env/bin/python -m unittest discover -s tests -p test_gaze.py -v
# Actual MTGS with a paced 8 fps downloaded-video source and authenticated MJPEG relay.
.tools/gaze-env/bin/python tools/validate_gaze_stream.py
```

The initial October 21 validation passed 10 original Part A tests, including Java interoperability, and five Part B tests. Its native 448/FP32 simulated relay integration passed Start, Pause/raw fallback, Resume/settings, Stop, disconnect clearing and reconnect with a fresh source session. During an 8.005 s interval it received 64 frames and processed 39 (~4.87 fps); old frames were dropped rather than queued. This historical result is superseded by the October 22 optimized-mode results above. Initial outputs remain under `output/part-b/stream-validation/`.

Still pending: gaze-target accuracy against annotated ground truth, systematic motion/lighting/occlusion evaluation, broad warm-device and network conditions, and the required in-class demo. The November 4 physical stream and recording now supplement the downloaded-video prototype. See `Bonus-PartC/README.md` for the current field-evaluation scope and outstanding 5G/scenario requirements.

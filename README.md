# CS536 Smart Glasses: gaze estimation

Glasses camera → Android phone relay → laptop head detection and gaze estimation → annotated laptop viewer. **All inference runs locally on the laptop.** The phone receives and relays video.

## Clone and prerequisites

```sh
git clone https://github.com/sashanksilwal/automatic-octo-dollop.git
cd automatic-octo-dollop
```

Use Python 3.12 for gaze inference, `uv`, `git`, `curl`, and `shasum`. Building Android apps also requires JDK 17, Android SDK platform 35 and build-tools 35.0.0. The checked-in Gradle wrapper selects Gradle 8.11.1. On a fresh machine, install these prerequisites and set `JAVA_HOME` and `ANDROID_HOME`. On the development laptop, scripts discover the ignored `.tools/` installations automatically. Initial dependency and model setup requires Internet access and several GB of free space; complete it before class.

Apple MPS is the measured inference backend (Apple M5, 24 GiB RAM). `--device cpu` is available on other machines, but its speed has not been validated at 8 fps.

## Part B: run without glasses

From the cloned repository root:

```sh
sh tools/setup_gaze.sh
.tools/gaze-env/bin/python laptop-viewer/gaze_viewer.py \
  --video output/part-b/inputs/classroom.mp4 --loop \
  --scene-size 224 --device auto
```

Wait for model loading and head-count warm-up, then open **http://127.0.0.1:8000/** and select **Start inference**. Use Pause/Resume, Stop and Apply settings to control inference. Scene input is selectable between **224 × 224 and 448 × 448 pixels**; this is distinct from camera stream resolution. The worker retains the newest frame and drops old work if processing falls behind. A missing or stale stream clears the overlay.

For an annotated video, per-frame predictions and timing:

```sh
.tools/gaze-env/bin/python laptop-viewer/gaze_video.py \
  --video output/part-b/inputs/classroom.mp4 \
  --output output/part-b/classroom-check --fps 8 \
  --scene-size 224 --device auto --warm-all-head-counts \
  --source-url https://raw.githubusercontent.com/yakhyo/gaze-estimation/main/assets/in_video.mp4
```

Choose a new output directory for each run. Encoded output is 8 fps; actual processing throughput and latency are reported separately. See [Part B configuration and sources](docs/PART_B.md) for exact settings, input/model pins and result interpretation.

## Part B: run with glasses and the phone relay

1. Enable USB debugging on both devices and approve the laptop. Obtain their current serials with `adb devices`; do not assume the loaner kit has the development unit's serial.
2. Build the Android apps:

   ```sh
   sh tools/build.sh
   ```

   This writes `output/apk/cs536-glasses-debug.apk` and `output/apk/cs536-phone-debug.apk`.
3. Install using the serials from step 1:

   ```sh
   adb -s GLASSES_SERIAL install -r output/apk/cs536-glasses-debug.apk
   adb -s PHONE_SERIAL install -r output/apk/cs536-phone-debug.apk
   ```

   Both apps support API 23+. The real tests used AIR2 Android 9 glasses and an Android 14 relay phone. For isolated installations alongside the original Part A app, build with `./gradlew -Pcs536ApplicationIdSuffix=.partb :glasses-app:assembleDebug :android-app:assembleDebug` and install the resulting APKs from each module's `build/outputs/apk/debug/` directory.
4. Join a network where the glasses, phone and laptop can reach each other. For PAL3.0 certificate-aware setup, follow [the saved checklist](docs/PAL3_DEMO.md). Network addresses may change after reconnecting.
5. Open **CS536 Glasses**, grant camera permission, select camera 0, 640 × 480 pixels, 8 fps, JPEG quality 65 and rotation 0. Select **Start camera stream**. Keep the glasses capture app visible.
6. Open **CS536 Receiver**, allow notifications, enter `http://CURRENT_GLASSES_IP:8080` and the glasses' displayed pairing code. Select **Connect and relay**. Check moving phone video and note the phone's separate pairing code.
7. Start the laptop viewer against the **phone** address:

   ```sh
   .tools/gaze-env/bin/python laptop-viewer/gaze_viewer.py \
     --source http://CURRENT_PHONE_IP:8081 --scene-size 224 --device auto
   ```

   Enter the phone pairing code when prompted. Open **http://127.0.0.1:8000/** and select **Start inference**. Both file and live input use the same inference pipeline.

The updated phone relay continues through app switching and screen lock after connection. Stop it from the app or running notification. Swiping the phone app out of Recents intentionally stops the relay. The glasses capture app still needs to remain visible. See [stability validation](docs/STREAMING_STABILITY.md). USB was used for setup, power and logs, not video, in the physical field trials.

For the original video-only laptop viewer, use `python3 laptop-viewer/viewer.py --source http://CURRENT_PHONE_IP:8081`. Part A functionality remains available independently.

## Checks

```sh
sh tools/check.sh
.tools/gaze-env/bin/python -m unittest discover -s tests -v
python3 -m unittest discover -s Bonus-PartC -p 'test_*.py' -v
```

`check.sh` builds both apps, runs Android lint and Java tests, compiles the shared Java relay harness, and runs Python regressions. Without Android/JDK tooling, `python3 -m unittest discover -s tests -v` runs the standard-library tests; optional ML and unbuilt Java interop tests are skipped. Run the gaze-environment command above for the ML control/scoring tests. Hardware checks and downloaded-video benchmarks are separate evidence.

## Part C: evaluation and results

- [Field collection, verification, analysis and plotting](Bonus-PartC/README.md)
- [Cellular-hotspot/Cloudflare route and reproduction](Bonus-PartC/CELLULAR_TESTS.md)
- [Labeled public-data accuracy protocol](docs/GAZE_ACCURACY.md)
- [Existing screen-to-screen latency evidence](Bonus-PartC/LATENCY_TEST.md)

Baseline field evidence totals **66 measured minutes**: 12 stationary PAL3.0 runs (24 minutes), 16 stationary cellular-hotspot runs (32 minutes), and 20 non-overlapping thirty-second walking tests from two five-minute PAL3.0 sessions (10 minutes). Session grouping and interruptions are retained. The cellular route includes hotspot Wi-Fi, cellular uplink, Internet and Cloudflare; the 5G indicator is operator-observed. It is not an isolated 5G-radio benchmark. Actual cellular receive/inference throughput is 7.27/7.09 fps.

The fixed 500-frame public test subset provides accuracy scores; it does not label the glasses footage. Three stopwatch samples provide preliminary display delay, not a calibrated latency distribution. Derived results are in `results/`; raw traces are retained locally for inspection on request.

## Part D: capture pacing

[Implementation and initial evaluation](Bonus-PartD/README.md), [comparison protocol](Bonus-PartD/MATCHED_PROTOCOL.md), and [completed comparison results](results/part-d/5g-matched-side-2pairs-2026-11-18/README.md). Four separate 120-second runs form two counterbalanced pairs. Absolute scheduling improves capture pacing; changing head workloads and WAN conditions limit causal interpretation of receive/inference and latency differences.

## Submission and demo

The public repository URL is the code submission for **November 30, 2026**. The final report and slides are due on Gradescope **December 4**; five-minute presentations with a mandatory Part B demo take place **December 7 and 9**. The class demonstration is still pending. Complete laptop/projector and shared-kit setup rehearsals before class. Current report, slides, recordings, SDKs, model files and credentials remain outside Git.

The intended five-minute sequence is: explain the Part B goal and demo (30 seconds), demonstrate actual glasses input and runtime controls (two minutes), summarize C/D results and limitations (two minutes), and allow 30 seconds for transitions. Preload the model before receiving the shared kit; practice installing, joining Wi-Fi and connecting the fresh device addresses within three minutes. Detailed demo setup: [PAL3 checklist](docs/PAL3_DEMO.md).

## Source map

| Directory | Role |
| --- | --- |
| `glasses-app/` | Glasses capture and runtime controls |
| `android-app/` | Phone preview, foreground relay service and controls |
| `android-common/`, `stream-core/` | Shared UI and transport |
| `laptop-viewer/` | Raw viewer, gaze engine, bounded worker and offline runner |
| `Bonus-PartC/`, `Bonus-PartD/` | Field evaluation and pacing comparison |
| `tools/`, `tests/` | Setup, fixtures and regression checks |
| `results/`, `docs/` | Derived results, protocols and measured evidence |

## Technical references

- [INMO AIR2 native SDK guide](https://gitee.com/inmolens/docs/blob/master/README.en.md): documents Android Camera1 access with camera ID 0 and touchpad key events. Our implementation uses Android APIs, not copied vendor sample code or the AR/SLAM SDK.
- [INMO developer portal](https://developer.inmolens.com/): confirm AIR3 setup and firmware-specific behavior when selecting hardware.
- [Android Camera1 guide](https://developer.android.com/media/camera/camera-deprecated/camera-api): preview callbacks, buffers, permissions, and camera release. Camera1 is deprecated; it is isolated in `CameraCapture` because the AIR2 documentation explicitly recommends that interface. AIR3 may require adapting this class.
- [AGP 8.9 compatibility](https://developer.android.com/build/releases/agp-8-9-0-release-notes): pinned build-tool requirements.

# Part A validation

## Physical device setup - October 5, 2026

- Pixel 5 detected over USB, running Android 11 / API 30.
- Receiver debug APK installation succeeded.
- `edu.purdue.cs536.phone/.PhoneActivity` launched successfully; its process was running after launch.
- INMO AIR2 detected after USB reconnection; Android 9 / API 28, firmware `Air2_BU_V2.7.030_Release_202308142032`. Developer access was already enabled.
- Camera ID 0 successfully captured the outward-facing RGB view at 640 x 480. Requested settings: 8 fps, JPEG quality 65, rotation 0.
- AIR2 and Pixel connected to `IPhone-sashank` at 5745 MHz. Wireless path: AIR2 `172.20.10.3:8080` -> Pixel `172.20.10.2:8081` -> Mac `172.20.10.4`.
- Phone CSV confirmed frames received and displayed. The real Python laptop viewer received those frames and its browser dashboard visibly displayed the camera view. No USB forwarding was active.
- A separate `nc` probe reported `No route to host`, but the Python viewer connected successfully without changing Mac permissions. Do not use that probe alone to conclude the application cannot connect.
- Sustained physical run: **128.352 seconds, 961 laptop frames, 7.479 fps, maximum interarrival gap 164.042 ms**, with zero duplicate frame IDs, missing sequence numbers, or laptop reconnects. Every sampled laptop frame matched the glasses and phone traces in source identity, capture timestamps, JPEG byte count, and dimensions; all 961 also had phone display events. Device clocks were not calibrated, so these are receive statistics, not end-to-end latency measurements.
- Evidence snapshots: `output/verification/hardware-2026-10-05/{glasses,phone,laptop}.csv` and `result.json`. The live laptop trace continues separately under `data/raw/`.
- A copy of the measured hardware summary is tracked at [`evidence/part-a-hardware-2026-10-05.json`](evidence/part-a-hardware-2026-10-05.json). Raw trace snapshots and camera images remain local and excluded from Git.

## Checkpoint verification - October 5, 2026

- `tools/check.sh` completed successfully after the glasses label update and black-and-white laptop UI change.
- Both Android debug APKs built successfully; both lint reports contain zero issues.
- Seven Java tests passed with zero failures/errors/skips. All ten Python tests passed, including the actual Java relay interoperability test.
- The shortened glasses label was installed and visually verified on AIR2. Streaming resumed afterward with a new source session reaching the laptop.
- The black-and-white dashboard was visually verified in the browser while the camera was stopped.
- The later attempt to run controlled recovery tests was paused for charging. Only the Pixel remained available at checkpoint publication, so no further hardware recovery result or recorded demo is claimed.
- Machine-readable software check results and APK checksums are tracked at [`evidence/part-a-checks-2026-10-05.json`](evidence/part-a-checks-2026-10-05.json).

## Completed locally - September 11, 2026

- Both Android debug APKs compiled with AGP 8.9.2, Gradle 8.11.1, JDK 17, and Android SDK 35.
- Both APK signatures verified. Final Android lint reports contain zero issues for both applications.
- Seven Java tests passed: fragmented reads and metadata preservation, oversized/truncated frame rejection, latest-frame storage and session reset, socket authentication/transport, server shutdown, CSV structure, and unsafe metadata/source rejection.
- Ten Python/integration tests passed, including a Python source -> real shared Java relay -> Python receiver. The integration case also checks recovery after an idle disconnection and source restart.
- The laptop dashboard was opened in the browser and visually checked with an animated simulated stream. The image, streaming status, frame count, approximately 8 fps, goodput, and frame age appeared correctly.
- A simulated endurance run through the actual shared Java relay passed: **65.121 seconds, 522 frames received out of 522 generated, 8.001 fps observed, maximum interarrival gap 146.5 ms**. These are localhost software results, not wireless or hardware measurements.

The machine-readable endurance result and CSV are under `output/verification/`. APKs are under `output/apk/`. Build/lint reports and test results are generated inside the corresponding module's `build/` directory. Reproduce with `tools/check.sh`, `tools/build.sh`, and `tools/soak_test.py`.

## Still pending

- Longer warm-device runs, physical touchpad/ring usability, rotation/focus checks, denied-permission recovery, and controlled pause/disconnection tests.
- AIR3 compatibility has not been tested; current physical results apply to AIR2 and Pixel 5.
- PAL3.0 reachability and any cellular experiment topology.
- Physical display timing and clock calibration for latency claims.

This is a Part A implementation checkpoint, not a claim that the required in-class demonstration has occurred. Controlled hardware recovery tests and a recorded demo remain pending, and no `BONUS-PartA` release tag has been created. Use `HARDWARE_CHECKLIST.md` to record the remaining acceptance evidence.

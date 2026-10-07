# CS536 Smart Glass - Part A

Part A implementation: **glasses camera -> Android receiver/relay -> laptop viewer**.

The Android source builds into two debug APKs. The physical INMO AIR2 -> Pixel 5 -> laptop path is verified over 5 GHz Wi-Fi on an iPhone hotspot, without USB video forwarding.

The **BONUS-PartA submission** includes a 128.352-second continuous hardware run at 7.479 fps, successful pause/resume, relay stop/restart, Wi-Fi reconnection and authentication checks, and verified 90-second phone and laptop recordings. Both builds, Android lint, seven Java tests and ten Python/integration tests passed. See [`docs/VALIDATION.md`](docs/VALIDATION.md) for measured evidence and remaining optional checks. The required in-class demonstration is still pending; Part B gaze estimation is not included.

The local submission archive is `output/Bonus-PartA.zip`: source, both APKs, both demo clips, checksums and submission instructions. Camera recordings remain outside Git; GitHub contains the source and evidence summaries. The `BONUS-PartA` tag identifies this submission version.

## What is implemented

- **Glasses app:** camera permission flow, Camera1 capture, selectable camera ID, rotation, JPEG quality and frame rate; start/pause/resume/stop; pairing code; local addresses and trace location.
- **Phone app:** receives and displays the glasses stream, relays the original JPEG frames to the laptop, reconnects after interruptions, clears stale previews, and provides pause/resume/stop.
- **Laptop viewer:** live picture, received frames, receive rate, JPEG goodput, frame age, fullscreen, and CSV traces. Python 3.10+; no pip packages required.
- **Transport:** authenticated HTTP MJPEG, preserved frame identity and source timestamps, bounded frame/header sizes, one latest-frame slot per hop, limited viewer connections, read timeouts and stalled-client cleanup.
- **Development tools:** generated animated camera fixtures, a simulated three-device demo, Java/Python interoperability tests, and an endurance test.

This baseline carries video only. Both Android apps must remain in the foreground; they keep the display awake and stop capture/relay when backgrounded. There is no audio requirement in the Part A handout.

## Try it now without hardware

From this directory:

```sh
python3 tools/demo.py
```

Open **http://127.0.0.1:8000**. The moving test pattern should appear, with approximately 8 received frames per second. Ctrl+C stops all simulated components. This demo simulates the glasses and phone in Python; `tools/check.sh` separately exercises the real shared Java relay used by the phone app.

## Build the Android apps

Prerequisites: **JDK 17**, **Android SDK platform 35**, **build-tools 35.0.0**. The project uses Android Gradle Plugin 8.9.2 and the checked-in Gradle 8.11.1 wrapper with its distribution checksum. Both apps support Android API 23+ at the software level; actual device support must be checked.

On this Mac, project-local build dependencies are already under ignored `.tools/`. The scripts find them automatically. On another machine, install the prerequisites through Android Studio or Android command-line tools, then set `JAVA_HOME` and `ANDROID_HOME`, or set `sdk.dir` in untracked `local.properties` for the SDK.

```sh
./tools/build.sh
```

Outputs:

```text
output/apk/cs536-glasses-debug.apk
output/apk/cs536-phone-debug.apk
```

You can also open this directory in Android Studio and select `glasses-app` or `android-app`. Android Studio may use its bundled JDK if compatible with the pinned build tools. The first Gradle run on a fresh machine needs internet access for build dependencies.

## Install on the physical devices

Enable developer access and USB debugging using the instructions for the actual glasses model. Enable USB debugging on the Android phone. Use `adb devices` to obtain each device's serial number, then substitute it below:

```sh
adb -s GLASSES_SERIAL install -r output/apk/cs536-glasses-debug.apk
adb -s PHONE_SERIAL install -r output/apk/cs536-phone-debug.apk
```

On this Mac, the project-local `adb` is `.tools/android-sdk/platform-tools/adb` if it is not already on `PATH`.

## Run the actual three-device stream

1. Connect glasses and phone to a network on which they can reach each other. A controlled Wi-Fi router or a phone hotspot is a useful first check. Do not assume PAL3.0 permits direct client-to-client traffic.
2. On the glasses, open **CS536 Glasses**. Grant camera permission. Start with camera ID **0**, **8 fps**, quality **65**, rotation **0**, and port **8080**. Select **Start camera stream**.
3. Note the glasses' displayed IPv4 address and pairing code. Multiple addresses may be listed; choose the interface reachable from the phone.
4. On the phone, open **CS536 Receiver**. Enter the glasses base address, such as `http://192.168.1.20:8080`, and the glasses pairing code. Leave the phone relay port at **8081**. Select **Connect and relay**.
5. Confirm the picture appears on the phone. Note the phone's address and its separate pairing code.
6. On the laptop, run:

```sh
python3 laptop-viewer/viewer.py --source http://PHONE_IP:8081
```

Enter the **phone's** pairing code when prompted, then open **http://127.0.0.1:8000**. Using the glasses address here would bypass the phone; use the phone relay for the Part A demonstration.

Open the viewer through that HTTP address. Opening `laptop-viewer/index.html` directly as a file cannot connect its relative `/frame` and `/status` requests to the Python server. The dashboard uses a simple black-and-white layout; the camera image retains its original colors.

7. Stream for more than one minute. The proposed acceptance run is 90 seconds followed by pause/resume and disconnect/reconnect checks. Follow `docs/HARDWARE_CHECKLIST.md` before calling Part A complete.

The stream addresses use ordinary HTTP on a controlled LAN or USB-forwarded link. Pairing codes prevent unauthenticated access but do not encrypt traffic. This version does not provide an internet-facing relay, NAT traversal, or TLS termination. PAL3.0/5G field routing is a later topology task and must not be inferred from a local hotspot test.

## Reliable phone-to-laptop debugging over USB

Keep the glasses-to-phone connection as above. Connect the phone to the laptop by USB:

```sh
adb -s PHONE_SERIAL forward tcp:18081 tcp:8081
python3 laptop-viewer/viewer.py --source http://127.0.0.1:18081
```

Enter the phone pairing code. This still shows video received and relayed by the phone. Remove the mapping after use:

```sh
adb -s PHONE_SERIAL forward --remove tcp:18081
```

## Develop with an emulator or a substitute phone camera

To test the receiver against the simulated glasses:

```sh
python3 tools/simulate.py --port 8080
```

In a standard Android emulator, use source `http://10.0.2.2:8080` and pairing code `demo536`. Install the receiver APK in the emulator. Use adb forwarding from emulator port 8081 to laptop port 18081 to test its actual Android relay with the laptop viewer.

For a physical receiver phone, expose the simulator only on the controlled test network:

```sh
python3 tools/simulate.py --bind 0.0.0.0 --port 8080
```

Use the laptop's LAN address on the phone. `CS536_PAIRING_CODE` overrides the simulator's development code. The camera APK can also be installed on another Android phone as a temporary glasses substitute; adjust camera ID and rotation as needed. These modes are development aids, not evidence of INMO hardware compatibility.

## Logs and measurements

Android apps show their trace path on screen. Traces are under the app's external-files directory, usually:

```text
/sdcard/Android/data/edu.purdue.cs536.glasses/files/traces/
/sdcard/Android/data/edu.purdue.cs536.phone/files/traces/
```

For example:

```sh
mkdir -p data/raw/glasses data/raw/phone
adb -s GLASSES_SERIAL pull /sdcard/Android/data/edu.purdue.cs536.glasses/files/traces/ data/raw/glasses/
adb -s PHONE_SERIAL pull /sdcard/Android/data/edu.purdue.cs536.phone/files/traces/ data/raw/phone/
```

If the vendor firmware prevents pulling external app files, use the debug APK's `run-as` access or Android Studio Device Explorer and verify the exported files. The laptop writes timestamped CSVs under `data/raw/` by default; `--log-dir` changes that location. Raw traces are excluded from Git and need a separate backup.

Each record includes the local event time, source session/frame ID, source capture-callback times, JPEG size/dimensions, and event details. Frame bytes and pairing codes are not logged. There is a new source session on every camera start/resume. The phone forwards source metadata and JPEG bytes unchanged.

Interpretation matters:

- Source capture time is the time of the Android preview callback, **not** a calibrated sensor-exposure timestamp.
- A `frame_sent` event records completion of the application write, not a remote receipt acknowledgment.
- `frame_displayed` on the phone records installing a decoded bitmap for rendering, not a measured physical display refresh.
- Laptop frame age uses its own monotonic clock. JPEG goodput counts received JPEG payload bytes, not IP/TCP overhead or link capacity.
- Cross-device monotonic clocks cannot be directly subtracted. Calibrate offsets or use an externally filmed timer before reporting one-way or glass-to-display latency.

The initial frame rate, resolution, and JPEG quality are configurable baseline choices. MJPEG is simple to inspect but uses more bandwidth than inter-frame video codecs. Rotation of nonzero angles currently adds a bitmap rotation/recompression step on the glasses; measure its cost on hardware.

## Verification

```sh
./tools/check.sh
python3 tools/soak_test.py --duration 65
```

`check.sh` builds both APKs, runs Android lint and Java unit/socket tests, compiles a JVM relay harness from the same transport used by the apps, and runs Python tests including Java/Python interoperability. The endurance test runs a generated source through that Java relay into the Python receiver and writes `output/verification/soak-result.json` plus a CSV trace. Its output is explicitly marked as simulated.

For Python-only checks without Android/JDK tooling:

```sh
python3 -m unittest discover -s tests -v
```

The Java interoperability test is skipped if its compiled harness is unavailable. Do not treat that skip as Android verification.

Checked-in evidence summaries are in [`docs/evidence/`](docs/evidence/). Raw device traces, camera screenshots, generated APKs, and local SDK/build caches stay outside Git. Build the APKs with `tools/build.sh`; consult [`docs/HARDWARE_CHECKLIST.md`](docs/HARDWARE_CHECKLIST.md) for the remaining physical checks.

## Code map

| Directory | Role |
| --- | --- |
| `glasses-app/` | Camera capture and glasses control screen |
| `android-app/` | Phone receiver, preview, and relay control screen |
| `android-common/` | Native UI helpers, bitmap preview, and trace-file creation |
| `stream-core/` | Shared Java protocol, server/client, frame store, and CSV logger |
| `laptop-viewer/` | Python upstream receiver, local browser viewer, and matching protocol |
| `tools/` | Demo source, build/check scripts, and endurance test |
| `tests/` | Python and cross-language tests |
| `docs/` | Protocol and physical-device acceptance procedure |

See `PROJECT_PLAN.md` for the larger A-E plan. This implementation covers Part A; it does not implement Part B AI or claim Part C/D results.

## Technical references

- [INMO AIR2 native SDK guide](https://gitee.com/inmolens/docs/blob/master/README.en.md): documents Android Camera1 access with camera ID 0 and touchpad key events. Our implementation uses Android APIs, not copied vendor sample code or the AR/SLAM SDK.
- [INMO developer portal](https://developer.inmolens.com/): confirm AIR3 setup and firmware-specific behavior when selecting hardware.
- [Android Camera1 guide](https://developer.android.com/media/camera/camera-deprecated/camera-api): preview callbacks, buffers, permissions, and camera release. Camera1 is deprecated; it is isolated in `CameraCapture` because the AIR2 documentation explicitly recommends that interface. AIR3 may require adapting this class.
- [AGP 8.9 compatibility](https://developer.android.com/build/releases/agp-8-9-0-release-notes): pinned build-tool requirements.

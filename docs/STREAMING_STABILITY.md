# Phone relay stability fix — November 18, 2026

The updated phone receiver owns its video relay in a user-started foreground service. Leaving the activity, switching apps, or locking the screen no longer closes the relay. Inference remains entirely on the laptop; the phone forwards JPEG frames and metadata using the existing bounded latest-frame buffer.

The service displays a running notification with a Stop action and holds CPU/Wi-Fi locks only while active. Pause clears the current frame and closes the upstream connection; resume reconnects. Stop releases resources. Swiping the app out of Recents intentionally stops the relay. Start the relay while the app is visible and allow notifications for the running notification and Stop control.

The earlier activity stopped the relay on leaving the foreground. This fixes that verified lifecycle failure path. The exact trigger of the historical walking interruption remains unconfirmed; Wi-Fi coverage and device shutdown can still interrupt video.

## Validation

- Android build, lint, shared Java tests and both Python regression suites passed. The standard Python environment skipped optional ML tests; the gaze environment passed all 26 tests.
- A physical Android lifecycle test passed 34 assertions using a synthetic localhost source, including Home, activity recreation, pause/resume, source outage/reconnection, 120 seconds with the screen off, and notification Stop. It delivered 1,325 frames. This isolates phone lifecycle behavior; it is separate from the real-camera test.
- The final APK includes a subsequent UI refresh correction. It passed the real PAL3.0 glasses → phone → laptop check below. This check used direct Wi-Fi video, with USB only for setup, power and control. All 899 recorded inference results contained detected heads.

| Phone state | Duration | Receive fps | Inference fps |
| --- | ---: | ---: | ---: |
| App visible | 30.35 s | 7.41 | 7.41 |
| Home screen | 30.35 s | 7.45 | 7.41 |
| Screen off | 60.19 s | 7.46 | 7.44 |

There were no sampled non-streaming states, frames older than 2.5 seconds, model errors or camera-session changes. Raw receive traces contain 901 frames, 899 corresponding inference records, and a maximum interarrival gap of 343 ms. Mean face-detection plus gaze/overlay processing was 62.49 ms. The observed delivered throughput is approximately 7.4 fps, below the requested 8 fps; the requested or encoded rate is not the measured throughput. This short check validates background and screen-off behavior, not uninterrupted operation under every network condition.

Evidence is saved locally under `output/verification/relay-background-2026-11-18/`: `instrumentation-clean.txt`, and `live-pal3/{manifest.json,samples.jsonl,glasses.csv,phone.csv,laptop.csv,inference.jsonl,verification.json}`. These checks do not change the historical Part C field-test counts or results. The camera and relay were stopped after collection; laptop inference was paused.

## Reproduce

Install the fixed receiver, open it, allow notifications and connect to the glasses. Start the laptop viewer on the phone relay as described in [PAL3 demo instructions](PAL3_DEMO.md). With fresh live video available:

```sh
python3 tools/validate_phone_relay.py --output output/verification/relay-recheck
```

The check moves the phone to Home and turns its screen off. It wakes the screen afterward; it does not bypass the phone lock. Stop the devices after testing.

Fixed APK: `output/apk/demo-stability/cs536-phone-partb-debug.apk`.
SHA-256: `e5034f874a5fbd5c448d73cec6a309c4d8fc80cf15df4970b9538600564f0e63`.
The local demo preparation launcher is pinned to this APK. Part A application IDs and installed apps remain unchanged.

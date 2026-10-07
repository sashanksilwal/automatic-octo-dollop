# Part A physical-device acceptance

Status: **physical AIR2 -> Pixel 5 -> laptop streaming verified over Wi-Fi; remaining acceptance checks are listed below.**

October 5, 2026: both project APKs were installed and launched on the actual devices. AIR2 developer access was already enabled and USB control worked after reconnection. The earlier missing-device observations were temporary, not evidence that developer mode needed enabling.

The AIR2 (Android 9 / API 28, firmware `Air2_BU_V2.7.030_Release_202308142032`) and Pixel 5 (Android 11 / API 30) joined `IPhone-sashank` at 5745 MHz (5 GHz Wi-Fi). The glasses served `172.20.10.3:8080`, the phone received and displayed its frames and relayed them at `172.20.10.2:8081`, and the Mac at `172.20.10.4` displayed the Python viewer at `http://127.0.0.1:8000/`. USB was used for device control and charging only. This is a local hotspot test, not a cellular video-path measurement.

Record the glasses model/firmware, phone model/Android version, app version, network diagram, IP/interface addresses, camera settings, and code commit before testing.

## Device bring-up

- [x] Enable developer access and install the correct APK on each actual device.
- [ ] Verify glasses UI is legible and the start/pause/stop controls can be reached through its touchpad/ring. The app uses native focusable controls; vendor input mapping is unverified.
- [x] Grant camera permission, launch camera ID 0, and verify it is the outward-facing RGB camera. Try another ID only if the device exposes it.
- [ ] Check actual preview size, orientation, focus, and simultaneous preview/streaming. Adjust image rotation if needed.
- [ ] Deny camera permission once and verify the app explains how to recover without crashing.
- [ ] Check leaving either Android app stops its camera/relay as documented. Return and explicitly restart.

## Three-device stream

- [x] Phone receives directly from the glasses app.
- [x] Laptop receives from the phone relay, not from the glasses or a simulated source.
- [x] Display live camera video on phone and laptop and retain a continuous run longer than 90 seconds: 128.352 seconds, 961 frames, 7.479 fps, no missing sequence numbers or laptop reconnects. All three CSV snapshots are under `output/verification/hardware-2026-10-05/`.
- [ ] Prefer three five-minute runs to check repeated operation and warm-device behavior. This is an internal target, beyond the handout's >1-minute tip.
- [x] Stop the phone relay and confirm the laptop loses fresh video, demonstrating that the phone is actually in the path.
- [x] Pause/resume the glasses and phone separately; verify fresh video returns and old source callbacks do not resurrect a paused session.
- [x] Interrupt and restore the glasses-to-phone link; verify automatic reconnect without restarting the laptop viewer.
- [x] Try an incorrect pairing code and verify rejection; correct it and reconnect.
- [x] Verify no USB video forwarding is active for the wireless demonstration.
- [x] Export traces, verify all CSV rows parse, and match source sessions/frame IDs across the devices. All 961 sampled laptop frames matched both upstream traces and had phone display events.

## October 7 recovery and recording results

Pause/resume, relay stop/restart, Wi-Fi recovery and authentication checks passed. Backgrounding each app cleared the laptop video; restarting the phone recovered in 26.836 seconds. Permission was restored and glasses capture restarted for recording, but the denied-permission interaction was not validated. See `docs/evidence/part-a-recovery-2026-10-07.json`.

- [x] Record and decode-check the phone screen (90.12 seconds) and laptop-received video (90.00 seconds).
- [x] All 90 once-per-second laptop status samples reported streaming in one source session; 666 frames arrived between the first and last samples.
- [ ] Perform the required in-class demonstration.

## Completion record

Write actual observations, durations, failures, and fixes here or in a dated test report. Complete the README with any device-specific setup changes. Only after the physical demo works should the private repository receive the `BONUS-PartA` tag. The `BONUS-PartA` tag identifies the verified implementation and recorded demonstration; it does not claim that the in-class demonstration or every optional check above has occurred.

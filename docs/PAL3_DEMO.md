# PAL3.0 demo reconnect checklist

The AIR2, Android phone and laptop must all have working PAL3.0 connections. All inference stays on the laptop. Use the phone relay as the video source.

## Demo day: fast reconnect after handoff

**Latest handoff state, November 18:** both PAL3.0 profiles were removed again after the final stability test, and removal was verified. Both devices have Wi-Fi off, our camera/relay apps are stopped, the glasses screen is asleep, and laptop inference is paused. Fresh Purdue login is required. The tested APKs and certificate helpers are saved on this laptop. Do not assume the old addresses still apply.

1. Charge the glasses to at least 30%, keep a power bank nearby, and connect both devices to this laptop with data-capable USB cables. Unlock the phone. If prompted, allow USB debugging. The helpers cannot bypass the screen lock or debugging approval.
2. Open a terminal in the project and check that both devices appear as `device`, then enable their Wi-Fi:

   ```sh
   cd /Users/sashank/Developer/fall_2026/cs536/Bonus_Project
   .tools/android-sdk/platform-tools/adb devices -l
   .tools/android-sdk/platform-tools/adb -s YM00DEC8P06371 shell svc wifi enable
   .tools/android-sdk/platform-tools/adb -s c1a1aa06 shell svc wifi enable
   ```

   Current units: glasses `YM00DEC8P06371`, phone `c1a1aa06`. If different hardware is returned, update the helper serials before using these commands.
3. Join PAL3.0 on the laptop. On the phone, open Wi-Fi settings and reconnect using Purdue's PAL3.0 setup/profile and your own login. The last successful phone connection used the university's SecureW2 profile. Keep certificate verification enabled; use Purdue's onboarding flow if its profile needs restoring.
4. Recreate the glasses' verified PAL3.0 profile:

   ```sh
   python3 tools/connect_pal3.py --refresh-login
   ```

   Open <http://127.0.0.1:8765/> and enter your Purdue login directly in the local form. The helper applies PEAP/MSCHAPv2, `purdue.edu` server-domain verification, and both cached CA roots in the Android-compatible PKCS#7 bundle. No certificate download is needed. Passwords are not saved on the laptop. If the form times out, allow DHCP to finish and run `python3 tools/connect_pal3.py` to check again before re-entering credentials.
5. Keep the phone unlocked. Run the connection check and restore the tested camera/relay configuration:

   ```sh
   python3 .tools/demo-side-2026-11-18/prepare_devices.py --check-only
   python3 .tools/demo-side-2026-11-18/prepare_devices.py
   ```

   The launcher discovers current IP addresses, installs only our isolated Part B packages, restores private pairing settings, and starts the glasses camera and phone relay. The phone APK is pinned to `output/apk/demo-stability/cs536-phone-partb-debug.apk`, which includes the background-relay and preview-refresh fixes. Allow receiver notifications in Android settings so its running notification and Stop button are visible. If a notification prompt blocks connection, allow it and select **Connect and relay** again. Confirm moving video on the phone.
6. Start the laptop viewer in a second terminal from the same project directory:

   ```sh
   .tools/gaze-env/bin/python .tools/demo-side-2026-11-18/start_viewer.py
   ```

   Allow model warm-up, open <http://127.0.0.1:8000/>, and select **Start inference**. The launcher refuses to replace a server already on port 8000; if one is still running, stop that project's viewer from its terminal before relaunching with the new addresses. An old viewer may still point to the previous phone address.
7. Before presenting, check fresh moving video, updating arrows on a visible face, no model error, and advancing received/processed frame counts. Target settings are 640 × 480 pixel video, requested 8 fps, JPEG quality 65, 224 × 224 pixel model scene input, FP32, maximum four heads, confidence 0.6. The final PAL3.0 check measured approximately 7.4 inference fps; 8 fps is the request, not a guaranteed measured rate.
8. Only after the check passes, disconnect USB data cables as needed and power the glasses from the power bank. The updated phone relay supports Home and screen lock after starting while visible. Do not swipe it out of Recents, which intentionally stops it. Keep the laptop awake and all devices within PAL3.0 coverage. No Cloudflare bridge or cellular hotspot is needed for this demo.

The two convenience launchers and their private pairing file live under ignored `.tools/demo-side-2026-11-18/`. Keep them on this laptop; a fresh Git checkout alone does not contain them or the cached APKs/model environment. The manual instructions below provide the fallback. See [the final stability checks](STREAMING_STABILITY.md) for test scope and saved evidence. No passwords or pairing codes belong in this checklist.

## Loaner handoff and fast restart

On November 18, the live demo check delivered 7.53 received fps and 7.33 inference fps over 10.23 seconds with no sampled non-streaming state or model error. This is a short readiness check, not a sustained-performance guarantee. The baseline settings remain 640x480 video, requested 8 fps, JPEG quality 65, 224x224 scene input, FP32, four heads maximum and confidence 0.6.

Before giving the devices to another team, the operator requested removal of both saved PAL3.0 profiles. Their removal was verified; our camera/relay apps, inference and local adapter were stopped, and Wi-Fi was switched off on both devices. The APKs, model runtime, public CA certificates and experiment files remain on this laptop. No Purdue password was exported as a backup. Fresh login is required when the devices return.

For the next demo, charge the glasses or use a power bank, reconnect both devices by USB and approve debugging if requested. Join PAL3.0 on the laptop and phone, then use the certificate-aware form for the glasses:

```sh
python3 tools/connect_pal3.py --refresh-login
```

After both devices have PAL3.0 addresses, this laptop also has private convenience launchers prepared from the same setup sequence used in the live check:

```sh
python3 .tools/demo-side-2026-11-18/prepare_devices.py
.tools/gaze-env/bin/python .tools/demo-side-2026-11-18/start_viewer.py
```

The first launcher checks the current SSIDs, discovers both IP addresses, reinstalls only our isolated `.partb` APKs, restores the baseline camera/relay settings and starts them. Pairing values stay in an ignored file with user-only permissions. The second starts local laptop inference using the new phone address. Allow model warm-up, open <http://127.0.0.1:8000/> and click **Start inference**. Check moving video and arrows before presenting. It refuses to replace an existing server on port 8000. Use `prepare_devices.py --check-only` for a read-only connection check.

These convenience launchers are stored locally under ignored `.tools/`; use the manual instructions below on a fresh checkout. Both devices subsequently rejoined PAL3.0, and the updated receiver passed the 121-second live background/lock check documented below. The phone launcher now uses the fixed APK under `output/apk/demo-stability/`. If another team changes our application IDs, signatures or debugging authorization, address that before starting the demo; the helper does not uninstall unrelated apps or bypass authorization.

## Before the demo

1. Charge the glasses and keep a power bank available. Connect the glasses and phone to the laptop by USB for setup. Unlock the phone and accept USB debugging if asked.
2. Join PAL3.0 on the laptop and Android phone. After the loaner handoff, recreate the phone profile with your Purdue login; use a saved profile only if one is actually available.
3. From `Bonus_Project/`, run:

   ```sh
   python3 tools/connect_pal3.py
   ```

   If the glasses are already connected, this prints their current address without changing the profile. Otherwise it compiles the cached helper, verifies both bundled certificate fingerprints, updates **only the glasses' PAL3.0 profile**, and reconnects using its saved credentials. It keeps PEAP/MSCHAPv2 and `purdue.edu` server-domain verification. It does not disable certificate validation or change system-wide trust.

4. If saved authentication still fails, run:

   ```sh
   python3 tools/connect_pal3.py --refresh-login
   ```

   Open <http://127.0.0.1:8765/> and enter your Purdue career-account username and password. The form runs on this laptop, passes credentials to the glasses over USB, clears the password field, and does not log or save the credentials. Android saves its Wi-Fi profile for reconnection. The form is one-use and expires after 15 minutes. Reload it after reopening the helper so the form token is fresh. Never paste credentials into chat, commands or Git.

5. Confirm that the helper reports **connected** and prints a current glasses address. Do not treat a certificate-update message alone as a successful Wi-Fi connection. DHCP can take additional time.
6. Open **CS536 Glasses** on the glasses and start the camera. Open **CS536 Receiver** on the phone. Set the source to `http://CURRENT_GLASSES_IP:8080` and use the glasses pairing code. Select **Connect and relay**. The source address can change after joining a different network.
7. Check moving video on the phone. Connect the laptop viewer to `http://CURRENT_PHONE_IP:8081` with the phone pairing code, then start inference. Use 224 x 224 pixel scene input, FP32, requested 8 fps, maximum four heads and confidence 0.6 for the recorded baseline configuration.
8. Confirm fresh moving video and gaze overlays at <http://127.0.0.1:8000/>. Only then switch the glasses to the power bank and unplug laptop USB cables for walking. Keep the laptop open/awake and both portable devices within PAL3.0 coverage. Use the updated receiver APK at `output/apk/demo-stability/cs536-phone-partb-debug.apk` and allow notifications. After connecting while the app is visible, switching apps or locking the phone is supported. The running notification provides a Stop button. Swiping the receiver out of Recents intentionally stops the relay. The older build used in the November 18 walking pilot stopped its relay when its activity left the foreground; the exact trigger of that historical interruption was not established. See [streaming stability validation](STREAMING_STABILITY.md).

The direct laptop launch command is:

```sh
.tools/gaze-env/bin/python laptop-viewer/gaze_viewer.py \
  --source http://CURRENT_PHONE_IP:8081 --scene-size 224 --device mps
```

Enter the phone pairing code when prompted. An existing running viewer may instead use our local adapter at port 8791: update/restart that adapter with the current phone address and private pairing configuration, rather than starting a second viewer on port 8000. The adapter is entirely local, with no Cloudflare tunnel for PAL3.0.

## Why the certificate fix is needed

On November 18, the glasses reported **unable to get local issuer certificate** when the access point presented `SSL.com TLS Issuing RSA CA R1`. The previously configured emSign root alone could not validate that chain. The repair trusts both verified roots for PAL3.0, retaining server-domain validation. After the repair the glasses completed EAP authentication and received a PAL3.0 address. Old hotspot addresses must then be replaced in the phone source and laptop receiver configuration.

| Certificate | Pinned SHA-256 fingerprint |
| --- | --- |
| emSign Root TLS CA - G1 | `cef71e70b7c29addf6c30cd19e614b38fd5f02a435a0eeddd0087e183d101a51` |
| SSL.com TLS RSA Root CA 2022 | `8faf7d2e2cb4709bb8e0b33666bf75a5dd45b5de480f8ea8d4bfe6bebc17f2ed` |

Public certificates and source helpers are in `tools/pal3/`. The SSL.com root and fingerprint come from the [official CA repository](https://www.ssl.com/repository/), with its [PEM download](https://repo-certs.ssl.com/repo/certs/SSLcom-TLS-Root-2022-RSA.pem). The emSign certificate is the previously fingerprint-verified November 4 setup certificate. Neither certificate contains an account password or private key. For Android's certificate parser, the helper sends both roots in a **PKCS#7 DER bundle**; concatenated PEM input returned only the first certificate on this device.

## Quick troubleshooting

- **Unknown SSID / disconnected:** Wi-Fi has not connected. Keep USB attached and retry the saved-profile command.
- **Unable to get local issuer certificate:** run the certificate-aware reconnect command. Do not select “do not validate.”
- **EAP authentication failed after the certificate repair:** this message alone does not prove the password is wrong. Check the latest failure and, if needed, refresh the saved login through the local form.
- **Phone preview works, laptop reconnects:** check the phone's current PAL3.0 address, relay port/pairing code and whether a previous adapter still points to the hotspot address.
- **Video stops while walking:** keep the phone beside the glasses, check PAL3.0 coverage and retain the gap in measured results. Do not claim that a running inference worker implies fresh video.
- **No USB device:** check the data cable, phone unlock/debugging approval and glasses power.

## Dependencies and offline preparation

This command uses the existing project Android SDK (`android-35`, build-tools `35.0.0`) and JDK under `.tools/`. No certificate download is needed at demo time. Prepare/check the helper without touching devices:

```sh
python3 tools/connect_pal3.py --prepare-only
```

The AIR2 serial is the current project unit (`YM00DEC8P06371`). Update the wrapper and local form together if borrowing another unit. Source helpers and public certificates can be versioned; generated DEX files stay under ignored `.tools/pal3-demo-cache/`. Pairing codes and account credentials remain outside the repository.

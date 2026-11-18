# Cellular hotspot trials

The cellular condition uses an additional iPhone as a hotspot. The AIR2 glasses
and Android relay join that hotspot; the laptop remains on campus PAL3.0.
The Android phone receives the glasses' MJPEG stream locally, then a
transport-only Java helper uploads frames through a TLS WebSocket to a temporary
Cloudflare tunnel terminating at the laptop. All gaze inference stays local.

This condition measures the combined hotspot WLAN, cellular uplink, Internet,
Cloudflare proxy and laptop path. It is **not** an isolated measurement of the
5G radio. The operator confirms the iPhone has Wi-Fi off and displays a 5G
indicator. This is operator-observed evidence, without iPhone modem telemetry or
a guarantee that the radio never changes during a trial. The laptop default
route and both Android devices' SSIDs are checked before each run. USB supplies
power, controls and trace export, with no video forwarding.

## Components

- `tools/cellular_bridge.py`: private-token upload endpoint on loopback port
  8790. Expose only this port through the tunnel. It has no video-reading route.
  A separate authenticated MJPEG endpoint on port 8791 feeds the existing
  laptop receiver. Neither the viewer nor its controls are tunneled.
- `tools/java/CellularUpload.java`: Android `app_process` transport helper using
  the existing `StreamClient`, `FrameHub` and frame format. The source and upload
  pairing codes arrive on standard input. They are not written to command-line
  arguments or traces. TLS certificate, hostname and WebSocket accept checks are
  enabled. The helper keeps only the newest source frame, with a bounded socket
  send buffer and a watchdog for blocked writes.
- `tests/test_cellular_bridge.py`: authenticated upload, no public read endpoint,
  live WebSocket delivery before close, size/framing limits and chunk decoding.

Ordinary long HTTP uploads were buffered by the proxy during setup. That
transport is not used for the measured trials. WebSocket delivery was verified
with actual glasses frame identifiers and local inference before collection.
Setup logs are retained separately and do not count toward measured time.

## Reproduce setup

Use the SDK/JDK locations configured in this checkout. Compile the transport
helper with the unchanged stream core, then convert it to Android DEX:

```sh
mkdir -p .tools/cellular-bridge/classes .tools/cellular-bridge/dex
.tools/jdk/Contents/Home/bin/javac --release 8 \
  -d .tools/cellular-bridge/classes \
  stream-core/src/main/java/edu/purdue/cs536/stream/*.java \
  tools/java/CellularUpload.java
JAVA_HOME="$PWD/.tools/jdk/Contents/Home" \
  .tools/android-sdk/build-tools/35.0.0/d8 --min-api 26 \
  --lib .tools/android-sdk/platforms/android-35/android.jar \
  --output .tools/cellular-bridge/dex \
  .tools/cellular-bridge/classes/*.class \
  .tools/cellular-bridge/classes/edu/purdue/cs536/stream/*.class
```

Create a random URL-safe bridge token (32 or more characters) in a local file
readable only by the user. Start the bridge with a **new** trace path:

```sh
python3 tools/cellular_bridge.py --token-file PRIVATE_TOKEN_FILE \
  --trace NEW_BRIDGE_TRACE.csv
cloudflared tunnel --url http://127.0.0.1:8790 \
  --no-autoupdate --protocol http2
```

The official client download is
`https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-arm64.tgz`.
The November 18 setup used version `2026.11.1`. The binary SHA-256 and DEX SHA-256
are preserved in each batch's topology manifest; the latest-download URL alone
does not pin a future version. Cloudflare Quick Tunnels are a development
service without an uptime guarantee:
https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/

Push the DEX to `/data/local/tmp/cs536-cellular.dex` on the Android relay.
Launch `app_process / CellularUpload /data/local/tmp/cs536-cellular-uploader.csv`
with `CLASSPATH` pointing to that file. Pass four newline-separated values on
stdin: local relay URL, phone pairing code, HTTPS tunnel base URL, bridge token.
The trace filename must be new or backed up first because Java `CsvTrace`
overwrites it. Private session launchers in `.tools/` supply these values without
printing them.

Point the normal `laptop-viewer/gaze_viewer.py` at `http://127.0.0.1:8791`, using
the bridge token as its pairing code and the same model settings as the baseline.
Inspect live `/status` and `/ai` on the loopback viewer before starting trials.

## Collect and analyze

Create a topology JSON containing the actual route, operator cellular evidence,
client hashes, `usb_video_forwarding: false` and
`cloud_proxy_included_in_measurements: true`. Private pairing JSON retains the
current glasses/phone IPs; no network-account credentials are included.

```sh
python3 Bonus-PartC/collect.py \
  --network 5G-hotspot-via-cloudflare --expected-ssid IPhone-sashank \
  --topology-file PRIVATE_TOPOLOGY.json --bridge-trace BRIDGE_TRACE.csv \
  --scenario stationary --runs 12 --duration 120 \
  --pairing-file PRIVATE_PAIRING.json --viewer-log-dir LAPTOP_LOG_DIR \
  --output NEW_BATCH_DIR
python3 Bonus-PartC/verify.py NEW_BATCH_DIR
python3 Bonus-PartC/analyze.py NEW_BATCH_DIR --output NEW_RESULTS_DIR
```

Every run restarts glasses capture and the phone relay, waits for a fresh camera
session, and saves the original three-device traces and inference results.
Additional `phone-uploader.csv` and `bridge.csv` retain that source session's
transport metadata. Camera IDs, frame sequences and JPEG lengths can be joined
across hops; timestamps remain in their own clock domains. Do not subtract
uncalibrated device clocks to claim one-way latency. Full continuous traces,
failed setup attempts and the topology evidence remain outside Git under
`output/verification/` and `data/raw/`.

Only completed run manifests count as evidence. A trial interruption or failed
run must remain visible. This cellular batch by itself does not complete Part C
or establish gaze accuracy, full display latency or extra walking-scenario runs.
Stop the phone helper and temporary tunnel after the authorized test session.

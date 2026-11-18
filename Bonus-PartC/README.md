# Physical field evaluation (partial Part C)

**Baseline collection completed November 4:** all 12 planned runs saved, totaling 24.00075 measured minutes. Frame envelope metadata was verified through all three devices. Actual laptop receive/inference rates were 7.455/7.273 fps. Mean pipeline time was 63.4 ms; 44 of 10,473 inferences exceeded 125 ms. There were no receive silences over 500 ms in these runs. These observations do not establish gaze accuracy or full Part C coverage.

The first prospectively planned condition is **stationary PAL3.0**, 12 fresh camera/relay sessions × 120 measured seconds. The operator authorized this condition before collection. Camera: requested 8 fps, 640×480, JPEG quality 65. Laptop: MTGS static VSGaze, 224 scene input, FP32, maximum four heads, confidence 0.6. No phone inference. The laptop also ran development and document-authoring tasks, so these timing results do not represent an isolated idle-laptop benchmark.

The current batch is `data/raw/part-c/2026-11-04-pal30-stationary-attempt03`. Earlier setup attempts are retained separately and do not count as complete runs. Run manifests are authoritative; only `status: complete` is analyzed. Collection uses actual physical video, not a video-file relay simulation. USB provides power/control and trace export; the video path uses PAL3.0, with no ADB forwarding.

## Reproduce analysis

From the project root:

```sh
python3 Bonus-PartC/verify.py \
  data/raw/part-c/2026-11-04-pal30-stationary-attempt03
python3 -m unittest discover -s Bonus-PartC -p 'test_*.py' -v
python3 Bonus-PartC/analyze.py \
  data/raw/part-c/2026-11-04-pal30-stationary-attempt03 \
  --output results/part-c/pal30-stationary-2026-11-04
MPLCONFIGDIR=.tools/matplotlib .tools/gaze-env/bin/python Bonus-PartC/plot.py \
  results/part-c/pal30-stationary-2026-11-04/summary.json \
  --output results/part-c/pal30-stationary-2026-11-04/figures
```

To collect another batch, keep the existing authenticated phone relay viewer running and use a **new** output directory:

```sh
python3 Bonus-PartC/collect.py --scenario stationary --runs 12 --duration 120 \
  --pairing-file .tools/live-test-2026-11-04/pairing.json \
  --viewer-log-dir output/verification/hardware-2026-11-04/laptop-traces \
  --output data/raw/part-c/NEW-PAL30-STATIONARY-BATCH
```

Optional `--glasses-package`, `--phone-package`, `--glasses-apk`, `--phone-apk` and `--variant` arguments record separate enhancement test builds accurately. Enhanced runs must contain a `pacing=absolute` camera configuration event. The original baseline process uses its originally loaded code and APKs throughout.

Pairing configuration stays local and is not copied into outputs. The collector defaults to the verified device serials, `.partb` application IDs and PAL3.0 checks. Cellular collection requires explicit `--network 5G-hotspot-via-cloudflare`, the actual hotspot SSID, a topology manifest and bridge trace. See [CELLULAR_TESTS.md](CELLULAR_TESTS.md). The `walking` option is available only when the operator actually performs walking runs.

Each run resets glasses capture and the relay, waits for a fresh session at the laptop, starts inference, measures the requested duration, pauses inference, stops both source applications and exports traces. The laptop model remains warm. Control and trace-export overhead is **outside** the measured run duration and lengthens total elapsed batch time. A stopped/interrupted run is retained but excluded from completed-run summaries.

## Metrics and limits

- Actual receive/inference/published fps = observed frame count / measured duration. Encoded video fps is unrelated to these counters.
- Pipeline timing covers detection, gaze, preprocessing and overlay rendering. Local receive-to-result adds laptop scheduling and annotation completion; it excludes camera, relay, Wi-Fi and browser display.
- Never subtract unsynchronized device clocks. Match frames by camera session and sequence; calculate rates within each local clock domain. Ping is phone-to-glasses RTT only.
- JPEG payload Mbit/s excludes protocol/radio overhead and is not available link bandwidth. Earlier hops use the same sequence interval as the laptop to avoid counting startup frames as losses. Missing frames do not identify a specific network-loss mechanism.
- Stall = receive silence >500 ms, including initial/final window silence. Report maximum silence and excess silence above the threshold. Jitter = absolute deviation of interarrival intervals from the run median.
- `received_without_inference` includes cadence/latest-frame selection and measurement-window boundaries. It is not a network-loss count.
- Head-containing inference timing is separate from no-head timing. Gaze accuracy remains unmeasured without manual ground-truth labels.
- Run-level plots show observed variation. Same devices and session do not supply independent subjects or diverse networks.

## Requirements still outstanding

This batch alone cannot complete Part C. Collect multiple real scenarios over PAL3.0 **and 5G**, with at least 10 runs per scenario, each >=30 seconds, and **more than one hour** in total. The November 18 cellular snapshot has 12 verified runs and four requested supplemental runs pending during recharge. Its explicit route includes the iPhone cellular uplink, hotspot WLAN and Cloudflare. Current eligible baseline field time is about 53 minutes; four additional actual two-minute runs would bring it above one hour, but they are not yet counted. Walking coverage remains below ten runs. Add defensible end-to-end/display latency evidence and app-specific ground-truth/user-experience evaluation. Preserve raw traces and report setup failures. No `BONUS-PartC` completion tag is asserted.

## Five-minute walking pilot (separate evidence)

The operator chose one continuous five-minute walk instead of the planned twelve two-minute walking trials. `walking_pilot.py` measures the existing live camera/relay session, samples laptop status and inference, probes phone-to-glasses RTT using wireless phone ADB, and exports the received-frame cohort. Video continues over Wi-Fi with USB cables removed. The glasses' wireless ADB connection did not become reachable, so its trace must be retrieved after USB reconnection if needed; missing device traces are explicitly labeled.

```sh
python3 Bonus-PartC/walking_pilot.py --duration 300 \
  --output data/raw/part-c/NEW-WALKING-PILOT \
  --pairing-file .tools/live-test-2026-11-04/pairing.json \
  --viewer-log-dir output/verification/hardware-2026-11-04/laptop-traces
MPLCONFIGDIR=.tools/matplotlib .tools/gaze-env/bin/python Bonus-PartC/analyze_pilot.py \
  data/raw/part-c/2026-11-04-pal30-walking-pilot \
  --output results/part-c/pal30-walking-pilot-2026-11-04
```

This pilot is **one measured run**, not ten independent runs. Thirty-second plotting windows remain correlated segments of that run. Do not extrapolate it into an hour of testing, infer a zero failure rate over longer periods, or claim completed walking-scenario coverage. Compare head-containing and no-head processing separately. Reuse the same local timing scopes and >500 ms receive-silence definition as the stationary trials. A logged Wi-Fi band/frequency change is not evidence that video traversed cellular 5G.

The November 4 pilot completed 300.002 measured seconds: 1,996 frames received (6.653 fps), 1,963 inferred (6.543 fps), and four receive gaps above 500 ms, with maximum 15.132 s. Head-containing inference averaged 65.5 ms (p95 75.5 ms); only 359 inferred frames contained detected heads, so the lower all-frame mean must not be called a model-speed improvement over stationary scenes. Four pipeline samples exceeded 125 ms. The glasses trace was subsequently retrieved by USB, completing three-device envelope-metadata verification. Long-gap episode details in the summary show that capture continued while phone reception paused; exact network root cause remains unestablished.

## November 18 cellular snapshot

November 18 update: twelve stationary cellular-hotspot trials are complete and verified, totaling 24.00076 measured minutes. The route is glasses and Android relay on an iPhone hotspot, cellular uplink through an authenticated Cloudflare WebSocket bridge, and laptop inference on PAL3.0. The operator observed a 5G indicator; no continuous iPhone modem telemetry is available. Actual receive/inference rates are 7.21/7.00 fps, with 23 receive gaps above 500 ms (maximum 4.59 s). Mean pipeline time is 68.0 ms, with 149 of 10,076 inferences above 125 ms. Camera, relay, uploader, bridge and laptop frame metadata match. Four additional requested cellular trials await glasses recharging; they are not counted yet. Eligible baseline field time is currently about 53 minutes. A further single walking pilot, optical latency measurement and matched pacing comparison are prepared or planned, not completed. Part C remains partial.

Derived data: `results/part-c/5g-hotspot-stationary-2026-11-18/`. Raw manifests and all five trace points: `data/raw/part-c/2026-11-18-5g-hotspot-stationary-attempt03/`. Prior setup/export failures are retained and excluded. [Optical latency protocol](LATENCY_TEST.md) and [matched pacing protocol](../Bonus-PartD/MATCHED_PROTOCOL.md) are prepared; neither is a completed physical follow-up.

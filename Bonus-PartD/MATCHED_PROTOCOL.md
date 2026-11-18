# Matched capture-pacing follow-up

The completed November 18 comparison used two counterbalanced pairs, with one 120-second run per condition in each pair (four runs, eight measured minutes). See [the completed results](../results/part-d/5g-matched-side-2pairs-2026-11-18/README.md). These were configuration-matched trials; head workloads and WAN conditions varied.

The protocol below preserves the original proposed four-pair, 60-second design for a future collection; it does not describe the completed run count.

For that design, collect four paired blocks. Each block has
one 60-second baseline run and one 60-second steady-pacing run. Preselect two
baseline-first blocks and two steady-first blocks, then shuffle their order with
the recorded seed. This gives eight actual runs and eight measured minutes;
installation, restarts, warm-up and exports are outside that time.

Wait for the operator to be ready and for sufficient glasses battery. Keep the
same visible person/scene and camera position for both conditions in a pair.
Use camera 0, 640x480, requested 8 fps, JPEG quality 65, rotation 0; laptop MTGS
224x224 scene input, FP32, max four heads, threshold 0.6. Keep the same phone
relay, local inference process and network topology. Record deviations rather
than silently treating unmatched scenes or head counts as identical workloads.

The runner installs known isolated `.partb` / `.partd` APKs and saves their
hashes. Original application IDs are left intact. The enhanced trace must contain
`pacing=absolute`. The normal callback-relative scheduler remains the baseline.

```sh
.tools/gaze-env/bin/python Bonus-PartD/matched_trials.py \
  --pairs 4 --duration 60 --seed 20261118 \
  --network 5G-hotspot-via-cloudflare --expected-ssid IPhone-sashank \
  --pairing-file PRIVATE_PAIRING.json --topology-file PRIVATE_TOPOLOGY.json \
  --bridge-trace CURRENT_BRIDGE.csv --viewer-log-dir CURRENT_LAPTOP_LOG_DIR \
  --output NEW_RAW_MATCHED_DIR --results NEW_MATCHED_RESULTS_DIR
```

Run this only after agreeing on the physical workload with the operator. For a
PAL3.0 comparison, select that network and SSID, use its actual relay addresses,
and omit the cellular-only options. Do not label PAL3.0 data as cellular data.

Each variant uses the existing collector with a fresh camera session and saves
camera, phone, laptop and, for cellular, uploader/bridge traces. Verify envelope
metadata before analysis. Preserve every batch separately, including partial
failures. Aggregate only complete pairs; one completed condition alone is not a
completed paired comparison.

Compare capture rate, receive rate, inference rate, JPEG payload rate, pipeline
budget exceedances, local receive-to-result p95, and stalls. Report
steady-minus-baseline differences within each pair and show the individual
pairs. A throughput gain can come with higher traffic or delay; a null or mixed
result is valid. Consecutive short trials on the same devices are not independent
subjects or proof of a general network improvement. These local timings do not
replace the separate preliminary stopwatch display-latency measurement.

# Capture-pacing comparison: November 18, 2026

Four complete and envelope-verified physical trials: two 120-second runs per condition. Pair 1 order: steady then baseline; pair 2: baseline then steady. Camera 0, 640x480, requested 8 fps, JPEG quality 65; laptop MTGS scene input 224x224, FP32, maximum four heads, detector threshold 0.6. The phone performs no inference.

The route includes iPhone hotspot WLAN, operator-observed 5G service, Internet routing and Cloudflare. No continuous iPhone modem telemetry or isolated cellular-radio claim.

| Metric | Baseline | Steady pacing |
|---|---:|---:|
| Mean capture fps in matched source intervals | 7.45 | 8.00 |
| Actual received fps | 4.92 | 7.38 |
| Actual inference fps | 4.75 | 7.25 |
| JPEG payload Mbit/s | 0.90 | 1.41 |
| Mean pipeline ms | 78.23 | 56.11 |
| Mean of run local receive-to-result p95, ms | 172.07 | 152.08 |
| Receive silences above 500 ms | 48.00 | 11.00 |

## Workload qualification

The configuration and durations are matched, but the visible-head workload changed in pair 1:
- Pair 1: baseline 530/544 head-containing inferences; steady pacing 5/788.
- Pair 2: baseline 596/596 head-containing inferences; steady pacing 953/953.

Delivery, inference and local-latency differences are descriptive. They cannot be attributed solely to pacing with the changing head workload and WAN conditions. The capture-rate comparison tests the scheduler directly, but does not demonstrate gaze accuracy, universal 8 fps delivery or a uniform latency improvement. The individual pairs and signed differences remain in `summary.json`; aggregates and limitations are in `review.json`. Local receive-to-result timing excludes network and physical-display delay.

Raw batches: `data/raw/part-d/2026-11-18-5g-matched-side-2pairs/`. Each condition retains its collector manifest, five-hop envelope verification, raw traces and per-frame inference. Prior PAL3.0 preliminary results remain separate. No raw data, credentials or model weights are added to this result directory.

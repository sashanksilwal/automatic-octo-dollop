# Capture pacing enhancement (preliminary physical evaluation)

Stationary PAL3.0 baseline traces show a capture rate near 7.5 fps despite requesting 8 fps. Complete-run metrics come from `Bonus-PartC/analyze.py`. The existing gate accepts the first camera callback after 125 ms since the previous accepted callback, then resets its deadline to that actual callback time. Regular 30 fps callbacks therefore select every fourth callback, producing 7.5 fps.

`stream-core/src/main/java/edu/purdue/cs536/stream/CapturePacer.java` preserves an absolute deadline, advances past missed slots after a stall, and permits at most one current frame per callback. A new instance starts each camera session. It handles monotonic counter wrap and rejects invalid requested rates. The glasses app now exposes an optional **Use steady capture pacing** checkbox, disabled during an active session and saved between sessions. It defaults off to preserve the Part A capture behavior. Each trace records the pacing mode. The updated application builds and passes Android lint; it was installed as a separate `.partd` app after all baseline trials saved, retaining the original applications.

```sh
mkdir -p .tools/part-d-test-classes
.tools/jdk/Contents/Home/bin/javac -d .tools/part-d-test-classes \
  stream-core/src/main/java/edu/purdue/cs536/stream/CapturePacer.java \
  Bonus-PartD/prototype/edu/purdue/cs536/glasses/CapturePacerTest.java
.tools/jdk/Contents/Home/bin/java -cp .tools/part-d-test-classes \
  edu.purdue.cs536.glasses.CapturePacerTest
```

For synthetic regular 15, 30 and 60 fps callbacks, the old gate selects 225 frames in 30 seconds and the new gate selects 240. A 5 fps callback source remains limited to 5 fps. Tests also cover jitter relative to deadlines, stalls, repeated callbacks and `nanoTime` wrap. **These are synthetic correctness results, not physical improvement measurements.**

The optional mode was tested after freezing baseline traces, without changing JPEG quality, dimensions, phone relay or laptop inference. Future interleaved physical runs should extend this preliminary comparison. Report source/arrival/inference frame rates, payload Mbit/s, stalls, local timing and >125 ms pipeline measurements. Extra capture work may increase traffic and processing pressure. Sequential trials are confounded by changing radio and thermal state; a small preliminary comparison must disclose that. No accuracy improvement or `BONUS-PartD` completion tag is claimed.

## November 4 physical comparison

After the 12 × 120 s baseline completed, two 60 s stationary PAL3.0 runs enabled steady pacing. Traces confirm `pacing=absolute`. Camera/inference settings, phone APK hash and laptop/phone/shared relay source hashes match the baseline. All three-device frame envelope metadata checks pass.

| Measured observation | Baseline | Steady pacing |
| --- | ---: | ---: |
| Mean source capture fps | 7.460 | 8.001 |
| Laptop receive fps | 7.455 | 7.991 |
| Laptop inference fps | 7.273 | 7.600 |
| JPEG payload Mbit/s | 1.391 | 1.499 |
| Mean of run p95 local receive-to-result, ms | 155.1 | 167.2 |

Three of 912 enhanced inferences exceed 125 ms; neither enhanced run has a receive silence over 500 ms. This is a sequential, unequal-duration and unequal-count preliminary comparison on the same devices/session. Head counts, background activity and laptop authoring workload were not controlled. Increased traffic and higher receive-to-result p95 are observed tradeoffs; a uniform latency improvement is not established. Actual inference still falls below 8 fps despite source capture approaching 8 fps. No gaze-accuracy improvement is claimed.

Raw enhanced traces: `data/raw/part-d/2026-11-04-pal30-steady-pacing`. Derived metrics and comparison: `results/part-d/`. Reproduce after Part C analysis:

```sh
python3 Bonus-PartC/verify.py data/raw/part-d/2026-11-04-pal30-steady-pacing
python3 Bonus-PartC/analyze.py data/raw/part-d/2026-11-04-pal30-steady-pacing \
  --output results/part-d/pal30-steady-pacing-2026-11-04
MPLCONFIGDIR=.tools/matplotlib .tools/gaze-env/bin/python Bonus-PartD/compare.py \
  --baseline results/part-c/pal30-stationary-2026-11-04/summary.json \
  --enhanced results/part-d/pal30-steady-pacing-2026-11-04/summary.json \
  --output results/part-d/comparison-2026-11-04
```

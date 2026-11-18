# Optical display-age measurement protocol (prepared; physical test pending)

The existing receive-to-result timings exclude the camera, relay/network and
physical browser display. This protocol adds an externally observed estimate of
the complete video path while keeping inference on the laptop. It does not
subtract device clocks or assume that half a ping is one-way video latency.

1. Finish the active field batch before changing the setup. Keep the normal
   annotated laptop viewer running with the intended model settings and network.
2. Run `.tools/gaze-env/bin/python tools/latency_probe.py serve` and open
   `http://127.0.0.1:8800/`. The source marker and the annotated laptop video are
   shown side by side. This page uses the existing inference viewer as its frame
   source; it does not change the model or transport.
3. Point the glasses at the left-hand source marker, with a physical person also
   visible if measuring the head-containing gaze workload. Frame only that
   source panel to avoid a recursive screen image. Check that the delayed marker
   appears clearly in the right-hand annotated video.
4. With a separate camera, record both panels simultaneously, preferably at
   60 fps. Do not open a camera application on the Android relay: its receiver
   must remain foreground. An iPhone hotspot camera can be used only if the
   hotspot and stream remain active. Collect separate, named recordings (for
   example three 20-second observations), recording network, model, head count,
   recording resolution and actual frame rate.
5. Analyze the external recordings. Choose one fixed rectangular crop around
   the source marker and another around the marker inside the delayed video.
   Each crop must contain exactly one readable marker. The assistant can inspect
   a recording frame and choose these coordinates.

```sh
.tools/gaze-env/bin/python tools/latency_probe.py analyze \
  --video EXTERNAL_RECORDING.mp4 \
  --source-roi X,Y,WIDTH,HEIGHT --received-roi X,Y,WIDTH,HEIGHT \
  --sample-fps 10 --output NEW_LATENCY_RESULTS_DIR
```

Marker IDs change every 20 ms and wrap every 20 seconds. The analysis estimates
display age as `((source_id - received_id) mod 1000) * 20 ms`. It assumes the
displayed video is less than 20 seconds old; do not interpret a wrapped outage as
low latency. Source-marker granularity, monitor refresh, external-camera
exposure and rolling shutter limit precision. This is an optical frame-age
estimate, not calibrated hardware capture timestamps. Keep unreadable pairs as
missing observations, retain the original recording and show valid-pair counts.
Consecutive recording frames are correlated and do not create independent runs.

The target adds a local frame-fetch/render step for this measurement page. Record
that distinction rather than claiming it is an exact measurement of every
possible viewer configuration. Preserve the original normal-viewer local
compute metrics alongside these optical observations.

`tests/test_latency.py` verifies a known 500 ms marker offset, including marker
wrap, through an encoded synthetic video. Passing that test validates the
analysis logic only. No physical latency result is claimed by preparing this
tool or running its synthetic test.

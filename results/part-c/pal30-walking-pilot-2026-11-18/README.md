# November 18 PAL3.0 walking pilot

One actual 300.005-second measurement window, with a walking interruption and near-laptop pause. Both device traces were retrieved after USB reconnection. Every measured laptop frame matches glasses and phone envelope metadata; two original phone trace files are retained across a relay restart. No extrapolation into extra runs.

- Received 1,129 frames (3.763 fps); inferred 1,128 (3.760 fps).
- One receive silence above 500 ms, lasting 148.990 seconds.
- Phone trace includes a stopped state, followed by a new connection/trace. The reason for stopping is not established by these CSV events alone.
- Operator reported a frozen/error phone preview and later recovery. The recorded duration is not a claim of uninterrupted walking or delivery.
- No RTT probes ran during this USB-free pilot; zero probe failures is not evidence of zero network failures.
- Raw data: `data/raw/part-c/2026-11-18-pal30-walking-pilot/`. Derived metrics, per-hop gap evidence and correlated plotting windows are in `summary.json`.

The earlier November 4 walking pilot remains separate. Together these are two actual pilots, below the required ten runs per scenario. Parts A/B remain functional; this trial does not complete Part C.

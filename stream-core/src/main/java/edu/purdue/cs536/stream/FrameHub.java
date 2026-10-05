package edu.purdue.cs536.stream;

/** One slot: slow consumers skip frames instead of accumulating latency and memory. */
public final class FrameHub {
    public static final long FRESH_MS = 2500;
    public static final class Sample {
        public final Frame frame;
        public final long version;
        Sample(Frame frame, long version) { this.frame = frame; this.version = version; }
    }
    private Frame latest;
    private String lastSession = "", state = "idle";
    private long lastSequence = -1, version, bytes, duplicates, lastArrivalNs;
    private final long startedNs = System.nanoTime();
    private boolean closed;
    private final Trace trace;
    public FrameHub(Trace trace) { this.trace = trace; }

    public synchronized boolean publish(Frame frame) {
        if (closed) return false;
        if (lastSession.equals(frame.session) && frame.sequence <= lastSequence) {
            duplicates++; return false;
        }
        latest = frame; lastSession = frame.session; lastSequence = frame.sequence;
        lastArrivalNs = System.nanoTime(); version++; bytes += frame.jpeg.length; state = "streaming";
        trace.event("frame_received", frame, "");
        notifyAll(); return true;
    }
    public synchronized Sample next(long after, long timeoutMs) throws InterruptedException {
        long deadline = System.nanoTime() + timeoutMs * 1_000_000L;
        while (!closed) {
            if (latest != null && version != after && ageMs() <= FRESH_MS) return new Sample(latest, version);
            long left = deadline - System.nanoTime();
            if (left <= 0) return null;
            wait(Math.max(1, left / 1_000_000L));
        }
        return null;
    }
    public synchronized void clear(String reason) {
        latest = null; state = reason; trace.event("state", null, reason); notifyAll();
    }
    public synchronized void close() { closed = true; clear("stopped"); }
    public synchronized boolean isClosed() { return closed; }
    public synchronized long ageMs() { return lastArrivalNs == 0 ? -1 : (System.nanoTime() - lastArrivalNs) / 1_000_000L; }
    public synchronized long frames() { return version; }
    public synchronized String statusJson() {
        long age = ageMs();
        String actual = latest != null && age > FRESH_MS ? "stalled" : state;
        return "{\"protocol\":1,\"state\":\"" + escape(actual) + "\",\"frames\":" + version
            + ",\"jpeg_bytes\":" + bytes + ",\"duplicates\":" + duplicates
            + ",\"frame_age_ms\":" + age + ",\"uptime_ms\":" + ((System.nanoTime() - startedNs) / 1_000_000L)
            + ",\"source_session\":\"" + lastSession + "\",\"sequence\":" + lastSequence + "}";
    }
    static String escape(String s) { return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", " ").replace("\r", " "); }
}

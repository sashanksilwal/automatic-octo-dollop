package edu.purdue.cs536.stream;

/** Absolute-deadline capture pacing. Caller supplies one monotonic clock domain.
 * One current frame at most per callback; missed slots never become queued work.
 * A new instance is created for each camera session. */
public final class CapturePacer {
    private final long periodNs;
    private boolean started;
    private long nextNs;
    public CapturePacer(int fps) {
        if (fps < 1 || fps > 120) throw new IllegalArgumentException("fps must be 1..120");
        periodNs = 1_000_000_000L / fps;
    }
    public boolean accept(long nowNs) {
        if (!started) {
            started = true;
            nextNs = nowNs + periodNs;
            return true;
        }
        long lateness = nowNs - nextNs;
        if (lateness < 0) return false;
        nextNs += (lateness / periodNs + 1) * periodNs;
        return true;
    }
}

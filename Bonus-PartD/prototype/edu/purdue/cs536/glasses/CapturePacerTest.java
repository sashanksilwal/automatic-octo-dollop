package edu.purdue.cs536.glasses;
import edu.purdue.cs536.stream.CapturePacer;

public final class CapturePacerTest {
    private static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
    private static int count(int callbacksPerSecond, boolean phase) {
        CapturePacer gate = new CapturePacer(8);
        long last = -1_000_000_000L;
        int count = 0;
        for (int i = 0; i < callbacksPerSecond * 30; i++) {
            long now = Math.round(i * 1_000_000_000.0 / callbacksPerSecond);
            boolean accepted = phase ? gate.accept(now) : now - last >= 125_000_000L;
            if (accepted) { count++; last = now; }
        }
        return count;
    }
    public static void main(String[] args) {
        for (int callbackRate : new int[] {15, 30, 60}) {
            int oldCount = count(callbackRate, false), newCount = count(callbackRate, true);
            check(newCount == 240, "8 fps schedule on " + callbackRate + " fps callbacks");
            check(oldCount < newCount, "Synthetic quantization reproduces the source deficit");
            System.out.println("30s synthetic " + callbackRate + " fps callbacks: legacy=" + oldCount + ", absolute=" + newCount);
        }
        check(count(5, true) == 150, "Cannot generate absent camera callbacks");
        CapturePacer p = new CapturePacer(8);
        check(p.accept(0), "First frame accepted");
        check(!p.accept(0), "Duplicate callback rejected");
        check(!p.accept(124_999_999), "No early capture");
        check(p.accept(133_333_333), "Delayed callback accepted");
        check(p.accept(250_000_000), "Deadline retains phase");
        check(p.accept(10_000_000_000L), "Current frame after stall accepted");
        check(!p.accept(10_000_000_000L), "No catch-up burst");
        check(!p.accept(10_124_999_999L), "No immediate extra work after stall");
        check(p.accept(10_125_000_000L), "Continues future deadlines");
        CapturePacer wrap = new CapturePacer(8);
        long start = Long.MAX_VALUE - 40_000_000;
        check(wrap.accept(start), "Accept near nanoTime wrap");
        check(!wrap.accept(start + 100_000_000), "Wrap-safe early check");
        check(wrap.accept(start + 125_000_000), "Wrap-safe due check");
        try { new CapturePacer(0); throw new AssertionError("Invalid fps"); }
        catch (IllegalArgumentException expected) { }
        System.out.println("Capture pacing correctness checks passed. This is synthetic, not physical evaluation.");
    }
}

package edu.purdue.cs536.stream;

import java.io.*;
import java.nio.charset.StandardCharsets;

/** Logs metadata only. No pairing tokens or image contents are written. */
public final class CsvTrace implements Trace, Closeable {
    private final BufferedWriter writer;
    private long lastFlush;
    private boolean closed;
    private volatile String error = "";

    public CsvTrace(File file) throws IOException {
        writer = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(file), StandardCharsets.UTF_8));
        writer.write("unix_ms,local_mono_ns,event,source_session,sequence,capture_mono_ns,capture_unix_ms,jpeg_bytes,width,height,detail\n");
        writer.flush();
    }
    @Override public synchronized void event(String event, Frame f, String detail) {
        if (closed) return;
        try {
            long now = System.nanoTime();
            writer.write(System.currentTimeMillis() + "," + now + "," + quote(event) + ","
                + (f == null ? ",,,,,," : quote(f.session) + "," + f.sequence + "," + f.captureMonoNs
                + "," + f.captureUnixMs + "," + f.jpeg.length + "," + f.width + "," + f.height)
                + "," + quote(detail) + "\n");
            if (now - lastFlush > 1_000_000_000L) { writer.flush(); lastFlush = now; }
        } catch (IOException e) { error = "Trace write failed: " + e.getClass().getSimpleName(); }
    }
    private static String quote(String text) { return "\"" + text.replace("\"", "\"\"") + "\""; }
    public String error() { return error; }
    @Override public synchronized void close() throws IOException {
        if (!closed) { closed = true; writer.close(); }
    }
}

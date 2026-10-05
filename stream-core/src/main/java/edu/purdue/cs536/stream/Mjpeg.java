package edu.purdue.cs536.stream;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Strict, bounded multipart framing shared with the Python viewer. */
public final class Mjpeg {
    public static final String BOUNDARY = "cs536frame";
    public static final String CONTENT_TYPE = "multipart/x-mixed-replace; boundary=" + BOUNDARY;
    private Mjpeg() { }
    public static void write(OutputStream out, Frame f) throws IOException {
        String header = "--" + BOUNDARY + "\r\nContent-Type: image/jpeg\r\nContent-Length: " + f.jpeg.length
            + "\r\nX-Protocol-Version: 1\r\nX-Source-Session: " + f.session + "\r\nX-Frame-Id: " + f.sequence
            + "\r\nX-Capture-Mono-Ns: " + f.captureMonoNs + "\r\nX-Capture-Unix-Ms: " + f.captureUnixMs
            + "\r\nX-Width: " + f.width + "\r\nX-Height: " + f.height + "\r\n\r\n";
        out.write(header.getBytes(StandardCharsets.US_ASCII)); out.write(f.jpeg);
        out.write(new byte[]{13, 10}); out.flush();
    }
    public static Frame read(InputStream in) throws IOException {
        if (!line(in).equals("--" + BOUNDARY)) throw new IOException("Unexpected multipart boundary");
        Map<String, String> h = headers(in);
        try {
            if (!"1".equals(h.get("x-protocol-version")) || !"image/jpeg".equals(h.get("content-type")))
                throw new IOException("Unsupported frame format");
            int length = Integer.parseInt(required(h, "content-length"));
            if (length < 4 || length > Frame.MAX_BYTES) throw new IOException("Frame length outside limit");
            byte[] jpeg = new byte[length];
            new DataInputStream(in).readFully(jpeg);
            if (in.read() != 13 || in.read() != 10) throw new IOException("Missing frame terminator");
            return new Frame(required(h, "x-source-session"), Long.parseLong(required(h, "x-frame-id")),
                Long.parseLong(required(h, "x-capture-mono-ns")), Long.parseLong(required(h, "x-capture-unix-ms")),
                Integer.parseInt(required(h, "x-width")), Integer.parseInt(required(h, "x-height")), jpeg);
        } catch (IllegalArgumentException e) { throw new IOException("Invalid frame metadata", e); }
    }
    private static String required(Map<String, String> h, String key) throws IOException {
        if (!h.containsKey(key)) throw new IOException("Missing " + key);
        return h.get(key);
    }
    static Map<String, String> headers(InputStream in) throws IOException {
        Map<String, String> result = new HashMap<>();
        int total = 0;
        for (int count = 0; count < 40; count++) {
            String line = line(in); total += line.length();
            if (total > 16384) throw new IOException("Headers too large");
            if (line.isEmpty()) return result;
            int colon = line.indexOf(':');
            if (colon < 1) throw new IOException("Malformed header");
            String key = line.substring(0, colon).trim().toLowerCase(Locale.ROOT);
            if (result.put(key, line.substring(colon + 1).trim()) != null) throw new IOException("Duplicate header");
        }
        throw new IOException("Too many headers");
    }
    static String line(InputStream in) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        for (int i = 0; i < 2048; i++) {
            int b = in.read();
            if (b < 0) throw new EOFException("Stream ended");
            if (b == 10) {
                byte[] bytes = out.toByteArray();
                if (bytes.length == 0 || bytes[bytes.length - 1] != 13) throw new IOException("Expected CRLF");
                return new String(bytes, 0, bytes.length - 1, StandardCharsets.US_ASCII);
            }
            out.write(b);
        }
        throw new IOException("Line too long");
    }
}

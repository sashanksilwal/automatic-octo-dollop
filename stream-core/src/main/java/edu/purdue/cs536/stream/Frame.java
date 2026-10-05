package edu.purdue.cs536.stream;

/** A JPEG and its source identity. Treat jpeg as immutable after construction. */
public final class Frame {
    public static final int MAX_BYTES = 4 * 1024 * 1024;
    public final String session;
    public final long sequence, captureMonoNs, captureUnixMs;
    public final int width, height;
    public final byte[] jpeg;

    public Frame(String session, long sequence, long captureMonoNs, long captureUnixMs,
                 int width, int height, byte[] jpeg) {
        if (session == null || !session.matches("[A-Za-z0-9-]{1,64}") || sequence < 0
                || captureMonoNs < 0 || captureUnixMs < 0 || width < 1 || width > 4096
                || height < 1 || height > 4096 || jpeg == null || jpeg.length < 4
                || jpeg.length > MAX_BYTES || (jpeg[0] & 255) != 255 || (jpeg[1] & 255) != 216
                || (jpeg[jpeg.length - 2] & 255) != 255 || (jpeg[jpeg.length - 1] & 255) != 217) {
            throw new IllegalArgumentException("Invalid frame metadata or JPEG envelope");
        }
        this.session = session; this.sequence = sequence;
        this.captureMonoNs = captureMonoNs; this.captureUnixMs = captureUnixMs;
        this.width = width; this.height = height; this.jpeg = jpeg;
    }
}

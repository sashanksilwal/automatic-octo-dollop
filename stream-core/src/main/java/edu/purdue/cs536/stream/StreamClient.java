package edu.purdue.cs536.stream;

import java.io.*;
import java.net.*;

/** Reconnecting receiver. Create a new instance for every start/resume. */
public final class StreamClient implements Closeable {
    public interface Listener {
        void frame(Frame frame);
        void state(String state);
    }
    private final URL url;
    private final String token;
    private final Listener listener;
    private final Trace trace;
    private volatile boolean running = true;
    private volatile HttpURLConnection connection;
    private final Thread thread;

    public StreamClient(String baseUrl, String token, Listener listener, Trace trace) throws MalformedURLException {
        URL base = new URL(baseUrl);
        if ((!base.getProtocol().equals("http") && !base.getProtocol().equals("https")) || base.getHost().isEmpty()
                || base.getUserInfo() != null || base.getQuery() != null || base.getRef() != null
                || (!base.getPath().isEmpty() && !base.getPath().equals("/")))
            throw new MalformedURLException("Enter a base address such as http://192.168.1.20:8080");
        if (token == null || !token.matches("[A-Za-z0-9_-]{6,128}")) throw new MalformedURLException("Invalid pairing code");
        this.url = new URL(base, "/stream"); this.token = token; this.listener = listener; this.trace = trace;
        thread = new Thread(this::run, "stream-receiver"); thread.setDaemon(true);
    }
    public void start() { thread.start(); }
    private void run() {
        long backoff = 250;
        while (running) {
            HttpURLConnection current = null;
            try {
                state("connecting");
                current = (HttpURLConnection) url.openConnection(); connection = current;
                current.setConnectTimeout(4000); current.setReadTimeout(4000);
                current.setInstanceFollowRedirects(false); current.setUseCaches(false);
                current.setRequestProperty("Authorization", "Bearer " + token);
                if (!running) break;
                int status = current.getResponseCode();
                if (status == 401 || status == 403) { state("pairing code rejected; stop and correct it"); break; }
                if (status != 200 || !Mjpeg.CONTENT_TYPE.equals(current.getContentType())) throw new IOException("Unexpected stream response");
                try (InputStream input = new BufferedInputStream(current.getInputStream())) {
                    while (running) {
                        Frame frame = Mjpeg.read(input);
                        if (!running) break;
                        listener.frame(frame); backoff = 250;
                    }
                }
            } catch (IOException | IllegalArgumentException e) {
                if (running) state("reconnecting (" + e.getClass().getSimpleName() + ")");
            } finally {
                if (current != null) current.disconnect(); connection = null;
            }
            if (running) {
                try { Thread.sleep(backoff); } catch (InterruptedException e) { break; }
                backoff = Math.min(4000, backoff * 2);
            }
        }
    }
    private void state(String state) { if (running) { trace.event("connection", null, state); listener.state(state); } }
    @Override public void close() {
        running = false; thread.interrupt();
        HttpURLConnection current = connection;
        if (current != null) current.disconnect();
    }
}

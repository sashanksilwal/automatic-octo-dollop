package edu.purdue.cs536.stream;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.*;

/** Small authenticated HTTP server for a controlled LAN or adb-forwarded demo. */
public final class StreamServer implements Closeable {
    private final FrameHub hub;
    private final Trace trace;
    private final String token;
    private final ServerSocket listener;
    private final ExecutorService clients = Executors.newFixedThreadPool(6);
    private final ScheduledExecutorService watchdog = Executors.newSingleThreadScheduledExecutor();
    private final ConcurrentHashMap<Socket, Long> sockets = new ConcurrentHashMap<>();
    private volatile boolean running = true;

    public StreamServer(String bind, int port, String token, FrameHub hub, Trace trace) throws IOException {
        if (token == null || !token.matches("[A-Za-z0-9_-]{6,128}"))
            throw new IllegalArgumentException("Pairing code must be 6-128 letters, numbers, underscores or hyphens");
        this.token = token; this.hub = hub; this.trace = trace;
        listener = new ServerSocket(); listener.setReuseAddress(true);
        listener.bind(new InetSocketAddress(bind, port), 8);
        Thread accept = new Thread(this::acceptLoop, "stream-listener"); accept.setDaemon(true); accept.start();
        watchdog.scheduleAtFixedRate(() -> {
            long now = System.nanoTime();
            for (Map.Entry<Socket,Long> entry : sockets.entrySet())
                if (now - entry.getValue() > 6_000_000_000L) closeSocket(entry.getKey());
        }, 1, 1, TimeUnit.SECONDS);
    }
    public int port() { return listener.getLocalPort(); }
    private void acceptLoop() {
        while (running) {
            try {
                Socket socket = listener.accept(); socket.setSoTimeout(4000); socket.setTcpNoDelay(true);
                if (sockets.size() >= 6) { closeSocket(socket); continue; }
                sockets.put(socket, System.nanoTime());
                try { clients.execute(() -> serve(socket)); }
                catch (RejectedExecutionException e) { sockets.remove(socket); closeSocket(socket); }
            } catch (IOException e) { if (running) trace.event("server_error", null, e.getClass().getSimpleName()); }
        }
    }
    private void serve(Socket socket) {
        try (Socket ignored = socket) {
            InputStream in = new BufferedInputStream(socket.getInputStream());
            OutputStream out = new BufferedOutputStream(socket.getOutputStream());
            String[] request = Mjpeg.line(in).split(" ");
            Map<String, String> headers = Mjpeg.headers(in);
            if (request.length != 3 || !request[0].equals("GET")) { response(out, 405, "text/plain", "GET required"); return; }
            // Tokens travel in Authorization, never in URLs or logs.
            String authorization = headers.containsKey("authorization") ? headers.get("authorization") : "";
            if (!MessageDigest.isEqual(("Bearer " + token).getBytes(StandardCharsets.UTF_8), authorization.getBytes(StandardCharsets.UTF_8))) {
                response(out, 401, "text/plain", "Pairing code required"); return;
            }
            if (request[1].equals("/status")) { response(out, 200, "application/json", hub.statusJson()); return; }
            if (!request[1].equals("/stream")) { response(out, 404, "text/plain", "Not found"); return; }
            out.write(("HTTP/1.1 200 OK\r\nContent-Type: " + Mjpeg.CONTENT_TYPE
                + "\r\nCache-Control: no-store\r\nConnection: close\r\nX-Content-Type-Options: nosniff\r\n\r\n").getBytes(StandardCharsets.US_ASCII));
            out.flush(); trace.event("viewer_connected", null, socket.getInetAddress().getHostAddress());
            long version = -1;
            while (running && !hub.isClosed() && !socket.isClosed()) {
                FrameHub.Sample sample = hub.next(version, 3000);
                if (sample == null) break; // Close stalled streams so receivers can reconnect.
                long skipped = version < 0 ? 0 : Math.max(0, sample.version - version - 1);
                Mjpeg.write(out, sample.frame); sockets.put(socket, System.nanoTime());
                trace.event("frame_sent", sample.frame, "skipped=" + skipped);
                version = sample.version;
            }
        } catch (IOException | InterruptedException e) {
            if (e instanceof InterruptedException) Thread.currentThread().interrupt();
        } finally { sockets.remove(socket); trace.event("viewer_closed", null, ""); }
    }
    private void response(OutputStream out, int status, String type, String body) throws IOException {
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        out.write(("HTTP/1.1 " + status + " Response\r\nContent-Type: " + type + "\r\nContent-Length: "
            + bytes.length + "\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n").getBytes(StandardCharsets.US_ASCII));
        out.write(bytes); out.flush();
    }
    private static void closeSocket(Socket socket) { try { socket.close(); } catch (IOException ignored) { } }
    @Override public void close() {
        running = false;
        try { listener.close(); } catch (IOException ignored) { }
        for (Socket socket : sockets.keySet()) closeSocket(socket);
        clients.shutdownNow(); watchdog.shutdownNow();
    }
}

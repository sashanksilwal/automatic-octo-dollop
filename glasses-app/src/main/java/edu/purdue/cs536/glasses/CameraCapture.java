package edu.purdue.cs536.glasses;

import android.graphics.*;
import android.hardware.Camera;
import android.os.*;
import android.view.SurfaceHolder;
import edu.purdue.cs536.stream.Frame;
import java.io.*;
import java.util.*;

/** Camera1 is intentional: INMO's AIR2 native guide documents Camera.open(0).
 * Camera operations and encoding stay on one worker looper; buffers are reused. */
@SuppressWarnings("deprecation")
final class CameraCapture {
    interface Listener { void frame(Frame frame); void state(String text, boolean failure); }
    static final class Config {
        final int cameraId, width, height, fps, quality, rotation;
        Config(int cameraId, int width, int height, int fps, int quality, int rotation) {
            this.cameraId=cameraId; this.width=width; this.height=height;
            this.fps=fps; this.quality=quality; this.rotation=rotation;
        }
    }
    private final HandlerThread thread = new HandlerThread("glasses-camera");
    private final Handler worker;
    private Camera camera;
    private volatile boolean enabled;
    CameraCapture() { thread.start(); worker = new Handler(thread.getLooper()); }

    @android.annotation.SuppressLint("MissingPermission") // Activity checks/requests permission before calling.
    void start(SurfaceHolder surface, Config config, Listener listener) {
        enabled = true;
        worker.post(() -> {
            release();
            if (!enabled) return;
            try {
                if (config.cameraId >= Camera.getNumberOfCameras()) throw new IOException("Camera ID unavailable");
                camera = Camera.open(config.cameraId);
                Camera.Parameters p = camera.getParameters();
                Camera.Size size = Collections.min(p.getSupportedPreviewSizes(), (a,b) ->
                    Double.compare(sizeScore(a,config),sizeScore(b,config)));
                if (!p.getSupportedPreviewFormats().contains(ImageFormat.NV21)) throw new IOException("Camera does not support NV21 preview");
                p.setPreviewSize(size.width, size.height); p.setPreviewFormat(ImageFormat.NV21);
                List<String> focus = p.getSupportedFocusModes();
                if (focus != null && focus.contains(Camera.Parameters.FOCUS_MODE_CONTINUOUS_VIDEO))
                    p.setFocusMode(Camera.Parameters.FOCUS_MODE_CONTINUOUS_VIDEO);
                camera.setParameters(p); camera.setDisplayOrientation(config.rotation); camera.setPreviewDisplay(surface);
                int length = size.width * size.height * ImageFormat.getBitsPerPixel(ImageFormat.NV21) / 8;
                for (int i = 0; i < 3; i++) camera.addCallbackBuffer(new byte[length]);
                String session = UUID.randomUUID().toString();
                long[] last = {0}, sequence = {0};
                camera.setErrorCallback((error, ignored) -> { enabled = false; release(); listener.state("Camera error " + error + "; stop and restart", true); });
                camera.setPreviewCallbackWithBuffer((data, source) -> {
                    long now = System.nanoTime();
                    try {
                        if (enabled && now - last[0] >= 1_000_000_000L / config.fps) {
                            last[0] = now;
                            long wall = System.currentTimeMillis();
                            byte[] jpeg = encode(data, size.width, size.height, config.quality, config.rotation);
                            boolean swap = config.rotation == 90 || config.rotation == 270;
                            listener.frame(new Frame(session, sequence[0]++, now, wall,
                                swap ? size.height : size.width, swap ? size.width : size.height, jpeg));
                        }
                    } catch (RuntimeException | IOException e) {
                        enabled = false; listener.state("Encoding failed: " + e.getClass().getSimpleName() + "; stop and restart", true);
                        worker.post(this::release);
                    } finally { if (camera == source && enabled) source.addCallbackBuffer(data); }
                });
                camera.startPreview(); listener.state("Camera " + config.cameraId + ": " + size.width + "x" + size.height + " at up to " + config.fps + " fps", false);
            } catch (IOException | RuntimeException e) {
                enabled = false; release(); listener.state("Camera unavailable: " + e.getClass().getSimpleName() + ". Check permission, ID, and other camera apps.", true);
            }
        });
    }
    private static double sizeScore(Camera.Size s, Config config) {
        return Math.abs(Math.log((double)s.width*s.height/(config.width*config.height)))
            + 4*Math.abs((double)s.width/s.height-(double)config.width/config.height);
    }
    private byte[] encode(byte[] nv21, int w, int h, int quality, int rotation) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        if (!new YuvImage(nv21, ImageFormat.NV21, w, h, null).compressToJpeg(new Rect(0,0,w,h), quality, bytes))
            throw new IOException("JPEG encoding failed");
        if (rotation == 0) return bytes.toByteArray();
        byte[] raw = bytes.toByteArray();
        Bitmap original = BitmapFactory.decodeByteArray(raw, 0, raw.length);
        if (original == null) throw new IOException("JPEG rotation failed");
        Matrix transform = new Matrix(); transform.postRotate(rotation);
        Bitmap rotated = Bitmap.createBitmap(original, 0, 0, w, h, transform, true);
        bytes.reset(); boolean success = rotated.compress(Bitmap.CompressFormat.JPEG, quality, bytes);
        if (rotated != original) rotated.recycle(); original.recycle();
        if (!success) throw new IOException("JPEG rotation encoding failed");
        return bytes.toByteArray();
    }
    void stop() { enabled = false; worker.post(this::release); }
    void close() { enabled = false; worker.post(() -> { release(); thread.quitSafely(); }); }
    private void release() {
        if (camera != null) {
            try { camera.setPreviewCallbackWithBuffer(null); camera.stopPreview(); } catch (RuntimeException ignored) { }
            camera.release(); camera = null;
        }
    }
}

package edu.purdue.cs536.glasses;

import android.Manifest;
import android.app.Activity;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.*;
import android.view.*;
import android.widget.*;
import edu.purdue.cs536.common.AppUi;
import edu.purdue.cs536.stream.*;
import java.io.*;

@android.annotation.SuppressLint("SetTextI18n") // English-only course prototype and live diagnostic values.
public final class GlassesActivity extends Activity implements SurfaceHolder.Callback {
    private final Handler ui = new Handler(Looper.getMainLooper());
    private final Object deliveryLock = new Object();
    private CameraCapture capture;
    private SurfaceView preview;
    private boolean surfaceReady, active, paused;
    private volatile int generation;
    private EditText cameraId, fps, quality, rotation, port, token;
    private TextView status, addresses, statistics;
    private Button start, pause, stop;
    private FrameHub hub;
    private StreamServer server;
    private CsvTrace trace;
    private CameraCapture.Config config;
    private SharedPreferences preferences;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state); capture = new CameraCapture(); preferences = getPreferences(MODE_PRIVATE);
        LinearLayout root = AppUi.root(this, "CS536 · Glasses camera");
        preview = new SurfaceView(this); root.addView(preview, new LinearLayout.LayoutParams(-1, AppUi.dp(this,120)));
        preview.getHolder().addCallback(this);
        LinearLayout form = AppUi.form(this, root);
        status = AppUi.text(this, form, "Ready. Connect the glasses and phone to the same reachable network.");
        addresses = AppUi.text(this, form, AppUi.addresses(8080)); addresses.setTextIsSelectable(true);
        cameraId = field(form,"Camera ID (INMO AIR2 RGB is normally 0)","camera","0",true);
        fps = field(form,"Maximum transmitted frames/sec (1-15)","fps","8",true);
        quality = field(form,"JPEG quality (30-90)","quality","65",true);
        rotation = field(form,"Clockwise image rotation (0, 90, 180, 270)","rotation","0",true);
        port = field(form,"Listen port","port","8080",true);
        token = field(form,"Pairing code (enter this on the phone)","token",AppUi.code(),false);
        AppUi.text(this, form, "Capture requests 640×480.");
        statistics = AppUi.text(this, form, "No frames yet");
        start = AppUi.button(this, form, "Start camera stream", this::startStream);
        pause = AppUi.button(this, form, "Pause", this::togglePause);
        stop = AppUi.button(this, form, "Stop", () -> stopStream("Stopped"));
        updateButtons(); ui.post(tick);
    }
    private EditText field(LinearLayout form, String label, String key, String fallback, boolean number) {
        return AppUi.field(this, form, label, preferences.getString(key,fallback), number);
    }
    private void startStream() {
        if (active) return;
        if (!surfaceReady) { status.setText("Waiting for camera preview surface"); return; }
        if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.CAMERA}, 1); return;
        }
        try {
            int angle=AppUi.number(rotation,0,270);
            if (angle % 90 != 0) throw new IllegalArgumentException("Rotation must be 0, 90, 180 or 270");
            config = new CameraCapture.Config(AppUi.number(cameraId,0,9),640,480,AppUi.number(fps,1,15),AppUi.number(quality,30,90),angle);
            int listen = AppUi.number(port,1024,65535);
            File file = AppUi.traceFile(this,"glasses"); trace = new CsvTrace(file); hub = new FrameHub(trace);
            server = new StreamServer("0.0.0.0",listen,token.getText().toString().trim(),hub,trace);
            active=true; paused=false; generation++;
            preferences.edit().putString("camera",cameraId.getText().toString()).putString("fps",fps.getText().toString())
                .putString("quality",quality.getText().toString()).putString("rotation",rotation.getText().toString())
                .putString("port",port.getText().toString()).putString("token",token.getText().toString().trim()).apply();
            addresses.setText(AppUi.addresses(listen) + "\nTrace: " + file.getAbsolutePath());
            trace.event("config",null,"camera="+config.cameraId+";fps="+config.fps+";quality="+config.quality+";rotation="+angle);
            beginCapture(); updateButtons();
        } catch (IOException | IllegalArgumentException e) { stopStream("Cannot start: " + e.getMessage()); }
    }
    private void beginCapture() {
        final int session = generation; final FrameHub destination = hub;
        capture.start(preview.getHolder(),config,new CameraCapture.Listener() {
            @Override public void frame(Frame frame) {
                synchronized(deliveryLock) { if(generation==session) destination.publish(frame); }
            }
            @Override public void state(String text, boolean failure) { ui.post(() -> {
                if (!active || generation != session) return;
                if (failure) stopStream(text); else status.setText(text);
            }); }
        });
    }
    private void togglePause() {
        if (!active) return;
        synchronized(deliveryLock) { paused=!paused; generation++; if(paused) hub.clear("paused"); }
        if (paused) { capture.stop(); status.setText("Paused. The camera is released."); }
        else beginCapture();
        updateButtons();
    }
    private void stopStream(String reason) {
        synchronized(deliveryLock) { active=false; paused=false; generation++; if(hub!=null) hub.close(); }
        capture.stop();
        if (server != null) server.close(); server=null;
        AppUi.closeTrace(trace); trace=null; hub=null;
        status.setText(reason); updateButtons();
    }
    private void updateButtons() {
        start.setEnabled(!active); pause.setEnabled(active); stop.setEnabled(active); pause.setText(paused?"Resume":"Pause");
        for (EditText e : new EditText[]{cameraId,fps,quality,rotation,port,token}) e.setEnabled(!active);
    }
    private final Runnable tick = new Runnable() { @Override public void run() {
        if (hub!=null) statistics.setText("Frames: " + hub.frames() + " · last frame " + hub.ageMs() + " ms ago"
            + (trace.error().isEmpty()?"":"\n"+trace.error()));
        ui.postDelayed(this,1000);
    }};
    @Override public void onRequestPermissionsResult(int requestCode,String[] permissions,int[] results) {
        super.onRequestPermissionsResult(requestCode,permissions,results);
        if (requestCode==1 && results.length>0 && results[0]==PackageManager.PERMISSION_GRANTED) startStream();
        else status.setText("Camera permission is required. Grant it in Settings if previously denied.");
    }
    @Override public void surfaceCreated(SurfaceHolder holder) { surfaceReady=true; }
    @Override public void surfaceChanged(SurfaceHolder holder,int format,int width,int height) { }
    @Override public void surfaceDestroyed(SurfaceHolder holder) { surfaceReady=false; if(active) stopStream("Preview closed; stream stopped"); }
    @Override protected void onStop() { super.onStop(); if(active) stopStream("App left foreground; stream stopped"); }
    @Override protected void onDestroy() { ui.removeCallbacks(tick); capture.close(); super.onDestroy(); }
}

package edu.purdue.cs536.phone;

import android.Manifest;
import android.app.Activity;
import android.content.*;
import android.content.pm.PackageManager;
import android.os.*;
import android.widget.*;
import edu.purdue.cs536.common.*;
import edu.purdue.cs536.stream.*;

@android.annotation.SuppressLint("SetTextI18n") // English-only course prototype and live diagnostic values.
public final class PhoneActivity extends Activity {
    private final Handler ui = new Handler(Looper.getMainLooper());
    private EditText source, sourceToken, relayPort, relayToken;
    private Button start, pause, stop;
    private TextView status, addresses, stats;
    private FramePreview preview;
    private SharedPreferences preferences;
    private RelayService relay;
    private boolean bound;
    private String validationError;
    private long addressUpdatedAt;
    private String previewMessage;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state); preferences = getPreferences(MODE_PRIVATE);
        LinearLayout root = AppUi.root(this, "CS536 · Phone receiver");
        preview = new FramePreview(this); root.addView(preview, new LinearLayout.LayoutParams(-1, AppUi.dp(this,190)));
        LinearLayout form = AppUi.form(this, root);
        status = AppUi.text(this, form, "Enter the glasses address and pairing code.");
        source = field(form,"Glasses base address","source","http://192.168.1.20:8080",false);
        sourceToken = field(form,"Glasses pairing code","sourceToken","",false);
        relayPort = field(form,"Phone relay port","relayPort","8081",true);
        relayToken = field(form,"Phone pairing code (for the laptop)","relayToken",AppUi.code(),false);
        addresses = AppUi.text(this, form, AppUi.addresses(8081)); addresses.setTextIsSelectable(true);
        stats = AppUi.text(this, form, "No frames yet");
        AppUi.text(this, form, "The relay keeps running when the phone is locked. Use Stop here or in its notification to end it.");
        start = AppUi.button(this, form, "Connect and relay", this::startStream);
        pause = AppUi.button(this, form, "Pause", () -> { if (relay != null) relay.togglePause(); });
        stop = AppUi.button(this, form, "Stop", () -> { if (relay != null) relay.stopRelay(); });
        updateButtons();
    }
    private EditText field(LinearLayout form, String label, String key, String fallback, boolean number) {
        return AppUi.field(this, form, label, preferences.getString(key, fallback), number);
    }
    private final ServiceConnection connection = new ServiceConnection() {
        @Override public void onServiceConnected(ComponentName name, IBinder binder) {
            relay = ((RelayService.LocalBinder)binder).service(); relay.uiVisibility(true);
            if (relay.active()) {
                source.setText(relay.source()); sourceToken.setText(relay.sourceToken());
                relayPort.setText(Integer.toString(relay.port())); relayToken.setText(relay.relayToken());
            }
            updateButtons();
        }
        @Override public void onServiceDisconnected(ComponentName name) {
            relay = null; preview.clear("Relay stopped"); status.setText("Relay stopped"); updateButtons();
        }
    };
    @Override protected void onStart() {
        super.onStart(); bound = bindService(new Intent(this, RelayService.class), connection, BIND_AUTO_CREATE);
        ui.post(tick);
    }
    private void startStream() {
        if (relay == null || relay.active()) return;
        try {
            int port = AppUi.number(relayPort,1024,65535);
            String address = source.getText().toString().trim(), token = sourceToken.getText().toString().trim();
            String outputToken = relayToken.getText().toString().trim();
            // Validate before launching a foreground service or changing saved settings.
            StreamClient validation = new StreamClient(address, token, new StreamClient.Listener() {
                @Override public void frame(Frame frame) { }
                @Override public void state(String text) { }
            }, edu.purdue.cs536.stream.Trace.NONE);
            validation.close();
            if (!outputToken.matches("[A-Za-z0-9_-]{6,128}")) throw new IllegalArgumentException("Invalid phone pairing code");
            preferences.edit().putString("source",address).putString("sourceToken",token)
                .putString("relayPort",Integer.toString(port)).putString("relayToken",outputToken).apply();
            if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
                requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},536);
            validationError = null;
            Intent command = RelayService.startIntent(this, address, token, port, outputToken);
            if (Build.VERSION.SDK_INT >= 26) startForegroundService(command); else startService(command);
        } catch (java.io.IOException | IllegalArgumentException | SecurityException e) {
            validationError = "Cannot start: " + e.getMessage();
            status.setText(validationError);
        }
    }
    private void updateButtons() {
        boolean active = relay != null && relay.active();
        start.setEnabled(relay != null && !active); pause.setEnabled(active); stop.setEnabled(active);
        setTextIfChanged(pause, active && relay.paused() ? "Resume" : "Pause");
        for (EditText field : new EditText[]{source,sourceToken,relayPort,relayToken}) field.setEnabled(!active);
    }
    private static void setTextIfChanged(TextView view, String text) {
        if (!text.contentEquals(view.getText())) view.setText(text);
    }
    private void clearPreview(String message) {
        if (!message.equals(previewMessage)) { preview.clear(message); previewMessage = message; }
    }
    private final Runnable tick = new Runnable() { @Override public void run() {
        if (relay != null) {
            Frame frame = relay.takePreview();
            if (frame != null && preview.show(frame)) { previewMessage = null; relay.displayed(frame); }
            if (!relay.active() || relay.paused() || !"streaming".equals(relay.state()) || relay.ageMs() > FrameHub.FRESH_MS)
                clearPreview(relay.paused() ? "Paused" : "Waiting for fresh video");
            setTextIfChanged(status, validationError == null ? relay.state() : validationError);
            if (relay.active()) {
                if (SystemClock.elapsedRealtime() - addressUpdatedAt > 5000) {
                    setTextIfChanged(addresses, relay.addresses()); addressUpdatedAt = SystemClock.elapsedRealtime();
                }
                setTextIfChanged(stats, "Received: " + relay.frames() + " frames · last frame " + relay.ageMs() + " ms ago"
                    + (relay.traceError().isEmpty() ? "" : "\n"+relay.traceError()));
            }
            updateButtons();
        }
        ui.postDelayed(this,100);
    }};
    @Override protected void onStop() {
        ui.removeCallbacks(tick);
        if (relay != null) relay.uiVisibility(false);
        if (bound) { unbindService(connection); bound = false; }
        relay = null; preview.clear("Preview hidden; relay continues");
        super.onStop();
    }
    @Override protected void onDestroy() { ui.removeCallbacks(tick); super.onDestroy(); }
}

package edu.purdue.cs536.phone;

import android.app.*;
import android.content.*;
import android.content.pm.ServiceInfo;
import android.net.wifi.WifiManager;
import android.os.*;
import edu.purdue.cs536.common.AppUi;
import edu.purdue.cs536.stream.*;
import java.io.*;
import java.util.concurrent.atomic.AtomicReference;

/** User-started relay whose lifetime is independent of the preview activity. */
public final class RelayService extends Service {
    static final String START = "edu.purdue.cs536.phone.START_RELAY";
    static final String STOP = "edu.purdue.cs536.phone.STOP_RELAY";
    private static final String CHANNEL = "glasses-relay";
    private static final int NOTIFICATION = 536;
    private final IBinder binder = new LocalBinder();
    private final Object deliveryLock = new Object();
    private final AtomicReference<Frame> pending = new AtomicReference<>();
    private volatile int generation;
    private volatile String connectionState = "idle";
    private boolean active, paused;
    private FrameHub hub;
    private CsvTrace trace;
    private StreamServer server;
    private StreamClient client;
    private PowerManager.WakeLock cpuLock;
    private WifiManager.WifiLock wifiLock;
    private String source = "", sourceToken = "", relayToken = "", tracePath = "";
    private int port;

    public final class LocalBinder extends Binder { RelayService service() { return RelayService.this; } }

    static Intent startIntent(Context context, String source, String sourceToken, int port, String relayToken) {
        return new Intent(context, RelayService.class).setAction(START)
            .putExtra("source", source).putExtra("sourceToken", sourceToken)
            .putExtra("port", port).putExtra("relayToken", relayToken);
    }

    @Override public void onCreate() {
        super.onCreate();
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel channel = new NotificationChannel(CHANNEL, "Glasses video relay", NotificationManager.IMPORTANCE_LOW);
            channel.setDescription("Keeps the phone relay running while the screen is locked or another app is open.");
            getSystemService(NotificationManager.class).createNotificationChannel(channel);
        }
    }
    @Override public IBinder onBind(Intent intent) { return binder; }
    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null) { stopSelf(startId); return START_NOT_STICKY; }
        if (STOP.equals(intent.getAction())) {
            shutdown("notification_stop", "Stopped"); stopSelf(); return START_NOT_STICKY;
        }
        if (!START.equals(intent.getAction())) { stopSelf(startId); return START_NOT_STICKY; }
        if (active) return START_NOT_STICKY;
        try {
            source = intent.getStringExtra("source"); sourceToken = intent.getStringExtra("sourceToken");
            relayToken = intent.getStringExtra("relayToken"); port = intent.getIntExtra("port", -1);
            paused = false;
            promote();
            if (port < 1024 || port > 65535) throw new IllegalArgumentException("Use a relay port between 1024 and 65535");
            File file = AppUi.traceFile(this, "phone"); tracePath = file.getAbsolutePath();
            trace = new CsvTrace(file); hub = new FrameHub(trace);
            server = new StreamServer("0.0.0.0", port, relayToken, hub, trace);
            acquireLocks(); active = true;
            trace.event("relay_start", null, "foreground_service");
            beginClient();
        } catch (IOException | IllegalArgumentException | SecurityException e) {
            // Errors contain no source token, credentials or notification payload.
            shutdown("start_failed", "Cannot start relay: " + e.getClass().getSimpleName()); stopSelf();
        }
        // Never silently restart a camera feed after process death or explicit Stop.
        return START_NOT_STICKY;
    }
    private Notification notification() {
        int immutable = PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE;
        PendingIntent open = PendingIntent.getActivity(this, 0,
            new Intent(this, PhoneActivity.class).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP), immutable);
        PendingIntent stop = PendingIntent.getService(this, 1,
            new Intent(this, RelayService.class).setAction(STOP), immutable);
        Notification.Builder builder = Build.VERSION.SDK_INT >= 26
            ? new Notification.Builder(this, CHANNEL) : new Notification.Builder(this);
        return builder.setSmallIcon(edu.purdue.cs536.phone.R.drawable.ic_phone)
            .setContentTitle("Glasses video relay")
            .setContentText(paused ? "Paused. Tap to resume or stop." : "Running. Video continues with the phone locked.")
            .setContentIntent(open).setOngoing(true).setOnlyAlertOnce(true)
            .setVisibility(Notification.VISIBILITY_PRIVATE)
            .addAction(new Notification.Action.Builder(android.graphics.drawable.Icon.createWithResource(this, android.R.drawable.ic_menu_close_clear_cancel), "Stop", stop).build()).build();
    }
    private void promote() {
        if (Build.VERSION.SDK_INT >= 29) startForeground(NOTIFICATION, notification(), ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE);
        else startForeground(NOTIFICATION, notification());
    }
    @android.annotation.SuppressLint("WakelockTimeout") // User-started stream; released on Pause, Stop, startup failure and destruction.
    private void acquireLocks() {
        if (cpuLock == null) {
            cpuLock = ((PowerManager)getSystemService(POWER_SERVICE)).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, getPackageName()+":relay");
            cpuLock.setReferenceCounted(false);
        }
        if (!cpuLock.isHeld()) cpuLock.acquire();
        if (wifiLock == null) {
            WifiManager wifi = (WifiManager)getApplicationContext().getSystemService(WIFI_SERVICE);
            wifiLock = wifi.createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, getPackageName()+":relay");
            wifiLock.setReferenceCounted(false);
        }
        if (!wifiLock.isHeld()) wifiLock.acquire();
    }
    private void releaseLocks() {
        if (wifiLock != null && wifiLock.isHeld()) wifiLock.release();
        if (cpuLock != null && cpuLock.isHeld()) cpuLock.release();
    }
    private void beginClient() throws IOException {
        final int session = ++generation; final FrameHub destination = hub;
        client = new StreamClient(source, sourceToken, new StreamClient.Listener() {
            @Override public void frame(Frame frame) {
                synchronized (deliveryLock) {
                    if (session != generation) return;
                    if (destination.publish(frame)) { pending.set(frame); connectionState = "streaming"; }
                }
            }
            @Override public void state(String state) {
                synchronized (deliveryLock) {
                    if (session != generation) return;
                    connectionState = state; destination.clear(state); pending.set(null);
                }
            }
        }, trace);
        client.start();
    }
    void togglePause() {
        if (!active) return;
        paused = !paused;
        if (paused) {
            synchronized (deliveryLock) { generation++; hub.clear("paused"); pending.set(null); connectionState = "paused"; }
            client.close(); client = null; releaseLocks();
        } else {
            try { acquireLocks(); beginClient(); }
            catch (IOException | SecurityException e) { shutdown("resume_failed", "Cannot resume relay"); stopSelf(); return; }
        }
        promote();
    }
    void stopRelay() { shutdown("user_stop", "Stopped"); stopSelf(); }
    private void shutdown(String reason, String status) {
        if (trace != null) trace.event("relay_stop", null, reason);
        synchronized (deliveryLock) { active = false; paused = false; generation++; if (hub != null) hub.close(); pending.set(null); }
        if (client != null) client.close(); client = null;
        if (server != null) server.close(); server = null;
        AppUi.closeTrace(trace); trace = null; hub = null;
        releaseLocks(); connectionState = status;
        if (Build.VERSION.SDK_INT >= 24) stopForeground(STOP_FOREGROUND_REMOVE);
        else stopForeground(true);
    }
    boolean active() { return active; }
    boolean paused() { return paused; }
    Frame takePreview() { return active && !paused ? pending.getAndSet(null) : null; }
    String state() { return active && !paused && hub != null && hub.ageMs() > FrameHub.FRESH_MS ? "Stream stalled; waiting for reconnect" : connectionState; }
    long frames() { return hub == null ? 0 : hub.frames(); }
    long ageMs() { return hub == null ? -1 : hub.ageMs(); }
    String traceError() { return trace == null ? "" : trace.error(); }
    String addresses() { return AppUi.addresses(port)+"\nTrace: "+tracePath; }
    String source() { return source; }
    String sourceToken() { return sourceToken; }
    String relayToken() { return relayToken; }
    int port() { return port; }
    void displayed(Frame frame) { if (trace != null) trace.event("frame_displayed", frame, ""); }
    void uiVisibility(boolean visible) { if (trace != null) trace.event("preview_visibility", null, visible ? "visible" : "hidden_relay_continues"); }
    @Override public void onTaskRemoved(Intent rootIntent) { shutdown("task_removed", "Stopped"); stopSelf(); }
    @Override public void onDestroy() { shutdown("service_destroyed", "Stopped"); super.onDestroy(); }
}

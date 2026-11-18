package edu.purdue.cs536.phone;

import android.app.*;
import android.content.*;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.os.*;
import edu.purdue.cs536.stream.*;
import java.io.*;
import java.net.ServerSocket;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/** Physical-phone lifecycle regression with a labeled synthetic network source.
 * It validates relay behavior, not Wi-Fi coverage or glasses-domain inference.
 */
public final class RelayLifecycleInstrumentation extends Instrumentation {
    private Context context;
    private RelayService relay;
    private Activity activity;
    private ServiceConnection binding;
    private StreamServer camera;
    private FrameHub cameraHub;
    private StreamClient observer;
    private final AtomicBoolean producing = new AtomicBoolean();
    private final AtomicLong delivered = new AtomicLong(), lastSequence = new AtomicLong(-1);
    private final AtomicReference<Throwable> frameError = new AtomicReference<>();
    private final AtomicReference<FrameHub> source = new AtomicReference<>();
    private int checks, sourcePort, relayPort;
    private Intent start;
    private final String sourceToken = "source-test-token", relayToken = "relay-test-token";
    @Override public void onCreate(Bundle arguments) { super.onCreate(arguments); start(); }
    private void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message); checks++;
    }
    private void phase(String name) {
        Bundle status = new Bundle(); status.putString("phase",name); status.putLong("delivered_frames",delivered.get()); sendStatus(0,status);
    }
    private void command(String command) throws IOException { getUiAutomation().executeShellCommand(command).close(); }
    private boolean active() {
        AtomicBoolean result = new AtomicBoolean(); runOnMainSync(() -> result.set(relay.active())); return result.get();
    }
    private void advancing(String name, int seconds) throws Exception {
        long before = delivered.get(); phase(name); Thread.sleep(seconds*1000L);
        require(frameError.get() == null, "Invalid or duplicate relay frame: "+frameError.get());
        require(active(), "Relay stopped during "+name);
        require(delivered.get()-before >= seconds*4L, "Relay did not keep delivering during "+name);
    }
    private void awaitFrames() throws Exception {
        long initial = delivered.get(), deadline = SystemClock.elapsedRealtime()+12000;
        while (delivered.get() < initial+8 && SystemClock.elapsedRealtime()<deadline) Thread.sleep(100);
        require(delivered.get()>=initial+8,"No fresh frames after start/reconnect");
    }
    private void observe() throws IOException {
        observer = new StreamClient("http://127.0.0.1:"+relayPort,relayToken,new StreamClient.Listener() {
            @Override public void frame(Frame frame) {
                long previous = lastSequence.getAndSet(frame.sequence);
                if (!"lifecycle-source".equals(frame.session) || frame.sequence<=previous || frame.width!=32 || frame.height!=32)
                    frameError.compareAndSet(null,new AssertionError("Frame identity/dimensions changed or sequence repeated"));
                delivered.incrementAndGet();
            }
            @Override public void state(String state) { }
        },edu.purdue.cs536.stream.Trace.NONE); observer.start();
    }
    @Override public void onStart() {
        Bundle result = new Bundle();
        int resultCode = Activity.RESULT_OK;
        try {
            context = getTargetContext();
            cameraHub = new FrameHub(edu.purdue.cs536.stream.Trace.NONE); source.set(cameraHub);
            camera = new StreamServer("127.0.0.1",0,sourceToken,cameraHub,edu.purdue.cs536.stream.Trace.NONE); sourcePort=camera.port();
            try (ServerSocket reserve = new ServerSocket(0)) { relayPort=reserve.getLocalPort(); }
            Bitmap image = Bitmap.createBitmap(32,32,Bitmap.Config.ARGB_8888);image.eraseColor(Color.CYAN);
            ByteArrayOutputStream jpeg=new ByteArrayOutputStream();image.compress(Bitmap.CompressFormat.JPEG,80,jpeg);image.recycle();
            byte[] bytes=jpeg.toByteArray();producing.set(true);
            Thread producer=new Thread(() -> {
                long sequence=0;
                while(producing.get()) {
                    FrameHub destination=source.get();
                    if(destination!=null)destination.publish(new Frame("lifecycle-source",sequence++,System.nanoTime(),System.currentTimeMillis(),32,32,bytes));
                    try { Thread.sleep(125); } catch(InterruptedException e) { return; }
                }
            },"synthetic-camera");producer.setDaemon(true);producer.start();
            activity=startActivitySync(new Intent(context,PhoneActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            CountDownLatch connected=new CountDownLatch(1);
            binding=new ServiceConnection() {
                @Override public void onServiceConnected(ComponentName name,IBinder binder) {relay=((RelayService.LocalBinder)binder).service();connected.countDown();}
                @Override public void onServiceDisconnected(ComponentName name) { }
            };
            require(context.bindService(new Intent(context,RelayService.class),binding,Context.BIND_AUTO_CREATE),"Cannot bind relay");
            require(connected.await(10,TimeUnit.SECONDS),"Relay binding timeout");
            start=RelayService.startIntent(context,"http://127.0.0.1:"+sourcePort,sourceToken,relayPort,relayToken);
            runOnMainSync(() -> { if(Build.VERSION.SDK_INT>=26)context.startForegroundService(start);else context.startService(start); });
            observe();awaitFrames();advancing("foreground",6);
            command("input keyevent 3");advancing("home_background",10);
            // Return to the existing task without waiting for a new Activity or removing the task.
            runOnMainSync(() -> context.startActivity(new Intent(context,PhoneActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)));
            waitForIdleSync();
            advancing("return_to_preview",6);
            runOnMainSync(() -> activity.recreate());advancing("activity_recreation",8);
            runOnMainSync(() -> relay.togglePause());Thread.sleep(3000);long pausedAt=delivered.get();Thread.sleep(3000);
            require(delivered.get()==pausedAt,"Frames delivered while paused");
            AtomicReference<String> pausedState=new AtomicReference<>();runOnMainSync(() -> pausedState.set(relay.state()));
            require("paused".equals(pausedState.get()),"Paused relay mislabeled as stalled");
            runOnMainSync(() -> relay.togglePause());awaitFrames();advancing("resume",6);
            phase("source_outage");source.set(null);camera.close();cameraHub.close();Thread.sleep(6500);
            long outageAt=delivered.get();Thread.sleep(2000);require(delivered.get()==outageAt,"Stale frames replayed during source outage");
            cameraHub=new FrameHub(edu.purdue.cs536.stream.Trace.NONE);camera=new StreamServer("127.0.0.1",sourcePort,sourceToken,cameraHub,edu.purdue.cs536.stream.Trace.NONE);source.set(cameraHub);
            awaitFrames();advancing("automatic_source_reconnect",8);
            command("input keyevent 223");Thread.sleep(1000);
            require(!((PowerManager)context.getSystemService(Context.POWER_SERVICE)).isInteractive(),"Screen did not lock/sleep");
            advancing("screen_off_120_seconds",120);
            NotificationManager manager=(NotificationManager)context.getSystemService(Context.NOTIFICATION_SERVICE);
            result.putBoolean("notifications_enabled",manager.areNotificationsEnabled());
            Notification notification=null;
            for(android.service.notification.StatusBarNotification item:manager.getActiveNotifications())if(item.getId()==536)notification=item.getNotification();
            require(notification!=null && notification.actions!=null && notification.actions.length>0,"Missing foreground notification Stop action");
            notification.actions[0].actionIntent.send();Thread.sleep(3000);
            require(!active(),"Notification Stop did not stop relay");long stoppedAt=delivered.get();Thread.sleep(3000);
            require(delivered.get()==stoppedAt,"Frames delivered after Stop");
            require(manager.getActiveNotifications().length==0,"Relay notification remained after Stop");
            phase("all_checks_passed");result.putString("result","PASS");result.putInt("assertions",checks);result.putLong("delivered_frames",delivered.get());
            result.putString("scope","Physical Android lifecycle test with synthetic localhost source; not Wi-Fi/glasses inference validation");

        } catch(Throwable failure) {
            result.putString("result","FAIL");result.putString("failure",failure.toString());result.putInt("assertions",checks);resultCode=Activity.RESULT_CANCELED;
        } finally {
            producing.set(false);if(observer!=null)observer.close();if(camera!=null)camera.close();if(cameraHub!=null)cameraHub.close();
            if(relay!=null)runOnMainSync(() -> relay.stopRelay());
            if(binding!=null)try{context.unbindService(binding);}catch(IllegalArgumentException ignored){}
            try { command("input keyevent 224"); }catch(IOException ignored){}
        }
        finish(resultCode,result);
    }
}

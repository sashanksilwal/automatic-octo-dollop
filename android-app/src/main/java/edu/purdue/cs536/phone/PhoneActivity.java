package edu.purdue.cs536.phone;

import android.app.Activity;
import android.content.SharedPreferences;
import android.os.*;
import android.widget.*;
import edu.purdue.cs536.common.*;
import edu.purdue.cs536.stream.*;
import java.io.*;
import java.util.concurrent.atomic.AtomicReference;

@android.annotation.SuppressLint("SetTextI18n") // English-only course prototype and live diagnostic values.
public final class PhoneActivity extends Activity {
    private final Handler ui = new Handler(Looper.getMainLooper());
    private final AtomicReference<Frame> pending = new AtomicReference<>();
    private final Object deliveryLock = new Object();
    private EditText source, sourceToken, relayPort, relayToken;
    private Button start,pause,stop;
    private TextView status,addresses,stats;
    private FramePreview preview;
    private volatile String connectionState = "idle";
    private boolean active,paused;
    private volatile int generation;
    private FrameHub hub;
    private CsvTrace trace;
    private StreamServer server;
    private StreamClient client;
    private SharedPreferences preferences;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state); preferences=getPreferences(MODE_PRIVATE);
        LinearLayout root=AppUi.root(this,"CS536 · Phone receiver");
        preview=new FramePreview(this); root.addView(preview,new LinearLayout.LayoutParams(-1,AppUi.dp(this,190)));
        LinearLayout form=AppUi.form(this,root);
        status=AppUi.text(this,form,"Enter the glasses address and pairing code.");
        source=field(form,"Glasses base address","source","http://192.168.1.20:8080",false);
        sourceToken=field(form,"Glasses pairing code","sourceToken","",false);
        relayPort=field(form,"Phone relay port","relayPort","8081",true);
        relayToken=field(form,"Phone pairing code (for the laptop)","relayToken",AppUi.code(),false);
        addresses=AppUi.text(this,form,AppUi.addresses(8081)); addresses.setTextIsSelectable(true);
        stats=AppUi.text(this,form,"No frames yet");
        start=AppUi.button(this,form,"Connect and relay",this::startStream);
        pause=AppUi.button(this,form,"Pause",this::togglePause);
        stop=AppUi.button(this,form,"Stop",()->stopStream("Stopped"));
        updateButtons(); ui.post(tick);
    }
    private EditText field(LinearLayout form,String label,String key,String fallback,boolean number) {
        return AppUi.field(this,form,label,preferences.getString(key,fallback),number);
    }
    private void startStream() {
        if(active) return;
        try {
            int port=AppUi.number(relayPort,1024,65535);
            File file=AppUi.traceFile(this,"phone"); trace=new CsvTrace(file); hub=new FrameHub(trace);
            server=new StreamServer("0.0.0.0",port,relayToken.getText().toString().trim(),hub,trace);
            active=true; paused=false;
            beginClient();
            preferences.edit().putString("source",source.getText().toString().trim()).putString("sourceToken",sourceToken.getText().toString().trim())
                .putString("relayPort",relayPort.getText().toString()).putString("relayToken",relayToken.getText().toString().trim()).apply();
            addresses.setText(AppUi.addresses(port)+"\nTrace: "+file.getAbsolutePath()); updateButtons();
        } catch(IOException | IllegalArgumentException e) { stopStream("Cannot start: "+e.getMessage()); }
    }
    private void beginClient() throws IOException {
        final int session=++generation; final FrameHub destination=hub;
        client=new StreamClient(source.getText().toString().trim(),sourceToken.getText().toString().trim(),new StreamClient.Listener() {
            @Override public void frame(Frame frame) {
                synchronized(deliveryLock) {
                    if(session!=generation) return;
                    if(destination.publish(frame)) { pending.set(frame); connectionState="streaming"; }
                }
            }
            @Override public void state(String text) {
                synchronized(deliveryLock) {
                    if(session!=generation) return;
                    connectionState=text; destination.clear(text); pending.set(null);
                }
            }
        },trace);
        client.start();
    }
    private void togglePause() {
        if(!active) return;
        paused=!paused;
        if(paused) {
            synchronized(deliveryLock) { generation++; hub.clear("paused"); pending.set(null); connectionState="paused"; }
            client.close(); client=null; preview.clear("Paused");
        } else {
            try { beginClient(); } catch(IOException e) { stopStream("Cannot resume: "+e.getMessage()); }
        }
        updateButtons();
    }
    private void stopStream(String reason) {
        synchronized(deliveryLock) { active=false; paused=false; generation++; if(hub!=null) hub.close(); pending.set(null); }
        if(client!=null) client.close(); client=null;
        if(server!=null) server.close(); server=null;
        AppUi.closeTrace(trace); trace=null; hub=null; pending.set(null);
        connectionState=reason; status.setText(reason); preview.clear(reason); updateButtons();
    }
    private void updateButtons() {
        start.setEnabled(!active);pause.setEnabled(active);stop.setEnabled(active);pause.setText(paused?"Resume":"Pause");
        for(EditText e:new EditText[]{source,sourceToken,relayPort,relayToken}) e.setEnabled(!active);
    }
    private final Runnable tick=new Runnable() { @Override public void run() {
        if(active && hub!=null) {
            Frame frame=pending.getAndSet(null);
            if(frame!=null && !paused && preview.show(frame)) trace.event("frame_displayed",frame,"");
            long age=hub.ageMs();
            if(paused || !connectionState.equals("streaming") || age>FrameHub.FRESH_MS) preview.clear(paused?"Paused":"Waiting for fresh video");
            status.setText(age>FrameHub.FRESH_MS && connectionState.equals("streaming")?"Stream stalled; waiting for reconnect":connectionState);
            stats.setText("Received: "+hub.frames()+" frames · last frame "+age+" ms ago"
                +(trace.error().isEmpty()?"":"\n"+trace.error()));
        }
        ui.postDelayed(this,100);
    }};
    @Override protected void onStop() { super.onStop(); if(active) stopStream("App left foreground; relay stopped"); }
    @Override protected void onDestroy() { ui.removeCallbacks(tick); super.onDestroy(); }
}

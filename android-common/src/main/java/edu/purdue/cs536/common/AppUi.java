package edu.purdue.cs536.common;

import android.app.Activity;
import android.graphics.Color;
import android.os.Build;
import android.text.InputType;
import android.view.*;
import android.widget.*;
import edu.purdue.cs536.stream.CsvTrace;
import java.io.*;
import java.net.*;
import java.util.*;

public final class AppUi {
    private AppUi() { }
    public static int dp(Activity a, int n) { return Math.round(n * a.getResources().getDisplayMetrics().density); }
    public static LinearLayout root(Activity a, String title) {
        a.getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        LinearLayout root = new LinearLayout(a); root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(15, 21, 31));
        int pad = dp(a, 12); root.setPadding(pad, pad, pad, pad);
        root.setOnApplyWindowInsetsListener((v, insets) -> {
            if (Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
                v.setPadding(pad + bars.left, pad + bars.top, pad + bars.right, pad + bars.bottom);
            } else {
                v.setPadding(pad + insets.getSystemWindowInsetLeft(), pad + insets.getSystemWindowInsetTop(),
                    pad + insets.getSystemWindowInsetRight(), pad + insets.getSystemWindowInsetBottom());
            }
            return insets;
        });
        a.setContentView(root);
        TextView heading = text(a, root, title); heading.setTextSize(22); return root;
    }
    public static TextView text(Activity a, LinearLayout parent, String value) {
        TextView t = new TextView(a); t.setText(value); t.setTextSize(14);
        t.setTextColor(Color.rgb(224, 233, 245)); t.setPadding(0, dp(a, 5), 0, dp(a, 5));
        parent.addView(t); return t;
    }
    public static LinearLayout form(Activity a, LinearLayout root) {
        ScrollView scroll = new ScrollView(a); root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        LinearLayout form = new LinearLayout(a); form.setOrientation(LinearLayout.VERTICAL); scroll.addView(form); return form;
    }
    public static EditText field(Activity a, LinearLayout parent, String label, String initial, boolean number) {
        TextView name = text(a, parent, label);
        EditText edit = new EditText(a); edit.setId(View.generateViewId()); name.setLabelFor(edit.getId());
        edit.setSingleLine(true); edit.setText(initial); edit.setTextColor(Color.WHITE);
        edit.setInputType(number ? InputType.TYPE_CLASS_NUMBER : InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        parent.addView(edit, new LinearLayout.LayoutParams(-1, -2)); return edit;
    }
    public static Button button(Activity a, LinearLayout parent, String name, Runnable action) {
        Button b = new Button(a); b.setText(name); b.setAllCaps(false); b.setOnClickListener(v -> action.run()); parent.addView(b); return b;
    }
    public static String code() { return UUID.randomUUID().toString().replace("-", "").substring(0, 12); }
    public static int number(EditText field, int min, int max) {
        int value;
        try { value = Integer.parseInt(field.getText().toString().trim()); }
        catch (NumberFormatException e) { throw new IllegalArgumentException("Enter a number between " + min + " and " + max); }
        if (value < min || value > max) throw new IllegalArgumentException("Value must be between " + min + " and " + max);
        return value;
    }
    public static String addresses(int port) {
        List<String> result = new ArrayList<>();
        try {
            for (NetworkInterface n : Collections.list(NetworkInterface.getNetworkInterfaces())) {
                if (!n.isUp() || n.isLoopback()) continue;
                for (InetAddress address : Collections.list(n.getInetAddresses())) {
                    if (address instanceof Inet4Address) result.add(n.getName() + ": http://" + address.getHostAddress() + ":" + port);
                }
            }
        } catch (SocketException e) { return "Network addresses unavailable"; }
        return result.isEmpty() ? "No IPv4 network address. Connect Wi-Fi or use adb forwarding." : android.text.TextUtils.join("\n", result);
    }
    public static File traceFile(Activity a, String role) throws IOException {
        File base = a.getExternalFilesDir(null);
        if (base == null) base = a.getFilesDir();
        File directory = new File(base, "traces");
        if (!directory.isDirectory() && !directory.mkdirs()) throw new IOException("Cannot create trace directory");
        return new File(directory, role + "-" + System.currentTimeMillis() + "-" + code() + ".csv");
    }
    public static void closeTrace(CsvTrace trace) { if (trace != null) try { trace.close(); } catch (IOException ignored) { } }
}

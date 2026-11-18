import android.content.Context;
import android.net.wifi.*;
import android.os.Looper;
import java.io.*;
import java.lang.reflect.*;
import java.security.*;
import java.security.cert.*;
import java.util.*;

public class PalCertificateFix {
  public static void main(String[] args) {
    int status=0;
    try { fix(); } catch(Exception e) { System.out.println("SETUP_ERROR: "+e.getClass().getSimpleName()); status=1; }
    System.exit(status);
  }
  static void fix() throws Exception {
    List<X509Certificate> roots=new ArrayList<>();
    for(java.security.cert.Certificate certificate:CertificateFactory.getInstance("X.509").generateCertificates(System.in)) {
      X509Certificate ca=(X509Certificate)certificate;
      StringBuilder hash=new StringBuilder();
      for(byte b:MessageDigest.getInstance("SHA-256").digest(ca.getEncoded())) hash.append(String.format("%02x",b&255));

      if(!Arrays.asList("cef71e70b7c29addf6c30cd19e614b38fd5f02a435a0eeddd0087e183d101a51","8faf7d2e2cb4709bb8e0b33666bf75a5dd45b5de480f8ea8d4bfe6bebc17f2ed").contains(hash.toString()))throw new SecurityException();
      ca.checkValidity();ca.verify(ca.getPublicKey());if(ca.getBasicConstraints()<0)throw new SecurityException();roots.add(ca);
    }

    if(roots.size()!=2)throw new SecurityException();
    Looper.prepareMainLooper();
    Class<?> cls=Class.forName("android.app.ActivityThread");
    Constructor<?> ctor=cls.getDeclaredConstructor(); ctor.setAccessible(true);
    Object thread=ctor.newInstance();
    Context system=(Context)cls.getMethod("getSystemContext").invoke(thread);
    Context shell=system.createPackageContext("com.android.shell",Context.CONTEXT_IGNORE_SECURITY);
    WifiManager wifi=(WifiManager)shell.getSystemService(Context.WIFI_SERVICE);
    WifiConfiguration target=null;
    for(WifiConfiguration c:wifi.getConfiguredNetworks()) if("\"PAL3.0\"".equals(c.SSID)) target=c;
    if(target==null) throw new IllegalStateException();
    // Android retains the existing password when its masked value is returned.
    // Change only this network's CA trust and expected server domain.
    WifiEnterpriseConfig.class.getMethod("setCaPath",String.class).invoke(target.enterpriseConfig,new Object[]{null});
    target.enterpriseConfig.setCaCertificates(roots.toArray(new X509Certificate[0]));
    target.enterpriseConfig.setDomainSuffixMatch("purdue.edu");
    int id=wifi.updateNetwork(target);
    if(id<0) { System.out.println("SETUP_REJECTED: Certificate update rejected."); return; }
    System.out.println("Certificate updated for PAL3.0 only; verification enabled.");
    wifi.disconnect();
    if(!wifi.enableNetwork(id,true)||!wifi.reconnect()) { System.out.println("CONNECT_REJECTED"); return; }
    for(int i=0;i<40;i++) {
      WifiInfo info=wifi.getConnectionInfo();
      if(("PAL3.0".equals(info.getSSID())||"\"PAL3.0\"".equals(info.getSSID()))&&info.getIpAddress()!=0) {
        int ip=info.getIpAddress();
        System.out.println("CONNECTED: "+(ip&255)+"."+((ip>>8)&255)+"."+((ip>>16)&255)+"."+((ip>>24)&255)); return;
      }
      Thread.sleep(1000);
    }
    System.out.println("NOT_CONNECTED: Still waiting for PAL3.0.");
  }
}

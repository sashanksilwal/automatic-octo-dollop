import android.content.Context;
import android.net.wifi.*;
import android.os.Looper;
import java.io.*;
import java.lang.reflect.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

public class PalConnect {
  public static void main(String[] args) {
    int status=0;
    try {
      if(args.length==1&&"--check".equals(args[0])) {
        WifiEnterpriseConfig check=new WifiEnterpriseConfig();
        WifiEnterpriseConfig.class.getMethod("setCaPath",String.class).invoke(check,"/system/etc/security/cacerts");
        check.setDomainSuffixMatch("purdue.edu");
        System.out.println("CHECK_OK: System certificate validation is available.");
      } else connect();
    }
    catch(Exception e) { System.out.println("SETUP_ERROR: "+e.getClass().getSimpleName()); status=1; }
    System.exit(status);
  }
  static void connect() throws Exception {
    BufferedReader input=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8));
    String username=input.readLine(),password=input.readLine();
    if(username==null||password==null||username.isEmpty()||password.isEmpty()) throw new IllegalArgumentException();
    Looper.prepareMainLooper();
    Class<?> cls=Class.forName("android.app.ActivityThread");
    Constructor<?> ctor=cls.getDeclaredConstructor(); ctor.setAccessible(true);
    Object thread=ctor.newInstance();
    Context system=(Context)cls.getMethod("getSystemContext").invoke(thread);
    Context shell=system.createPackageContext("com.android.shell",Context.CONTEXT_IGNORE_SECURITY);
    WifiManager wifi=(WifiManager)shell.getSystemService(Context.WIFI_SERVICE);
    WifiConfiguration config=new WifiConfiguration();
    config.SSID="\"PAL3.0\"";
    config.allowedKeyManagement.set(WifiConfiguration.KeyMgmt.WPA_EAP);
    config.allowedKeyManagement.set(WifiConfiguration.KeyMgmt.IEEE8021X);
    WifiEnterpriseConfig enterprise=new WifiEnterpriseConfig();
    enterprise.setEapMethod(WifiEnterpriseConfig.Eap.PEAP);
    enterprise.setPhase2Method(WifiEnterpriseConfig.Phase2.MSCHAPV2);
    enterprise.setIdentity(username);
    enterprise.setPassword(password);
    enterprise.setDomainSuffixMatch("purdue.edu");
    // Require system CA validation; fail rather than disable certificate checks.
    List<java.security.cert.X509Certificate> roots=new ArrayList<>();
    try(InputStream inputRoots=new FileInputStream("/data/local/tmp/cs536-pal-roots.p7b")) {
      for(java.security.cert.Certificate cert:java.security.cert.CertificateFactory.getInstance("X.509").generateCertificates(inputRoots)) {
        java.security.cert.X509Certificate ca=(java.security.cert.X509Certificate)cert;
        StringBuilder hash=new StringBuilder();
        for(byte b:java.security.MessageDigest.getInstance("SHA-256").digest(ca.getEncoded()))hash.append(String.format("%02x",b&255));
        if(!Arrays.asList("cef71e70b7c29addf6c30cd19e614b38fd5f02a435a0eeddd0087e183d101a51","8faf7d2e2cb4709bb8e0b33666bf75a5dd45b5de480f8ea8d4bfe6bebc17f2ed").contains(hash.toString()))throw new SecurityException();
        ca.checkValidity();ca.verify(ca.getPublicKey());if(ca.getBasicConstraints()<0)throw new SecurityException();roots.add(ca);
      }
    }
    if(roots.size()!=2)throw new SecurityException();
    enterprise.setCaCertificates(roots.toArray(new java.security.cert.X509Certificate[0]));
    config.enterpriseConfig=enterprise;
    List<WifiConfiguration> saved=wifi.getConfiguredNetworks();
    if(saved!=null) for(WifiConfiguration old:saved)
      if("\"PAL3.0\"".equals(old.SSID)) config.networkId=old.networkId;
    int id=wifi.addNetwork(config);
    username=password=null;
    if(id<0) { System.out.println("SETUP_REJECTED: Android rejected the network profile."); return; }
    if(!wifi.enableNetwork(id,true)||!wifi.reconnect()) { System.out.println("CONNECT_REJECTED: Android could not start the connection."); return; }
    for(int i=0;i<25;i++) {
      WifiInfo info=wifi.getConnectionInfo();
      if(("PAL3.0".equals(info.getSSID())||"\"PAL3.0\"".equals(info.getSSID()))&&info.getIpAddress()!=0) {
        int ip=info.getIpAddress();
        System.out.println("CONNECTED: "+(ip&255)+"."+((ip>>8)&255)+"."+((ip>>16)&255)+"."+((ip>>24)&255)); return;
      }
      Thread.sleep(1000);
    }
    System.out.println("NOT_CONNECTED: No PAL3.0 address within 25 seconds. Check credentials and network availability.");
  }
}

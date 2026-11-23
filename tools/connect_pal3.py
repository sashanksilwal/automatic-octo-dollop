#!/usr/bin/env python3
"""Reconnect USB-attached AIR2 to PAL3.0 using verified roots, without logging credentials."""
import argparse,hashlib,json,os,re,ssl,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ADB=ROOT/'.tools/android-sdk/platform-tools/adb'
SOURCE=ROOT/'tools/pal3'
CACHE=ROOT/'.tools/pal3-demo-cache'
SERIAL='YM00DEC8P06371'
PINS={'emsign-root-tls-g1.pem':'cef71e70b7c29addf6c30cd19e614b38fd5f02a435a0eeddd0087e183d101a51','sslcom-tls-rsa-root-2022.pem':'8faf7d2e2cb4709bb8e0b33666bf75a5dd45b5de480f8ea8d4bfe6bebc17f2ed'}

def run(*args,**kw):return subprocess.run([str(a) for a in args],check=True,**kw)
def shell(*args,**kw):return run(ADB,'-s',SERIAL,'shell',*args,**kw)
def connected():
    wifi=shell('dumpsys','wifi',capture_output=True,text=True).stdout
    return any(l.strip().startswith('mWifiInfo') and any(x in l for x in ['SSID: PAL3.0,','SSID: "PAL3.0",']) and 'COMPLETED' in l for l in wifi.splitlines())
def show_ip():
    text=shell('ip','-4','addr','show','wlan0',capture_output=True,text=True).stdout
    ip=re.search(r'inet ([0-9.]+)/',text)
    print('Glasses connected to PAL3.0. Address: '+(ip.group(1) if ip else 'waiting for DHCP'),flush=True)
def prepare():
    CACHE.mkdir(parents=True,exist_ok=True)
    for name,pin in PINS.items():
        cert=(SOURCE/'certificates'/name).read_text()
        if hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert)).hexdigest()!=pin:raise ValueError('Certificate fingerprint mismatch: '+name)
    bundle=CACHE/'roots.p7b'
    run('openssl','crl2pkcs7','-nocrl','-certfile',SOURCE/'certificates/emsign-root-tls-g1.pem','-certfile',SOURCE/'certificates/sslcom-tls-rsa-root-2022.pem','-outform','DER','-out',bundle)
    java=ROOT/'.tools/jdk/Contents/Home';sdk=ROOT/'.tools/android-sdk';jar=sdk/'platforms/android-35/android.jar'
    classes=CACHE/'classes';dex=CACHE/'dex';classes.mkdir(exist_ok=True);dex.mkdir(exist_ok=True)
    run(java/'bin/javac','--release','8','-cp',jar,'-d',classes,SOURCE/'PalCertificateFix.java',SOURCE/'PalConnect.java')
    run(sdk/'build-tools/35.0.0/d8','--min-api','28','--lib',jar,'--output',dex,classes/'PalCertificateFix.class',classes/'PalConnect.class',env={**os.environ,'JAVA_HOME':str(java)})
    return dex/'classes.dex',bundle

def main():
    global SERIAL
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--serial',default=SERIAL,help='Glasses serial from adb devices');p.add_argument('--refresh-login',action='store_true',help='Open a laptop-only credential form if saved authentication fails');p.add_argument('--prepare-only',action='store_true',help='Validate certificates and compile helpers without touching devices');a=p.parse_args()
    SERIAL=a.serial
    if not a.prepare_only and not a.refresh_login and connected():show_ip();return
    dex,bundle=prepare()
    if a.prepare_only:print('Certificate pins verified and helper compiled. No device changes.');return
    run(ADB,'-s',SERIAL,'push',dex,'/data/local/tmp/cs536-pal-setup.dex');run(ADB,'-s',SERIAL,'push',bundle,'/data/local/tmp/cs536-pal-roots.p7b')
    if a.refresh_login:
        # Credentials flow directly from localhost to the glasses via stdin.
        import runpy
        runpy.run_path(str(SOURCE/'local_form.py'),run_name='__main__',init_globals={'SERIAL':SERIAL});return
    result=shell('CLASSPATH=/data/local/tmp/cs536-pal-setup.dex app_process / PalCertificateFix',input=bundle.read_bytes(),capture_output=True,timeout=55)
    print(result.stdout.decode(errors='replace'),flush=True)
    if connected():show_ip()
    else:
        print('Not connected yet. To refresh login: python3 tools/connect_pal3.py --refresh-login',flush=True)
        raise SystemExit(2)
if __name__=='__main__':main()

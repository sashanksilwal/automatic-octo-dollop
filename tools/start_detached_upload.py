#!/usr/bin/env python3
"""Launch the transport helper detached from USB; use only between measured runs."""
import argparse
import json
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
ADB=ROOT/'.tools/android-sdk/platform-tools/adb'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--device',default='c1a1aa06')
    p.add_argument('--pairing-file',type=Path,required=True)
    p.add_argument('--tunnel-file',type=Path,required=True)
    p.add_argument('--token-file',type=Path,required=True)
    p.add_argument('--remote-trace',required=True)
    p.add_argument('--state-output',type=Path,required=True)
    a=p.parse_args()
    if not re.fullmatch(r'/data/local/tmp/[A-Za-z0-9_.-]+\.csv',a.remote_trace):p.error('Use a new CSV under /data/local/tmp/')
    def adb(*args,**kwargs):return subprocess.check_output([str(ADB),'-s',a.device,*args],**kwargs)
    processes=adb('shell','ps','-A','-o','PID,ARGS',text=True)
    if any('app_process / CellularUpload ' in row for row in processes.splitlines()):
        raise RuntimeError('Stop the existing uploader after its field batch before launching a detached replacement')
    exists=subprocess.run([str(ADB),'-s',a.device,'shell','test','-e',a.remote_trace],capture_output=True)
    if exists.returncode==0:raise FileExistsError('Choose a new remote trace; existing evidence will not be overwritten')
    config=json.loads(a.pairing_file.read_text());url=a.tunnel_file.read_text().strip();token=a.token_file.read_text().strip()
    if not url.startswith('https://') or '\n' in url or '\n' in token:raise ValueError('HTTPS bridge configuration required')
    data='\n'.join(['http://127.0.0.1:8081',config['phone_code'],url,token])+'\n'
    remote='/data/local/tmp/cs536-upload-'+secrets.token_hex(12)+'.cfg'
    logfile=a.remote_trace[:-4]+'.log'
    try:
        with tempfile.TemporaryDirectory(prefix='cs536-upload-') as folder:
            local=Path(folder)/'config';local.write_text(data);local.chmod(0o600)
            adb('push',str(local),remote,stderr=subprocess.DEVNULL)
        adb('shell','chmod','600',remote)
        command=('CLASSPATH=/data/local/tmp/cs536-cellular.dex /system/bin/nohup /system/bin/setsid '
                 'app_process / CellularUpload '+shlex.quote(a.remote_trace)+' < '+shlex.quote(remote)+
                 ' > '+shlex.quote(logfile)+' 2>&1 & echo $!')
        output=adb('shell',command,text=True).strip()
        if not output.isdigit():raise RuntimeError('Detached helper did not return a process ID')
        pid=int(output);connected=False
        deadline=time.monotonic()+25
        while time.monotonic()<deadline:
            text=adb('shell','cat',logfile,text=True)
            if 'Live WSS bridge connected' in text:connected=True;break
            time.sleep(1)
        a.state_output.parent.mkdir(parents=True,exist_ok=True)
        state={'device':a.device,'pid':pid,'remote_trace':a.remote_trace,'remote_log':logfile,
               'detached_from_usb':True,'wss_connected':connected,'usb_disconnect_test_pending':True}
        a.state_output.write_text(json.dumps(state,indent=2))
        print(json.dumps(state,indent=2))
        if not connected:raise RuntimeError('No WSS handshake yet; do not unplug USB or start walking')
    finally:
        adb('shell','rm','-f',remote)

if __name__=='__main__':main()

#!/usr/bin/env python3
"""Collect physical PAL3.0 or explicitly documented cellular-bridge trials.

Uses the verified Android apps and the existing laptop viewer. Never stores account
or pairing credentials in the experiment outputs. Ctrl+C retains the partial run.
"""
import argparse
import csv
import hashlib
import http.client
import io
import json
import os
import re
import signal
import subprocess
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
ADB=ROOT/'.tools/android-sdk/platform-tools/adb'
GLASSES='YM00DEC8P06371'
PHONE='c1a1aa06'
GP='edu.purdue.cs536.glasses.partb'
PP='edu.purdue.cs536.phone.partb'
STOP=False

def now():return datetime.now(ZoneInfo('America/Indianapolis')).isoformat()
def stop(*_):
    global STOP
    STOP=True
signal.signal(signal.SIGINT,stop)
signal.signal(signal.SIGTERM,stop)

def adb(serial,*args,timeout=20):
    return subprocess.check_output([str(ADB),'-s',serial,*args],timeout=timeout)

def api(path,action=None):
    c=http.client.HTTPConnection('127.0.0.1',8000,timeout=5)
    try:
        c.request('POST' if action else 'GET',path,json.dumps(action) if action else None,
                  {'Content-Type':'application/json'})
        r=c.getresponse();body=r.read()
        if r.status!=200:raise RuntimeError('Viewer returned HTTP '+str(r.status))
        return json.loads(body)
    finally:c.close()

def click(serial,package,label):
    for attempt in range(7):
        try:
            adb(serial,'shell','uiautomator','dump','/sdcard/cs536-trial-controls.xml')
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            if attempt==6:raise
            # Device wake/reconnection can leave the vendor launcher foreground.
            # Retry setup only; never reuse stale controls after a failed dump.
            resolved=adb(serial,'shell','cmd','package','resolve-activity','--brief',package).decode().splitlines()
            component=next((s.strip() for s in reversed(resolved) if s.strip().startswith(package+'/')),None)
            if component:adb(serial,'shell','am','start','-n',component)
            continue
        ui=ET.fromstring(adb(serial,'exec-out','cat','/sdcard/cs536-trial-controls.xml'))
        if not any(n.get('package')==package for n in ui.iter('node')):
            if attempt>=2:raise RuntimeError('Expected test app is not foreground: '+package)
            resolved=adb(serial,'shell','cmd','package','resolve-activity','--brief',package).decode().splitlines()
            component=next((s.strip() for s in reversed(resolved) if '/' in s and s.strip().startswith(package+'/')),None)
            if not component:raise RuntimeError('Cannot resolve test activity: '+package)
            adb(serial,'shell','am','start','-n',component)
            continue
        for n in ui.iter('node'):
            if n.get('text')==label:
                if n.get('enabled')!='true':return False
                b=list(map(int,re.findall(r'\d+',n.get('bounds',''))))
                if len(b)==4 and b[2]>b[0] and b[3]>b[1]:
                    adb(serial,'shell','input','tap',str((b[0]+b[2])//2),str((b[1]+b[3])//2))
                    return True
        scroll=[n for n in ui.iter('node') if n.get('scrollable')=='true']
        if not scroll:raise RuntimeError('Cannot find control: '+label)
        x1,y1,x2,y2=map(int,re.findall(r'\d+',scroll[-1].get('bounds')))
        adb(serial,'shell','input','swipe',str((x1+x2)//2),str(y2-(y2-y1)//8),
            str((x1+x2)//2),str(y1+(y2-y1)//8),'300')
    raise RuntimeError('Control not found: '+label)

def diagnostics(serial):
    result={}
    wifi=adb(serial,'shell','dumpsys','wifi').decode(errors='replace')
    line=next((s for s in wifi.splitlines() if s.strip().startswith('mWifiInfo')),'')
    ssid=re.search(r'SSID:\s*([^,]+)',line)
    result['ssid']=ssid.group(1).strip().strip('"') if ssid else None
    for key,pattern in [('rssi_dbm',r'RSSI:\s*(-?\d+)'),('frequency_mhz',r'Frequency:\s*(\d+)'),('link_speed_mbps',r'Link speed:\s*(\d+)')]:
        match=re.search(pattern,line);result[key]=int(match.group(1)) if match else None
    battery=adb(serial,'shell','dumpsys','battery').decode(errors='replace')
    for key,pattern in [('battery_percent',r'(?m)^\s*level:\s*(\d+)'),('temperature_tenths_c',r'(?m)^\s*temperature:\s*(\d+)')]:
        match=re.search(pattern,battery);result[key]=int(match.group(1)) if match else None
    return result

def latest_trace(serial,package,role,dest,source=None):
    base=f'/sdcard/Android/data/{package}/files/traces'
    names=adb(serial,'shell','ls',base).decode().splitlines()
    names=sorted(n.strip() for n in names if n.startswith(role+'-') and n.endswith('.csv'))
    if not names:raise RuntimeError('No '+role+' trace')
    for name in reversed(names):
        data=adb(serial,'exec-out','cat',base+'/'+name)
        if source:
            rows=csv.DictReader(io.StringIO(data.decode()))
            if not any(r.get('source_session')==source for r in rows):continue
        dest.write_bytes(data)
        return name
    raise RuntimeError('No '+role+' trace matches the measured camera session')

def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def code_snapshot():
    paths=[]
    for directory in ['laptop-viewer','glasses-app/src','android-app/src','android-common/src','stream-core/src','tools/java']:
        paths.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and p.suffix in ('.py','.java','.xml','.html'))
    paths.extend([ROOT/'tools/cellular_bridge.py', Path(__file__)])
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}

def snapshot_laptop(csv_path,jsonl_path,source,start,end,dest):
    # Receive clock and trial clock both use this laptop's monotonic clock.
    received={}
    with csv_path.open(newline='') as f,(dest/'laptop.csv').open('w',newline='') as out:
        reader=csv.DictReader(f);writer=csv.DictWriter(out,fieldnames=reader.fieldnames);writer.writeheader()
        for row in reader:
            if row.get('source_session')!=source:continue
            try:timestamp=int(row['local_mono_ns'])
            except (ValueError,TypeError):continue
            if start<=timestamp<=end:
                writer.writerow(row)
                if row['event']=='frame_received':received[int(row['sequence'])]=timestamp
    with jsonl_path.open() as f,(dest/'inference.jsonl').open('w') as out:
        for line in f:
            try:r=json.loads(line)
            except json.JSONDecodeError:continue
            if r.get('source_session')==source and r.get('sequence') in received:
                out.write(line)

def authenticated_status(ip,port,code):
    c=http.client.HTTPConnection(ip,port,timeout=5)
    try:
        c.request('GET','/status',headers={'Authorization':'Bearer '+code})
        r=c.getresponse();body=r.read()
        if r.status!=200:raise RuntimeError('Relay HTTP '+str(r.status))
        return json.loads(body)
    finally:c.close()

def main():
    global GP, PP, GLASSES, PHONE
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--glasses-serial',default=GLASSES)
    p.add_argument('--phone-serial',default=PHONE)
    p.add_argument('--control-transport',choices=['usb','wifi'],default='usb')
    p.add_argument('--trial-kind',choices=['planned-field-batch','pilot'],default='planned-field-batch')
    p.add_argument('--glasses-package',default=GP)
    p.add_argument('--phone-package',default=PP)
    p.add_argument('--glasses-apk',type=Path,default=ROOT/'output/apk/live-test/cs536-glasses-partb-debug.apk')
    p.add_argument('--phone-apk',type=Path,default=ROOT/'output/apk/live-test/cs536-phone-partb-debug.apk')
    p.add_argument('--variant',default='baseline',choices=['baseline','steady-pacing'])
    p.add_argument('--scenario',choices=['stationary','walking'],required=True)
    p.add_argument('--network',choices=['PAL3.0','5G-hotspot-via-cloudflare'],default='PAL3.0')
    p.add_argument('--expected-ssid',default='PAL3.0')
    p.add_argument('--topology-file',type=Path)
    p.add_argument('--bridge-trace',type=Path)
    p.add_argument('--uploader-trace',default='/data/local/tmp/cs536-cellular-uploader.csv')
    p.add_argument('--runs',type=int,default=12)
    p.add_argument('--duration',type=float,default=120)
    p.add_argument('--pairing-file',type=Path,required=True)
    p.add_argument('--viewer-log-dir',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    topology=None
    if args.network!='PAL3.0':
        if not args.topology_file or not args.bridge_trace or args.expected_ssid=='PAL3.0':
            p.error('Cellular runs require topology evidence, bridge trace and hotspot SSID')
        topology=json.loads(args.topology_file.read_text())
        if (not topology.get('cellular_generation_evidence') or topology.get('usb_video_forwarding') is not False
                or topology.get('cloud_proxy_included_in_measurements') is not True):
            p.error('Document cellular evidence and actual proxy/video route')
    GP,PP=args.glasses_package,args.phone_package
    GLASSES,PHONE=args.glasses_serial,args.phone_serial
    if not all(re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_.]+",x) for x in (GP,PP)):p.error("Invalid application ID")
    if args.runs<1 or args.duration<30:p.error('Runs >=1 and duration >=30 seconds required')
    args.output.mkdir(parents=True,exist_ok=False)
    credentials=json.loads(args.pairing_file.read_text())
    csv_path=sorted(args.viewer_log_dir.glob('part-b-stream-*.csv'))[-1]
    jsonl_path=sorted(args.viewer_log_dir.glob('part-b-gaze-*.jsonl'))[-1]
    snapshot=code_snapshot()
    manifest={'created_at':now(),'control_transport':args.control_transport,'trial_kind':args.trial_kind,'variant':args.variant,'scenario':args.scenario,'network':args.network,'operator_confirmed_scenario':True,
              'planned_runs':args.runs,'requested_duration_s':args.duration,'collection_kind':'prospective physical trials',
              'run_reset':'camera and phone relay stopped/restarted for every run; laptop viewer remains warm',
              'independence_limit':'same devices, operator and session; runs are not independent subjects',
              'model':'mtgs-static-vsgaze','settings':{'scene_size':224,'precision':'float32','fps':8,'max_faces':4,'confidence':.6},
              'camera':{'requested_fps':8,'requested_width':640,'requested_height':480,'jpeg_quality':65,'rotation':0},
              'glasses_package':GP,'phone_package':PP,'glasses_serial':GLASSES,'phone_serial':PHONE,
              'code_hash_scope':'Current workspace; APK hashes identify installed builds. Earlier baseline batch retains source hashes for the unchanged .partb APKs.',
              'code_hashes':snapshot,'apk_hashes':{str(path):sha(path) for path in [args.glasses_apk,args.phone_apk]},
              'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'git_worktree_dirty':True,'wire_packet_capture':False,
              'latency_scope':'inference and local receive-to-result timings; no calibrated cross-device one-way/display latency',
              'ground_truth_accuracy_available':False,'stall_definition_s':.5,
              'forwarding':subprocess.check_output([str(ADB),'forward','--list'],text=True).splitlines()}
    if topology:
        manifest['topology']=topology
        manifest['expected_ssid']=args.expected_ssid
    (args.output/'batch.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (args.output/'collector-pid.json').write_text(json.dumps({'pid':os.getpid(),'output':str(args.output),'started_at':now()}))
    completed=[]
    print(args.network+' batch prepared: '+str(args.output),flush=True)
    try:
        for index in range(1,args.runs+1):
            if STOP:break
            folder=args.output/f'run-{index:03d}';folder.mkdir()
            run={'run_id':folder.name,'variant':args.variant,'scenario':args.scenario,'network':args.network,'started_at':now(),'status':'setting_up'}
            (folder/'manifest.json').write_text(json.dumps(run,indent=2)+'\n')
            gl,ph=diagnostics(GLASSES),diagnostics(PHONE)
            run['device_start']={'glasses':gl,'phone':ph}
            if gl['ssid']!=args.expected_ssid or ph['ssid']!=args.expected_ssid:
                raise RuntimeError('Both devices must remain on '+args.expected_ssid)
            if topology:
                route=subprocess.check_output(['route','-n','get','default'],text=True)
                if 'gateway: 10.186.' not in route:
                    raise RuntimeError('Laptop campus route changed; verify cellular topology before continuing')
                run['laptop_default_route']=route
                run['phone_routes']=adb(PHONE,'shell','ip','route','show','table','all').decode()
                run['topology']=topology
            api('/ai/control',{'action':'pause'})
            click(PHONE,PP,'Stop');click(GLASSES,GP,'Stop')
            previous=api('/status')['source_session']
            setup=time.monotonic()
            click(GLASSES,GP,'Start camera stream');click(PHONE,PP,'Connect and relay')
            deadline=time.monotonic()+45
            while time.monotonic()<deadline and not STOP:
                status=api('/status')
                if status['state']=='streaming' and status['source_session']!=previous and status['sequence']>=3:break
                time.sleep(.2)
            else:raise RuntimeError('Fresh source session did not reach laptop')
            source=status['source_session'];run.update(source_session=source,automation_startup_s=time.monotonic()-setup)
            api('/ai/control',{'action':'settings','fps':8,'max_faces':4,'confidence':.6,'scene_size':224})
            api('/ai/control',{'action':'start'})
            started=time.monotonic();start_ns=time.monotonic_ns()
            run.update(status='measuring',measurement_start_mono_ns=start_ns)
            (folder/'manifest.json').write_text(json.dumps(run,indent=2)+'\n')
            print(f'RUN {index}/{args.runs} STARTED: {args.scenario}, {args.duration:g}s, fresh camera session',flush=True)
            probe_at=0.;last_report=-1
            with (folder/'samples.jsonl').open('w') as log,(folder/'rtt.jsonl').open('w') as probes:
                while not STOP and time.monotonic()-started<args.duration:
                    elapsed=time.monotonic()-started
                    sample={'elapsed_s':elapsed,'local_mono_ns':time.monotonic_ns()}
                    try:
                        sample['stream']=api('/status');sample['ai']=api('/ai')
                        if sample['stream']['source_session']!=source:sample['protocol_deviation']='camera session changed during run'
                    except Exception as exc:sample['error']=type(exc).__name__
                    log.write(json.dumps(sample)+'\n');log.flush()
                    if elapsed>=probe_at:
                        try:
                            raw=subprocess.run([str(ADB),'-s',PHONE,'shell','ping','-c','1','-W','1',credentials['glasses_ip']],capture_output=True,text=True,timeout=5)
                            match=re.search(r'time[=<]([\d.]+)\s*ms',raw.stdout)
                            probe={'elapsed_s':elapsed,'link':'phone_to_glasses','rtt_ms':float(match.group(1)) if match else None,'exit_code':raw.returncode}
                        except subprocess.TimeoutExpired:
                            probe={'elapsed_s':elapsed,'link':'phone_to_glasses','rtt_ms':None,'exit_code':None,'probe_error':'ADB/ping timeout'}
                        probes.write(json.dumps(probe)+'\n');probes.flush();probe_at+=20
                    marker=int(elapsed//30)
                    if marker!=last_report:
                        last_report=marker;print(f'RUN {index}: {elapsed:.0f}/{args.duration:g}s; stream={sample.get("stream",{}).get("state","unavailable")}',flush=True)
                    time.sleep(min(1,max(0,args.duration-(time.monotonic()-started))))
            end_ns=time.monotonic_ns();duration=(end_ns-start_ns)/1e9
            # Persist the measured boundary before UI controls or USB export can
            # fail. An export-pending run is not counted as complete.
            run.update(measurement_end_mono_ns=end_ns,measured_duration_s=duration,
                       finished_at=now(),status='interrupted' if STOP else 'export_pending')
            (folder/'manifest.json').write_text(json.dumps(run,indent=2)+'\n')
            time.sleep(1.25)  # Drain the local logs' periodic flush, outside the measured window.
            api('/ai/control',{'action':'pause'})
            snapshot_laptop(csv_path,jsonl_path,source,start_ns,end_ns,folder)
            click(PHONE,PP,'Stop');click(GLASSES,GP,'Stop')
            run.update(measurement_end_mono_ns=end_ns,measured_duration_s=duration,finished_at=now(),status='interrupted' if STOP else 'complete')
            run['source_files']={
                'glasses':latest_trace(GLASSES,GP,'glasses',folder/'glasses.csv',source),
                'phone':latest_trace(PHONE,PP,'phone',folder/'phone.csv',source)}
            if args.variant=='steady-pacing':
                with (folder/'glasses.csv').open(newline='') as f:
                    configs=[r['detail'] for r in csv.DictReader(f) if r['event']=='config']
                if not any('pacing=absolute' in r for r in configs):raise RuntimeError('Enhanced run did not enable absolute pacing')
            run['device_end']={'glasses':diagnostics(GLASSES),'phone':diagnostics(PHONE)}
            if topology:
                # Extra hops remain in their own clock domains; preserve session rows.
                uploader=adb(PHONE,'exec-out','cat',args.uploader_trace).decode()
                for name,data in [('phone-uploader.csv',uploader),('bridge.csv',args.bridge_trace.read_text())]:
                    reader=csv.DictReader(io.StringIO(data))
                    with (folder/name).open('w',newline='') as out:
                        writer=csv.DictWriter(out,fieldnames=reader.fieldnames);writer.writeheader()
                        for row in reader:
                            if row.get('source_session')==source:writer.writerow(row)
                run['transport_limits']='Includes hotspot Wi-Fi, iPhone cellular and Cloudflare tunnel; not isolated 5G radio performance. 5G indicator is operator-observed, not modem telemetry.'
            (folder/'manifest.json').write_text(json.dumps(run,indent=2)+'\n')
            completed.append({'run_id':folder.name,'status':run['status'],'duration_s':duration})
            (args.output/'progress.json').write_text(json.dumps({'updated_at':now(),'completed':completed,'planned':args.runs,'stopped':STOP},indent=2)+'\n')
            print(f'RUN {index} SAVED: {duration:.2f}s with three-device traces and inference results',flush=True)
    except Exception as exc:
        (args.output/'collection-error.json').write_text(json.dumps({'at':now(),'error':str(exc),'completed':completed},indent=2)+'\n')
        print('COLLECTION STOPPED: '+str(exc),flush=True)
        raise
    finally:
        try:api('/ai/control',{'action':'pause'})
        except Exception:pass
        (args.output/'collector-pid.json').unlink(missing_ok=True)
        print('COLLECTION FINISHED: '+json.dumps(completed),flush=True)

if __name__=='__main__':main()

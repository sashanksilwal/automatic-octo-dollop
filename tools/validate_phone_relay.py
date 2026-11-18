#!/usr/bin/env python3
"""Live three-device relay check while the physical phone backgrounds and sleeps.

Requires an already streaming glasses -> phone -> laptop viewer. No simulated
source, Wi-Fi changes, pairing credentials or model changes are introduced.
"""
import argparse,json,subprocess,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ADB=ROOT/'.tools/android-sdk/platform-tools/adb'

def api(path,action=None):
    request=urllib.request.Request('http://127.0.0.1:8000'+path,data=json.dumps(action).encode() if action else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=4) as response:return json.load(response)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--phone',default='c1a1aa06');a=p.parse_args()
    before=api('/status')
    if before['state']!='streaming' or before['frame_age_ms']>1000:raise RuntimeError('Fresh live video required before testing')
    api('/ai/control',{'action':'start'});deadline=time.monotonic()+10
    while api('/ai')['processed']<2 and time.monotonic()<deadline:time.sleep(.2)
    a.output.mkdir(parents=True,exist_ok=False);start=time.monotonic_ns();manifest={'status':'measuring','network':'PAL3.0','transport':'glasses Wi-Fi -> phone Wi-Fi relay -> laptop local inference','usb':'Setup, power and phone control only; video uses direct Wi-Fi addresses','source_session':before['source_session'],'start_mono_ns':start,'phases':[],'model_settings':api('/ai')['settings']}
    def save():(a.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    save()
    try:
        with (a.output/'samples.jsonl').open('x') as log:
            for phase,seconds,key in [('foreground',30,None),('home_background',30,'3'),('screen_off',60,'223')]:
                if key:subprocess.run([str(ADB),'-s',a.phone,'shell','input','keyevent',key],check=True)
                began=time.monotonic_ns();first=api('/status');first_ai=api('/ai');record={'phase':phase,'start_mono_ns':began,'requested_duration_s':seconds,'nonstreaming_samples':0,'stale_samples':0,'model_error_samples':0,'session_changes':0};print('LIVE CHECK: '+phase,flush=True)
                while (time.monotonic_ns()-began)/1e9<seconds:
                    item={'phase':phase,'elapsed_s':(time.monotonic_ns()-start)/1e9,'mono_ns':time.monotonic_ns()}
                    try:
                        state=api('/status');ai=api('/ai');item.update(stream=state,ai=ai)
                        record['nonstreaming_samples']+=state['state']!='streaming';record['stale_samples']+=state['frame_age_ms']>2500
                        record['model_error_samples']+=bool(ai.get('error')) or ai['state']!='running'
                        record['session_changes']+=state['source_session']!=manifest['source_session']
                    except Exception as exc:
                        item['error']=type(exc).__name__;record['nonstreaming_samples']+=1
                    log.write(json.dumps(item)+'\n');log.flush();time.sleep(.5)
                ended=time.monotonic_ns();last=api('/status');last_ai=api('/ai');span=(ended-began)/1e9
                record.update(end_mono_ns=ended,measured_s=span,received_frames=last['frames']-first['frames'],inferences=last_ai['processed']-first_ai['processed'],actual_receive_fps=(last['frames']-first['frames'])/span,actual_inference_fps=(last_ai['processed']-first_ai['processed'])/span)
                record['passed']=record['received_frames']>0 and record['inferences']>0 and not any(record[k] for k in ['nonstreaming_samples','stale_samples','model_error_samples','session_changes'])
                manifest['phases'].append(record);save();print(json.dumps(record),flush=True)
        manifest.update(end_mono_ns=time.monotonic_ns(),status='passed' if all(r['passed'] for r in manifest['phases']) else 'failed')
    finally:
        manifest.setdefault('end_mono_ns',time.monotonic_ns());save()
        subprocess.run([str(ADB),'-s',a.phone,'shell','input','keyevent','224'],check=False)
    if manifest['status']!='passed':raise SystemExit('Live stability check failed; retain samples for diagnosis')
    print('LIVE CHECK PASSED',flush=True)
if __name__=='__main__':main()

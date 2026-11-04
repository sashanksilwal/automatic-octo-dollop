#!/usr/bin/env python3
"""One continuous physical walking pilot; never extrapolated into extra trials."""
import argparse,csv,hashlib,importlib.util,json,signal,subprocess,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('collector',ROOT/'Bonus-PartC/collect.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
STOP=False

def stop(*args):
    global STOP
    STOP=True
signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop)

def snapshot(log_dir,start,end,out):
    csv_path=sorted(log_dir.glob('part-b-stream-*.csv'))[-1]
    json_path=sorted(log_dir.glob('part-b-gaze-*.jsonl'))[-1]
    received=set()
    with csv_path.open(newline='') as f,(out/'laptop.csv').open('w',newline='') as dest:
        reader=csv.DictReader(f);writer=csv.DictWriter(dest,fieldnames=reader.fieldnames);writer.writeheader()
        for row in reader:
            try:timestamp=int(row['local_mono_ns'])
            except (ValueError,TypeError):continue
            if start<=timestamp<=end:
                writer.writerow(row)
                if row['event']=='frame_received':received.add((row['source_session'],int(row['sequence'])))
    with json_path.open() as f,(out/'inference.jsonl').open('w') as dest:
        for line in f:
            try:r=json.loads(line)
            except json.JSONDecodeError:continue
            if (r.get('source_session'),r.get('sequence')) in received:dest.write(line)
    return {'laptop':csv_path.name,'inference':json_path.name}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--duration',type=float,default=300)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--pairing-file',type=Path,required=True)
    p.add_argument('--viewer-log-dir',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    cfg=json.loads(a.pairing_file.read_text());phone=cfg['phone_ip']+':5555'
    status=c.api('/status');ai=c.api('/ai')
    if status['state']!='streaming' or ai['state']!='running':raise RuntimeError('Fresh physical video and running inference required')
    start=time.monotonic_ns()
    manifest={'started_at':c.now(),'measurement_start_mono_ns':start,'requested_duration_s':a.duration,
      'status':'measuring','scenario':'walking','network':'PAL3.0','trial_kind':'single continuous walking pilot',
      'operator_confirmed_ready':True,'extrapolated':False,'independent_runs':1,'source_session_at_start':status['source_session'],
      'run_reset':'existing camera/relay session continues; no app restart','inference_settings':ai['settings'],
      'precision':ai.get('precision'),'phone_inference':False,'video_transport':'Wi-Fi through existing phone relay',
      'control_transport':'phone wireless ADB; glasses USB absent during walking',
      'app_reference_batch':'data/raw/part-c/2026-11-04-pal30-stationary-attempt03/batch.json',
      'glasses_trace_status':'pending retrieval after USB reconnection','phone_trace_status':'pending wireless export',
      'ground_truth_accuracy_available':False,'counts_as_ten_runs':False,'full_part_c_validated':False}
    (a.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (a.output/'collector-pid.json').write_text(json.dumps({'pid':__import__('os').getpid()}))
    print(f'WALKING PILOT STARTED: {a.duration:.0f} seconds; one continuous physical run',flush=True)
    probe_at=0;marker=-1
    try:
        with (a.output/'samples.jsonl').open('w') as log,(a.output/'rtt.jsonl').open('w') as probes:
            while not STOP:
                elapsed=(time.monotonic_ns()-start)/1e9
                if elapsed>=a.duration:break
                sample={'elapsed_s':elapsed,'local_mono_ns':time.monotonic_ns()}
                try:sample['stream']=c.api('/status');sample['ai']=c.api('/ai')
                except Exception as e:sample['error']=type(e).__name__
                log.write(json.dumps(sample)+'\n');log.flush()
                if elapsed>=probe_at:
                    try:
                        r=subprocess.run([str(c.ADB),'-s',phone,'shell','ping','-c','1','-W','1',cfg['glasses_ip']],capture_output=True,text=True,timeout=3)
                        match=c.re.search(r'time[=<]([\d.]+)\s*ms',r.stdout)
                        probe={'elapsed_s':elapsed,'link':'phone_to_glasses','rtt_ms':float(match.group(1)) if match else None,'exit_code':r.returncode}
                    except subprocess.TimeoutExpired:probe={'elapsed_s':elapsed,'link':'phone_to_glasses','rtt_ms':None,'probe_error':'ADB/ping timeout'}
                    probes.write(json.dumps(probe)+'\n');probes.flush();probe_at+=20
                if int(elapsed//30)!=marker:
                    marker=int(elapsed//30);print(f'PILOT {elapsed:.0f}/{a.duration:.0f}s; video={sample.get("stream",{}).get("state","unavailable")}',flush=True)
                time.sleep(min(1,max(0,a.duration-(time.monotonic_ns()-start)/1e9)))
        end=time.monotonic_ns();manifest.update(measurement_end_mono_ns=end,measured_duration_s=(end-start)/1e9,
                finished_at=c.now(),status='interrupted' if STOP else 'complete')
        print('WALKING TIMER FINISHED. Saving measured-window traces.',flush=True)
        # Allow already-received work to finish before selecting the input cohort.
        time.sleep(2)
        manifest['source_files']=snapshot(a.viewer_log_dir,start,end,a.output)
        try:
            manifest['source_files']['phone']=c.latest_trace(phone,c.PP,'phone',a.output/'phone.csv')
            manifest['phone_trace_status']='exported via wireless ADB after measurement'
        except Exception as e:manifest['phone_trace_status']='export unavailable: '+type(e).__name__
        for name in ['laptop.csv','inference.jsonl','samples.jsonl','rtt.jsonl','phone.csv']:
            path=a.output/name
            if path.exists():
                with path.open('rb') as f:manifest.setdefault('raw_sha256',{})[name]=hashlib.file_digest(f,'sha256').hexdigest()
    finally:
        (a.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        (a.output/'collector-pid.json').unlink(missing_ok=True)
    print('PILOT SAVED: '+str(a.output),flush=True)

if __name__=='__main__':main()

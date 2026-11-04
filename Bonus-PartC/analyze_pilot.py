#!/usr/bin/env python3
"""Analyze one measured walking pilot without treating segments as independent runs."""
import argparse,csv,importlib.util,json
from pathlib import Path

spec=importlib.util.spec_from_file_location('field_analysis',Path(__file__).with_name('analyze.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
p=argparse.ArgumentParser(description=__doc__);p.add_argument('pilot',type=Path);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();m=json.loads((a.pilot/'manifest.json').read_text())
if m['status']!='complete':raise SystemExit('Pilot is not complete; do not present unfinished data as a five-minute run')
start,end=m['measurement_start_mono_ns'],m['measurement_end_mono_ns'];duration=m['measured_duration_s']
with (a.pilot/'laptop.csv').open(newline='') as log:
 rows=[r for r in csv.DictReader(log) if r['event']=='frame_received']
received={(r['source_session'],int(r['sequence'])):r for r in rows}
inferred={(r['source_session'],r['sequence']):r for r in f.jsonlines(a.pilot/'inference.jsonl') if (r['source_session'],r['sequence']) in received}
heads=[r for r in inferred.values() if r.get('faces')];published=[r for r in inferred.values() if r.get('published')]
stamps=sorted(int(r['local_mono_ns']) for r in received.values());edges=[start]+stamps+[end]
silences=[(b-x)/1e9 for x,b in zip(edges,edges[1:])]
gaps=[(b-x)/1e6 for x,b in zip(stamps,stamps[1:])]
median=f.percentile(gaps,.5)
probes=list(f.jsonlines(a.pilot/'rtt.jsonl'));samples=list(f.jsonlines(a.pilot/'samples.jsonl'))
summary={'trial_kind':'one continuous physical walking pilot','scenario':'walking','network':m['network'],
 'independent_runs':1,'extrapolated':False,'measured_duration_s':duration,'received_frames':len(received),
 'inferred_frames':len(inferred),'published_frames':len(published),'head_containing_inferences':len(heads),
 'actual_receive_fps':len(received)/duration,'actual_inference_fps':len(inferred)/duration,
 'actual_published_fps':len(published)/duration,'received_without_inference':len(received.keys()-inferred.keys()),
 'pipeline_ms':f.distribution(r['pipeline_ms'] for r in inferred.values()),
 'head_pipeline_ms':f.distribution(r['pipeline_ms'] for r in heads),
 'worker_ms':f.distribution(r['worker_ms'] for r in inferred.values()),
 'local_receive_to_result_ms':f.distribution(r['local_receive_to_result_ms'] for r in inferred.values()),
 'pipeline_over_125_ms':sum(r['pipeline_ms']>125 for r in inferred.values()),
 'worker_over_125_ms':sum(r['worker_ms']>125 for r in inferred.values()),
 'payload_mbps':sum(int(r['jpeg_bytes']) for r in received.values())*8/duration/1e6,
 'interarrival_ms':f.distribution(gaps),'max_receive_silence_s':max(silences),
 'receive_silences_over_500_ms':sum(x>.5 for x in silences),
 'receive_silence_excess_s':sum(max(0,x-.5) for x in silences),
 'jitter_abs_deviation_from_median_ms':f.distribution(abs(x-median) for x in gaps),
 'ping_rtt_ms':f.distribution(r.get('rtt_ms') for r in probes),'ping_probes':len(probes),
 'ping_failed_probes':sum(r.get('rtt_ms') is None for r in probes),
 'status_error_samples':sum('error' in r for r in samples),
 'nonstreaming_status_samples':sum(r.get('stream',{}).get('state')!='streaming' for r in samples),
 'source_sessions':sorted(set(r['source_session'] for r in received.values())),
 'phone_trace_status':m['phone_trace_status'],'glasses_trace_status':m['glasses_trace_status'],
 'full_part_c_validated':False,'ground_truth_gaze_accuracy_available':False,
 'limitations':['One five-minute run cannot establish hour-long reliability or replace ten separately collected runs.',
 'Thirty-second plotting windows below are correlated segments of one pilot, not independent trials.',
 'Inference throughput uses the received-frame cohort; final work can finish just after the window.',
 'Local latency excludes glasses capture, phone/network transit and physical browser display.',
 'No ground-truth gaze accuracy is inferred from detected heads or model scores.']}
# Each device keeps its own clock. Source identity joins never subtract clocks.
if (a.pilot/'glasses.csv').exists() and (a.pilot/'phone.csv').exists():
    roles={}
    for role in ['glasses','phone']:
        with (a.pilot/(role+'.csv')).open(newline='') as log:
            roles[role]={(r['source_session'],int(r['sequence'])):r for r in csv.DictReader(log) if r['event']=='frame_received'}
    metadata=['capture_mono_ns','capture_unix_ms','jpeg_bytes','width','height']
    for key,row in received.items():
        for role in roles:
            assert key in roles[role],f'Missing {role} trace record for received frame {key}'
            assert all(row[k]==roles[role][key][k] for k in metadata),f'Relay metadata mismatch: {key}'
    summary['frame_envelope_metadata_verified_across_three_devices']=True
    episodes=[]
    ordered=sorted(received.items(),key=lambda pair:int(pair[1]['local_mono_ns']))
    for (pk,pr),(nk,nr) in zip(ordered,ordered[1:]):
        gap=(int(nr['local_mono_ns'])-int(pr['local_mono_ns']))/1e9
        if gap<=.5:continue
        episode={'laptop_receive_gap_s':gap,'previous_frame':list(pk),'next_frame':list(nk),'start_elapsed_s':(int(pr['local_mono_ns'])-start)/1e9}
        if pk[0]==nk[0]:
            for role,role_rows in roles.items():
                subset=[r for (session,seq),r in role_rows.items() if session==pk[0] and pk[1]<=seq<=nk[1]]
                ts=sorted(int(r['local_mono_ns']) for r in subset)
                episode[role+'_frames_in_same_sequence_interval']=len(subset)
                episode[role+'_max_local_receive_gap_s']=max(((b-x)/1e9 for x,b in zip(ts,ts[1:])),default=None)
            episode['camera_sequence_span_inclusive']=nk[1]-pk[1]+1
        episode['interpretation_limit']='Per-hop gap observations; these do not identify the Wi-Fi or application root cause.'
        episodes.append(episode)
    summary['receive_gap_episodes']=episodes
windows=[]
for i in range(int((duration+29.999)//30)):
 lo=start+i*30_000_000_000;hi=min(end,lo+30_000_000_000);span=(hi-lo)/1e9
 if span<.5:continue
 keys={k for k,r in received.items() if lo<=int(r['local_mono_ns'])<hi}
 windows.append({'start_s':i*30,'duration_s':span,'received_fps':len(keys)/span,'inferred_fps':len(keys&inferred.keys())/span})
summary['correlated_30s_windows']=windows
a.output.mkdir(parents=True,exist_ok=True);(a.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
with (a.output/'windows.csv').open('w',newline='') as log:
 w=csv.DictWriter(log,fieldnames=['start_s','duration_s','received_fps','inferred_fps']);w.writeheader();w.writerows(windows)
print(json.dumps({k:v for k,v in summary.items() if k not in ['correlated_30s_windows','limitations']},indent=2))
try:
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
except ImportError:raise SystemExit('Summary saved. Use the gaze environment to render the plot.')
fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
x=[r['start_s'] for r in windows]
axes[0].plot(x,[r['received_fps'] for r in windows],'o-',label='Received')
axes[0].plot(x,[r['inferred_fps'] for r in windows],'s-',label='Inferred')
axes[0].axhline(8,color='0.4',linestyle='--',label='8 fps target');axes[0].set(xlabel='Window start in this single pilot (s)',ylabel='Actual frames / second',ylim=(0,8.5));axes[0].legend(fontsize=8)
vals=sorted(r['pipeline_ms'] for r in inferred.values())
if vals:axes[1].plot(vals,[(i+1)/len(vals) for i in range(len(vals))])
axes[1].axvline(125,color='0.4',linestyle='--',label='125 ms budget');axes[1].set(xlabel='Detection + gaze + overlay (ms)',ylabel='Empirical fraction of inferences',ylim=(0,1));axes[1].legend(fontsize=8)
for ax in axes:ax.spines[['top','right']].set_visible(False);ax.grid(alpha=.15)
fig.suptitle(f'PAL3.0 walking pilot: one {duration/60:.2f}-minute physical run; no extrapolation')
fig.savefig(a.output/'walking-pilot-performance.png',dpi=180)

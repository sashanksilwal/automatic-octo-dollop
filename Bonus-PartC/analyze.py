#!/usr/bin/env python3
"""Analyze complete physical trials without subtracting unsynchronized device clocks."""
import argparse
import csv
import json
import math
import statistics
from pathlib import Path


def percentile(values, q):
    values=sorted(values)
    if not values:return None
    rank=(len(values)-1)*q;lo=math.floor(rank);hi=math.ceil(rank)
    return values[lo]+(values[hi]-values[lo])*(rank-lo)


def distribution(values):
    values=[float(x) for x in values if x is not None and math.isfinite(float(x))]
    return {'n':len(values),'mean':statistics.mean(values) if values else None,
            'p50':percentile(values,.5),'p95':percentile(values,.95),'max':max(values) if values else None}


def jsonlines(path):
    with path.open() as f:
        for line in f:
            if line.strip():yield json.loads(line)


def frames(path, source, event="frame_received"):
    with path.open(newline='') as f:
        return {int(r['sequence']):r for r in csv.DictReader(f)
                if r['event']==event and r['source_session']==source}


def rate(rows, clock='local_mono_ns'):
    """Same-device first-to-last arrival rate; separate from fixed-window count / duration."""
    stamps=sorted(int(r[clock]) for r in rows.values())
    return (len(stamps)-1)*1e9/(stamps[-1]-stamps[0]) if len(stamps)>1 and stamps[-1]>stamps[0] else None


def analyze_run(folder, stall_s=.5):
    manifest=json.loads((folder/'manifest.json').read_text())
    if manifest.get('status')!='complete':return None
    source=manifest['source_session'];duration=manifest['measured_duration_s']
    laptop=frames(folder/'laptop.csv',source)
    if not laptop:raise ValueError(f'{folder}: complete trial contains no laptop frames')
    lo,hi=min(laptop),max(laptop)
    # Anchor both earlier hops to the same camera sequence interval. These rows
    # have distinct local clocks; they are never subtracted across devices.
    glasses={s:r for s,r in frames(folder/'glasses.csv',source).items() if lo<=s<=hi}
    phone={s:r for s,r in frames(folder/'phone.csv',source).items() if lo<=s<=hi}
    received=set(laptop);generated=set(glasses);relayed=set(phone)
    inferred={r['sequence']:r for r in jsonlines(folder/'inference.jsonl')
              if r.get('source_session')==source and r.get('sequence') in received}
    published={s:r for s,r in inferred.items() if r.get('published')}
    stamps=sorted(int(r['local_mono_ns']) for r in laptop.values())
    gaps=[(b-a)/1e6 for a,b in zip(stamps,stamps[1:])]
    median=percentile(gaps,.5)
    # Include initial/final silence in observed laptop stalls, rather than hiding
    # an outage at a measurement boundary.
    edges=[manifest['measurement_start_mono_ns']]+stamps+[manifest['measurement_end_mono_ns']]
    silence=[(b-a)/1e9 for a,b in zip(edges,edges[1:])]
    samples=list(jsonlines(folder/'samples.jsonl'))
    probes=list(jsonlines(folder/'rtt.jsonl'))
    pipe=[r['pipeline_ms'] for r in inferred.values()]
    head_pipe=[r['pipeline_ms'] for r in inferred.values() if r.get('faces')]
    result={'variant':manifest.get('variant','baseline'),'run_id':folder.name,'network':manifest['network'],'scenario':manifest['scenario'],
        'duration_s':duration,'source_session':source,'status':'complete',
        'laptop_received_frames':len(received),'inferred_frames':len(inferred),'published_frames':len(published),
        'actual_laptop_receive_fps':len(received)/duration,'actual_inference_fps':len(inferred)/duration,
        'actual_published_fps':len(published)/duration,
        'received_without_inference':len(received-set(inferred)),
        'head_containing_inferences':len(head_pipe),
        'pipeline_ms':distribution(pipe),'head_pipeline_ms':distribution(head_pipe),
        'pipeline_over_125_ms':sum(x>125 for x in pipe),
        'pipeline_over_125_fraction':sum(x>125 for x in pipe)/len(pipe) if pipe else None,
        'detection_ms':distribution(r['detection_ms'] for r in inferred.values()),
        'gaze_and_overlay_ms':distribution(r['gaze_and_overlay_ms'] for r in inferred.values()),
        'local_receive_to_result_ms':distribution(r['local_receive_to_result_ms'] for r in inferred.values()),
        'worker_ms':distribution(r['worker_ms'] for r in inferred.values()),
        'worker_over_125_ms':sum(r['worker_ms']>125 for r in inferred.values()),
        'laptop_interarrival_ms':distribution(gaps),
        'laptop_jitter_abs_deviation_from_median_ms':distribution(abs(x-median) for x in gaps),
        'laptop_silence_over_500_ms':sum(x>stall_s for x in silence),
        'laptop_silence_excess_s':sum(max(0,x-stall_s) for x in silence),
        'laptop_max_silence_s':max(silence),
        'phone_to_glasses_ping_rtt_ms':distribution(r['rtt_ms'] for r in probes),
        'ping_probes':len(probes),'ping_failed_probes':sum(r['rtt_ms'] is None for r in probes),
        'status_samples':len(samples),'status_error_samples':sum('error' in s for s in samples),
        'nonstreaming_status_samples':sum(s.get('stream',{}).get('state')!='streaming' for s in samples),
        'protocol_deviation_samples':sum('protocol_deviation' in s for s in samples),
        'source_sequence_interval':[lo,hi],
        'source_generated_in_matched_interval':len(generated),
        'source_capture_fps_matched_interval':rate(glasses,'capture_mono_ns'),
        'phone_receive_fps_matched_interval':rate(phone),
        'source_frames_missing_at_phone_in_matched_interval':len(generated-relayed),
        'phone_frames_missing_at_laptop_in_matched_interval':len(relayed-received),
        'laptop_payload_mbps':sum(int(r['jpeg_bytes']) for r in laptop.values())*8/duration/1e6,
        'phone_payload_mbps_matched_interval':None,
        'device_start':manifest['device_start'],'device_end':manifest['device_end'],
        'limitations':['payload throughput excludes HTTP/TCP/Wi-Fi overhead; not link capacity',
                      'ping is phone-to-glasses RTT, not one-way video latency',
                      'local receive-to-result excludes camera, relay, network and browser display',
                      'received_without_inference includes intentional cadence/buffer drops and window boundaries',
                      'no ground-truth gaze accuracy or independent-subject claim',
                      'inference throughput uses frames received in the window; a result may finish just after its boundary' ]}
    for role,event in [('glasses','frame_sent'),('phone','frame_sent'),('phone','frame_displayed')]:
        subset={seq:r for seq,r in frames(folder/(role+'.csv'),source,event).items() if lo<=seq<=hi}
        key=role+'_'+event
        result[key+'_unique_frames_matched_interval']=len(subset)
        result[key+'_fps_matched_interval']=rate(subset)
        result[key+'_payload_mbps_matched_interval']=None
        if len(subset)>1:
            ts=[int(r['local_mono_ns']) for r in subset.values()];span=(max(ts)-min(ts))/1e9
            result[key+'_payload_mbps_matched_interval']=sum(int(r['jpeg_bytes']) for r in subset.values())*8/span/1e6 if span>0 else None
        if event=='frame_displayed':
            result['phone_local_receive_to_display_callback_ms']=distribution((int(r['local_mono_ns'])-int(phone[seq]['local_mono_ns']))/1e6 for seq,r in subset.items() if seq in phone)
    result['limitations'].append('Phone display timing ends at the logged UI callback, not a calibrated physical screen event.')
    if len(phone)>1:
        times=[int(r['local_mono_ns']) for r in phone.values()]
        result['phone_payload_mbps_matched_interval']=sum(int(r['jpeg_bytes']) for r in phone.values())*8/((max(times)-min(times))/1e9)/1e6
    if manifest.get('topology'):
        uploaded=frames(folder/'phone-uploader.csv',source,'frame_uploaded')
        bridge=frames(folder/'bridge.csv',source)
        result['topology']=manifest['topology']
        result['transport_limits']=manifest.get('transport_limits')
        result['phone_frames_missing_at_bridge_in_matched_interval']=len(relayed-set(bridge))
        result['bridge_frames_missing_at_laptop_in_matched_interval']=len({s for s in bridge if lo<=s<=hi}-received)
        # Each subtraction below stays on one physical device and clock domain.
        result['phone_receive_to_wss_write_return_ms']=distribution(
            (int(r['local_mono_ns'])-int(phone[s]['local_mono_ns']))/1e6
            for s,r in uploaded.items() if s in phone)
        result['laptop_bridge_to_viewer_receive_ms']=distribution(
            (int(r['local_mono_ns'])-int(bridge[s]['local_mono_ns']))/1e6
            for s,r in laptop.items() if s in bridge)
        result['limitations']+=['Cellular condition includes hotspot WLAN, Internet and Cloudflare proxy overhead.',
            '5G indicator was operator-observed; no continuous iPhone modem telemetry.',
            'A WSS write return is not a remote receipt acknowledgment or one-way network latency.']
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('batch',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    batch=json.loads((args.batch/'batch.json').read_text())
    runs=[];excluded=[]
    for folder in sorted(args.batch.glob('run-*')):
        m=json.loads((folder/'manifest.json').read_text())
        if m.get('status')!='complete':
            excluded.append({'run_id':folder.name,'status':m.get('status')});continue
        run=analyze_run(folder,batch.get('stall_definition_s',.5));runs.append(run)
        (args.output/(folder.name+'.json')).write_text(json.dumps(run,indent=2)+'\n')
    fields=['run_id','duration_s','laptop_received_frames','inferred_frames','actual_laptop_receive_fps',
            'actual_inference_fps','actual_published_fps','head_containing_inferences','pipeline_over_125_ms',
            'laptop_payload_mbps','source_capture_fps_matched_interval','laptop_silence_over_500_ms',
            'laptop_max_silence_s','ping_failed_probes','protocol_deviation_samples']
    with (args.output/'runs.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in runs:w.writerow({k:r[k] for k in fields})
    duration=sum(r['duration_s'] for r in runs)
    summary={'variant':batch.get('variant','baseline'),'batch':str(args.batch),'network':batch['network'],'scenario':batch['scenario'],
             'planned_runs':batch['planned_runs'],'complete_runs':len(runs),'excluded_runs':excluded,
             'total_measured_s':duration,'scope':f"{batch['scenario']} {batch['network']} {batch.get('variant','baseline')} batch; partial field evidence",
             'actual_inference_fps_pooled':sum(r['inferred_frames'] for r in runs)/duration if duration else None,
             'actual_receive_fps_pooled':sum(r['laptop_received_frames'] for r in runs)/duration if duration else None,
             'per_run_inference_fps':distribution(r['actual_inference_fps'] for r in runs),
             'per_run_pipeline_p95_ms':distribution(r['pipeline_ms']['p95'] for r in runs),
             'full_part_c_validated':False,'pending':['remaining required scenario/run coverage','more than one hour total across eligible field batches','ground-truth gaze evaluation','cross-device/display latency','in-class demo'],
             'runs':runs}
    if batch.get('topology'):summary['topology']=batch['topology']
    if batch['network']=='PAL3.0':summary['pending'].insert(0,'cellular trials (not represented by this batch)')
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='runs'},indent=2))

if __name__=='__main__':main()

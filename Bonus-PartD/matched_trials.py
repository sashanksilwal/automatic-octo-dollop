#!/usr/bin/env python3
"""Collect prospectively paired baseline/steady-pacing trials after operator readiness."""
import argparse
import json
from pathlib import Path
import random
import shlex
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
ADB=ROOT/'.tools/android-sdk/platform-tools/adb'
GLASSES='YM00DEC8P06371'
PHONE='c1a1aa06'
BASE='edu.purdue.cs536.glasses.partb'
ENHANCED='edu.purdue.cs536.glasses.partd'

def schedule(pairs,seed):
    if pairs<1:raise ValueError('At least one pair required')
    orders=[i%2 for i in range(pairs)];random.Random(seed).shuffle(orders)
    return [{'pair':i+1,'order':['baseline','steady-pacing'] if order==0 else ['steady-pacing','baseline']}
            for i,order in enumerate(orders)]

def run(*args,**kwargs):
    subprocess.run([str(x) for x in args],cwd=ROOT,check=True,**kwargs)

def adb(serial,*args,**kwargs):return run(ADB,'-s',serial,*args,**kwargs)

def setup_variant(variant,credentials):
    pkg=BASE if variant=='baseline' else ENHANCED
    apk=ROOT/('output/apk/live-test/cs536-glasses-partb-debug.apk' if variant=='baseline' else 'output/apk/part-d/cs536-glasses-partd-debug.apk')
    # Only the isolated test packages are stopped or installed.
    for old in [BASE,ENHANCED]:adb(GLASSES,'shell','am','force-stop',old,stdout=subprocess.DEVNULL)
    # Installing the recorded APK ensures its manifest hash identifies the code
    # actually tested, even if a package with this name was already present.
    adb(GLASSES,'install','-r',str(apk))
    adb(GLASSES,'shell','pm','grant',pkg,'android.permission.CAMERA')
    values={'camera':'0','fps':'8','quality':'65','rotation':'0','port':'8080','token':credentials['glasses_code']}
    xml=ET.Element('map')
    for key,value in values.items():ET.SubElement(xml,'string',name=key).text=value
    ET.SubElement(xml,'boolean',name='steadyPacing',value='true' if variant=='steady-pacing' else 'false')
    adb(GLASSES,'shell','run-as',pkg,'mkdir','-p','shared_prefs')
    command='cat > shared_prefs/edu.purdue.cs536.glasses.GlassesActivity.xml'
    adb(GLASSES,'shell','run-as',pkg,'sh','-c',shlex.quote(command),input=ET.tostring(xml))
    adb(GLASSES,'shell','input','keyevent','224')
    adb(GLASSES,'shell','am','start','-n',pkg+'/edu.purdue.cs536.glasses.GlassesActivity',stdout=subprocess.DEVNULL)
    return pkg,apk

def summarize(records):
    metrics=['source_capture_fps_matched_interval','actual_laptop_receive_fps','actual_inference_fps','laptop_payload_mbps']
    pairs=[]
    for pair in sorted({r['pair'] for r in records}):
        by_mode={r['variant']:r['result'] for r in records if r['pair']==pair}
        if set(by_mode)!={'baseline','steady-pacing'}:continue
        b,e=by_mode['baseline'],by_mode['steady-pacing']
        delta={key:e[key]-b[key] for key in metrics}
        delta['local_receive_to_result_p95_ms']=e['local_receive_to_result_ms']['p95']-b['local_receive_to_result_ms']['p95']
        pairs.append({'pair':pair,'baseline':b,'steady_pacing':e,'steady_minus_baseline':delta})
    mean={key:sum(p['steady_minus_baseline'][key] for p in pairs)/len(pairs) for key in pairs[0]['steady_minus_baseline']} if pairs else {}
    return {'complete_pairs':len(pairs),'complete_runs':len(records),'mean_paired_differences':mean,'pairs':pairs,
            'limitations':['Same devices/session and fixed workload, not independent subjects.',
             'Short interleaved trials reduce order imbalance but do not eliminate changing radio or thermal conditions.',
             'Local receive-to-result excludes capture, network and physical display; accuracy is not measured.']}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pairs',type=int,default=4);p.add_argument('--duration',type=float,default=60);p.add_argument('--seed',type=int,default=20261118)
    p.add_argument('--network',choices=['PAL3.0','5G-hotspot-via-cloudflare'],required=True)
    p.add_argument('--expected-ssid',required=True);p.add_argument('--pairing-file',type=Path,required=True)
    p.add_argument('--topology-file',type=Path);p.add_argument('--bridge-trace',type=Path)
    p.add_argument('--uploader-trace',default='/data/local/tmp/cs536-cellular-uploader.csv')
    p.add_argument('--viewer-log-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--results',type=Path,required=True)
    args=p.parse_args()
    if args.pairs<1 or args.duration<30:p.error('Positive pairs and at least 30 seconds per run required')
    if args.network!='PAL3.0' and (not args.topology_file or not args.bridge_trace):p.error('Cellular topology and bridge trace required')
    order=schedule(args.pairs,args.seed)
    args.output.mkdir(parents=True,exist_ok=False);args.results.mkdir(parents=True,exist_ok=False)
    credentials=json.loads(args.pairing_file.read_text())
    plan={'planned_pairs':args.pairs,'planned_runs':2*args.pairs,'duration_s_per_run':args.duration,'seed':args.seed,'order':order,
        'network':args.network,'workload':'Stationary glasses with the same visible person/scene; camera and model settings fixed.',
        'prospective':True,'created_unix_ms':time.time_ns()//1_000_000,'operator_readiness_required':'Run only after operator agrees to the matched stationary comparison.'}
    (args.output/'plan.json').write_text(json.dumps(plan,indent=2))
    records=[]
    for block in order:
        for variant in block['order']:
            name=f'pair-{block["pair"]:03d}-{variant}';raw=args.output/name;derived=args.results/name
            pkg,apk=setup_variant(variant,credentials)
            command=[sys.executable,ROOT/'Bonus-PartC/collect.py','--scenario','stationary','--runs','1','--duration',str(args.duration),
                '--variant',variant,'--glasses-package',pkg,'--glasses-apk',apk,'--network',args.network,'--expected-ssid',args.expected_ssid,
                '--pairing-file',args.pairing_file,'--viewer-log-dir',args.viewer_log_dir,'--output',raw]
            if args.topology_file:command+=['--topology-file',args.topology_file,'--bridge-trace',args.bridge_trace,
                '--uploader-trace',args.uploader_trace]
            run(*command);run(sys.executable,ROOT/'Bonus-PartC/verify.py',raw)
            run(sys.executable,ROOT/'Bonus-PartC/analyze.py',raw,'--output',derived,stdout=subprocess.DEVNULL)
            result=json.loads((derived/'summary.json').read_text())['runs'][0]
            records.append({'pair':block['pair'],'variant':variant,'raw_batch':str(raw),'result':result})
            (args.results/'progress.json').write_text(json.dumps({'records':records,'paired_summary':summarize(records)},indent=2))
    result=summarize(records);result.update(plan=plan,status='complete',raw=str(args.output))
    (args.results/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'complete_pairs':result['complete_pairs'],'complete_runs':result['complete_runs'],'mean_paired_differences':result['mean_paired_differences']},indent=2))

if __name__=='__main__':main()

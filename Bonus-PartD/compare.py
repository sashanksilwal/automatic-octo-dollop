#!/usr/bin/env python3
"""Descriptive comparison of sequential physical capture-pacing trials."""
import argparse,json,statistics
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline',type=Path,required=True)
p.add_argument('--enhanced',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();base=json.loads(a.baseline.read_text());new=json.loads(a.enhanced.read_text())
assert base['complete_runs']>0 and new['complete_runs']>0,'Both conditions need complete physical runs'
batch_b=json.loads((Path(base['batch'])/'batch.json').read_text())
batch_n=json.loads((Path(new['batch'])/'batch.json').read_text())
for key in ['settings','camera','scenario','network','phone_package']:
 assert batch_b[key]==batch_n[key],f'Comparison changed {key}'
assert batch_n['variant']=='steady-pacing','Enhanced traces must declare the tested variant'
def apk_hash(batch,role):
 return next(v for k,v in batch['apk_hashes'].items() if role in Path(k).name)
assert apk_hash(batch_b,'phone')==apk_hash(batch_n,'phone'),'Phone APK changed'
for path,digest in batch_b['code_hashes'].items():
 if path.startswith(('laptop-viewer/','android-app/src/','android-common/src/')):
  assert batch_n['code_hashes'].get(path)==digest,f'Inference or relay code changed: {path}'

def metrics(s):
 r=s['runs'];duration=s['total_measured_s'];n=sum(x['inferred_frames'] for x in r)
 return {'complete_runs':len(r),'measured_s':duration,'inferred_frames':n,
  'mean_source_fps':statistics.mean(x['source_capture_fps_matched_interval'] for x in r),
  'receive_fps':s['actual_receive_fps_pooled'],'inference_fps':s['actual_inference_fps_pooled'],
  'payload_mbps':sum(x['laptop_payload_mbps']*x['duration_s'] for x in r)/duration,
  'pipeline_mean_ms':sum(x['pipeline_ms']['mean']*x['inferred_frames'] for x in r)/n,
  'mean_of_run_pipeline_p95_ms':statistics.mean(x['pipeline_ms']['p95'] for x in r),
  'mean_of_run_receive_to_result_p95_ms':statistics.mean(x['local_receive_to_result_ms']['p95'] for x in r),
  'pipeline_over_125_fraction':sum(x['pipeline_over_125_ms'] for x in r)/n,
  'receive_stalls_per_measured_min':sum(x['laptop_silence_over_500_ms'] for x in r)/(duration/60)}
b,n=metrics(base),metrics(new)
changes={k:{'baseline':b[k],'enhanced':n[k],'absolute_change':n[k]-b[k],
             'relative_change_percent':(n[k]/b[k]-1)*100 if b[k] else None}
         for k in ['mean_source_fps','receive_fps','inference_fps','payload_mbps','pipeline_mean_ms','mean_of_run_pipeline_p95_ms','mean_of_run_receive_to_result_p95_ms','pipeline_over_125_fraction','receive_stalls_per_measured_min']}
out={'baseline':b,'enhanced':n,'changes':changes,'comparison_kind':'sequential preliminary physical evaluation',
     'matching_checks':['camera settings','inference settings','network and scenario','phone APK hash','laptop/phone/shared relay source hashes'],
     'limitations':['Same devices/session; no independent-subject claim.','Stationary camera placement does not control head counts or background activity.','Sequential conditions were not randomized or interleaved.','Run counts and durations may differ; this is a small preliminary field check.','Laptop authoring/build workload varied during baseline; local timing changes are descriptive.','No ground-truth gaze accuracy improvement is claimed.','5G and other scenarios remain pending.'],
     'preliminary_physical_comparison_available':True,'full_project_validated':False}
a.output.mkdir(parents=True,exist_ok=True);(a.output/'comparison.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
try:
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
except ImportError:raise SystemExit('Comparison JSON saved. Use the gaze environment for plotting.')
fig,ax=plt.subplots(figsize=(8,4.8),layout='constrained')
labels=['Glasses capture','Laptop receive','Laptop inference'];keys=['mean_source_fps','receive_fps','inference_fps'];x=range(3)
ax.bar([i-.18 for i in x],[b[k] for k in keys],width=.36,label=f"Baseline: {b['complete_runs']} runs",color='#357ca5')
ax.bar([i+.18 for i in x],[n[k] for k in keys],width=.36,label=f"Steady pacing: {n['complete_runs']} runs",color='#d27b39')
ax.axhline(8,color='0.35',linestyle='--',label='8 fps target');ax.set_xticks(list(x),labels)
ax.set(ylabel='Observed frames per second',ylim=(0,9),title='Stationary PAL3.0: preliminary sequential comparison')
ax.spines[['top','right']].set_visible(False);ax.legend(loc='lower left');ax.grid(axis='y',alpha=.15)
fig.text(.5,-.015,'Same devices and session. Unequal sample sizes. No randomized causal or gaze-accuracy claim.',ha='center',fontsize=9)
fig.savefig(a.output/'capture-pacing-comparison.png',dpi=180,bbox_inches='tight');fig.savefig(a.output/'capture-pacing-comparison.pdf',bbox_inches='tight')

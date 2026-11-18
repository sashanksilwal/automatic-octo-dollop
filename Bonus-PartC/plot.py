#!/usr/bin/env python3
"""Plot run-level observations; no independent-subject or ground-truth accuracy claim."""
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('summary',type=Path);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();data=json.loads(a.summary.read_text());runs=data['runs']
if not runs:raise SystemExit('No complete runs to plot')
a.output.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':180})
x=list(range(1,len(runs)+1))
fig,axes=plt.subplots(2,2,figsize=(8,5.5),layout='constrained')
ax=axes[0,0];ax.plot(x,[r['actual_laptop_receive_fps'] for r in runs],'o-',label='Received')
ax.plot(x,[r['actual_inference_fps'] for r in runs],'s-',label='Inferred')
ax.axhline(8,color='0.4',linestyle='--',label='8 fps target');ax.set(ylabel='Frames/s (actual)',ylim=(0,8.5),title='Delivered and inferred frame rates');ax.legend(fontsize=8)
ax=axes[0,1]
for name,label in [('pipeline_ms','Detection + gaze + overlay'),('local_receive_to_result_ms','Laptop receive to result')]:
 ax.plot(x,[r[name]['p95'] for r in runs],'o-',label=label)
ax.axhline(125,color='0.4',linestyle='--',label='125 ms processing budget');ax.set(ylabel='Per-run p95 (ms)',title='Local timing scopes')
timing_max=max(125,max(r[name]['p95'] for r in runs for name in ['pipeline_ms','local_receive_to_result_ms']))
ax.set_ylim(0,timing_max*1.7);ax.legend(loc='upper right',fontsize=7.5,framealpha=1)
ax=axes[1,0];ax.bar(x,[r['laptop_payload_mbps'] for r in runs],color='#357bad');ax.set(ylabel='JPEG payload (Mbit/s)',title='Laptop application receive throughput')
ax=axes[1,1];ax.bar(x,[r['laptop_max_silence_s'] for r in runs],color='#d48043');ax.axhline(.5,color='0.4',linestyle='--',label='Stall threshold');ax.set(ylabel='Longest receive silence (s)',title='Silence includes trial boundaries');ax.legend(fontsize=8)
for ax in axes.flat:ax.set_xlabel('Run');ax.set_xticks(x);ax.tick_params(axis='x',labelsize=8);ax.grid(axis='y',alpha=.2)
network=data['network']
network_label='5G hotspot + Cloudflare' if network=='5G-hotspot-via-cloudflare' else network
scope='Includes hotspot WLAN and Cloudflare; 5G indicator operator-observed' if data.get('topology') else 'Same devices/session; other networks/scenarios not represented'
fig.suptitle(f"{network_label} {data['scenario']}: {len(runs)} complete runs, {data['total_measured_s']/60:.1f} measured min\n{scope}",fontsize=12)
fig.savefig(a.output/'stationary-performance.png');fig.savefig(a.output/'stationary-performance.pdf');plt.close(fig)
print(a.output/'stationary-performance.png')

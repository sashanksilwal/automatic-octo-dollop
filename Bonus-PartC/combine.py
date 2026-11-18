#!/usr/bin/env python3
"""Combine separately retained batches from the same condition without inventing runs."""
import argparse
import csv
import importlib.util
import json
from pathlib import Path

spec=importlib.util.spec_from_file_location('field_analysis',Path(__file__).with_name('analyze.py'))
analysis=importlib.util.module_from_spec(spec);spec.loader.exec_module(analysis)


def combine(summaries):
    if not summaries:raise ValueError('At least one batch is required')
    batches=[json.loads(Path(s['batch']).joinpath('batch.json').read_text()) for s in summaries]
    for batch in batches[1:]:
        for key in ['network','scenario','variant','model','settings','camera','apk_hashes']:
            if batch.get(key)!=batches[0].get(key):raise ValueError('Batch condition differs: '+key)
    runs=[];seen=set();predictions=[]
    for summary in summaries:
        for run in summary['runs']:
            if run['source_session'] in seen:raise ValueError('Camera session reused across batches')
            seen.add(run['source_session'])
    for i,(summary,batch) in enumerate(zip(summaries,batches),1):
        for original in summary['runs']:
            run=dict(original)
            run.update(run_id=f'batch-{i:02d}-{original["run_id"]}',original_run_id=original['run_id'],batch=summary['batch'])
            runs.append(run)
            path=Path(summary['batch'])/original['run_id']/'inference.jsonl'
            # Keep timing scalars only; do not accumulate all gaze heatmaps in RAM.
            rows={r['sequence']:{'pipeline_ms':r['pipeline_ms'],
                'local_receive_to_result_ms':r['local_receive_to_result_ms'],
                'faces':bool(r.get('faces'))} for r in analysis.jsonlines(path)}
            if len(rows)!=original['inferred_frames']:raise ValueError('Inference cohort mismatch')
            predictions.extend(rows.values())
    duration=sum(r['duration_s'] for r in runs)
    result={'network':summaries[0]['network'],'scenario':summaries[0]['scenario'],
        'variant':summaries[0]['variant'],'complete_runs':len(runs),'total_measured_s':duration,
        'actual_receive_fps_pooled':sum(r['laptop_received_frames'] for r in runs)/duration,
        'actual_inference_fps_pooled':sum(r['inferred_frames'] for r in runs)/duration,
        'pipeline_ms':analysis.distribution(r['pipeline_ms'] for r in predictions),
        'head_pipeline_ms':analysis.distribution(r['pipeline_ms'] for r in predictions if r.get('faces')),
        'pipeline_over_125_ms':sum(r['pipeline_ms']>125 for r in predictions),
        'local_receive_to_result_ms':analysis.distribution(r['local_receive_to_result_ms'] for r in predictions),
        'laptop_silence_over_500_ms':sum(r['laptop_silence_over_500_ms'] for r in runs),
        'laptop_max_silence_s':max(r['laptop_max_silence_s'] for r in runs),
        'per_run_inference_fps':analysis.distribution(r['actual_inference_fps'] for r in runs),
        'per_run_pipeline_p95_ms':analysis.distribution(r['pipeline_ms']['p95'] for r in runs),
        'source_batches':[s['batch'] for s in summaries],
        'topology':batches[0].get('topology'),
        'topologies':[b.get('topology') for b in batches],
        'scope':'Separately retained, same-condition batches. Counts sum actual complete runs; no extrapolation. Same devices and collection session, not independent subjects.',
        'full_part_c_validated':False,'runs':runs}
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('summaries',nargs='+',type=Path)
    p.add_argument('--output',required=True,type=Path)
    args=p.parse_args()
    result=combine([json.loads(path.read_text()) for path in args.summaries])
    result['input_summaries']=[str(path) for path in args.summaries]
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    fields=['run_id','batch','original_run_id','duration_s','laptop_received_frames','inferred_frames',
        'actual_laptop_receive_fps','actual_inference_fps','pipeline_over_125_ms',
        'laptop_silence_over_500_ms','laptop_max_silence_s']
    with (args.output/'runs.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        writer.writerows({k:r[k] for k in fields} for r in result['runs'])
    print(json.dumps({k:v for k,v in result.items() if k not in ('runs','topology')},indent=2))


if __name__=='__main__':main()

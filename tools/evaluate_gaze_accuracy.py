#!/usr/bin/env python3
"""Evaluate the unchanged laptop detector + MTGS pipeline on frozen VAT test frames.

Primary results use detected heads, not ground-truth model inputs. Ground-truth
boxes are used only for one-to-one IoU matching. No thresholds are tuned here.
"""
import argparse, csv, hashlib, json, math, platform, sys, time
from pathlib import Path
import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment
from sklearn.metrics import average_precision_score

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'laptop-viewer'))

def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def iou(a,b):
    inter=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    union=max(0,a[2]-a[0])*max(0,a[3]-a[1])+max(0,b[2]-b[0])*max(0,b[3]-b[1])-inter
    return inter/union if union else 0.

def match_heads(labels,faces,threshold=.5):
    if not labels or not faces:return {}
    overlaps=np.array([[iou(g['head_bbox_pixels'],p['bbox']) for p in faces] for g in labels])
    # Maximize valid match count first, then summed IoU, without reusing a head.
    score=(overlaps>=threshold)*1000+overlaps
    gi,pi=linear_sum_assignment(-score)
    return {int(g):(int(p),float(overlaps[g,p])) for g,p in zip(gi,pi) if overlaps[g,p]>=threshold}

def score_frame(frame,result,width,height,threshold=.8):
    faces=result['faces'];matches=match_heads(frame['labels'],faces);rows=[]
    for i,g in enumerate(frame['labels']):
        inside=g['inside'];row=dict(key=frame['key'],show=frame['key'].split('/')[0],track=g['track'],gt_inside=inside,gt_head_bbox=g['head_bbox_pixels'],gt_gaze_normalized=[min(1,max(0,g['gaze_pixels'][0]/width)),min(1,max(0,g['gaze_pixels'][1]/height))] if inside else None,matched=i in matches)
        if i in matches:
            j,overlap=matches[i];face=faces[j];prob=face['in_frame_probability'];pred=face['heatmap_peak_xy_normalized']
            row.update(prediction_index=j,match_iou=overlap,in_frame_probability=prob,predicted_inside=prob>=threshold,predicted_peak=pred,inout_correct=(prob>=threshold)==inside)
            if inside:
                row['normalized_l2']=math.dist(pred,row['gt_gaze_normalized'])
                for tolerance in [.1,.2]:row[f'joint_success_at_{tolerance}']=prob>=threshold and row['normalized_l2']<=tolerance
        else:
            row['inout_correct']=False
            if inside:
                for tolerance in [.1,.2]:row[f'joint_success_at_{tolerance}']=False
        rows.append(row)
    return rows

def describe(values):
    a=np.asarray(list(values),dtype=float)
    return dict(n=len(a),mean=float(a.mean()),median=float(np.median(a)),p95=float(np.percentile(a,95)),max=float(a.max())) if len(a) else dict(n=0,mean=None,median=None,p95=None,max=None)

def metrics(rows):
    matched=[r for r in rows if r['matched']];inside=[r for r in rows if r['gt_inside']];out=[r for r in rows if not r['gt_inside']]
    def mean(values):
        v=list(values);return sum(v)/len(v) if v else None
    class_recall={str(label):mean(r['inout_correct'] for r in matched if r['gt_inside']==label) for label in [False,True]}
    return dict(person_labels=len(rows),in_frame_labels=len(inside),out_of_frame_labels=len(out),matched_heads=len(matched),head_detection_recall=len(matched)/len(rows) if rows else None,conditional_inout_accuracy=mean(r['inout_correct'] for r in matched),conditional_inout_balanced_accuracy=mean(v for v in class_recall.values() if v is not None),conditional_inout_class_recalls=class_recall,conditional_in_frame_average_precision=float(average_precision_score([r['gt_inside'] for r in matched],[r['in_frame_probability'] for r in matched])) if matched and any(r['gt_inside'] for r in matched) else None,all_label_detection_and_inout_success=mean(r['inout_correct'] for r in rows),conditional_in_frame_normalized_l2=describe(r['normalized_l2'] for r in matched if r['gt_inside']),joint_in_frame_success_at_0_1=mean(r['joint_success_at_0.1'] for r in inside),joint_in_frame_success_at_0_2=mean(r['joint_success_at_0.2'] for r in inside))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,default=Path('data/raw/accuracy/vat-test-2026-11-18'));p.add_argument('--output',required=True,type=Path);p.add_argument('--scene-size',type=int,choices=[224,448],default=224);p.add_argument('--device',choices=['auto','mps','cpu'],default='auto');a=p.parse_args()
    # Refuse overlap with a live measurement, without mutating its controls.
    import urllib.request
    try:
        with urllib.request.urlopen('http://127.0.0.1:8000/ai',timeout=2) as r:status=json.load(r)
    except Exception:status={}
    if status.get('state')=='running':raise RuntimeError('Viewer inference is running. Finish/pause the physical trial before local accuracy inference.')
    selection=json.loads((a.data/'selection.json').read_text());hashes=json.loads((a.data/'download-sha256.json').read_text())
    for path in hashes:
        if sha256(a.data/path)!=hashes[path]:raise ValueError('Input checksum mismatch: '+path)
    a.output.mkdir(parents=True,exist_ok=False);(a.output/'previews').mkdir()
    from mtgs_engine import MTGSEngine,MODEL,HEAD_MODEL
    warm=time.perf_counter();engine=MTGSEngine(a.device,a.scene_size,'float32');engine.warmup(4)
    first=cv2.imread(str(a.data/selection['frames'][0]['image']));engine.process(first,4,.6);warm=time.perf_counter()-warm
    allrows=[];timings=[];started=time.perf_counter()
    with (a.output/'predictions.jsonl').open('x') as log,(a.output/'scored-labels.jsonl').open('x') as scored:
        for i,frame in enumerate(selection['frames']):
            image=cv2.imread(str(a.data/frame['image']))
            if image is None:raise ValueError('Decode failure: '+frame['image'])
            h,w=image.shape[:2];annotated,result=engine.process(image,4,.6)
            rows=score_frame(frame,result,w,h);allrows.extend(rows);timings.append(result['pipeline_ms'])
            log.write(json.dumps(dict(key=frame['key'],width=w,height=h,**result))+'\n');log.flush()
            for row in rows:scored.write(json.dumps(row)+'\n')
            scored.flush()
            # Fixed examples chosen by index, never by prediction quality.
            if i%50==0:
                for row in rows:
                    box=list(map(round,row['gt_head_bbox']));cv2.rectangle(annotated,tuple(box[:2]),tuple(box[2:]),(0,255,0),2)
                    if row['gt_inside']:
                        target=tuple(round(v*s) for v,s in zip(row['gt_gaze_normalized'],[w,h]));cv2.circle(annotated,target,10,(0,255,0),3)
                cv2.imwrite(str(a.output/'previews'/f'{i:04d}.jpg'),annotated)
            if (i+1)%25==0:print(f'{i+1}/{len(selection["frames"])} frames processed',flush=True)
    elapsed=time.perf_counter()-started
    summary=dict(dataset=selection['dataset'],split=selection['split'],frames=len(selection['frames']),shows=len(set(r['show'] for r in allrows)),clips=len(set('/'.join(f['key'].split('/')[:2]) for f in selection['frames'])),selection=selection['selection'],selection_sha256=sha256(a.data/'selection.json'),input_hashes_sha256=sha256(a.data/'download-sha256.json'),settings=dict(scene_size_pixels=a.scene_size,precision='float32',max_heads=4,confidence=.6,inout_threshold=.8,match_iou=.5,ground_truth_boxes_as_model_input=False),device=engine.device,model_sha256=sha256(MODEL),detector_sha256=sha256(HEAD_MODEL),engine_source_sha256=sha256(ROOT/'laptop-viewer/mtgs_engine.py'),evaluator_sha256=sha256(__file__),python=platform.python_version(),warmup_and_loading_s=warm,evaluation_wall_s=elapsed,actual_offline_frames_per_s=len(timings)/elapsed,pipeline_ms=describe(timings),metrics=metrics(allrows),per_show={show:metrics([r for r in allrows if r['show']==show]) for show in sorted(set(r['show'] for r in allrows))},limitations=['Fixed subset, not full official test benchmark.','Third-person TV video differs from glasses footage.','Adjacent frames and tracks may correlate; no independent-subject confidence claim.','Checkpoint was trained on the training portion of VSGaze including VAT; evaluation uses only original official test-show labels.','Conditional accuracy/distance exclude unmatched heads; joint success includes missing heads as failures.','Only annotated people are scored; unannotated detected people cannot be counted as false positives.','No threshold tuning, model updates, or test-driven resolution selection.','Peak L2 is measured for matched ground-truth in-frame cases even if predicted out; joint success also requires predicted in-frame.','Normalized L2 uses x/image-width and y/image-height, not pixels, degrees or fraction of diagonal.','Raw annotation boxes are unsmoothed; matching differs from official ground-truth-box model evaluation.','Frames are sparse accuracy samples, not an 8 fps playback or live throughput trial.'])
    (a.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    with (a.output/'per-show.csv').open('w') as f:
        fields=['show','person_labels','matched_heads','head_detection_recall','conditional_inout_accuracy','joint_in_frame_success_at_0_1'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for show,m in summary['per_show'].items():w.writerow(dict(show=show,**{k:m[k] for k in fields[1:]}))
    print(json.dumps({k:summary[k] for k in ['frames','clips','metrics','pipeline_ms','actual_offline_frames_per_s']},indent=2),flush=True)
if __name__=='__main__':main()

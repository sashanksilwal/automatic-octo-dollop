#!/usr/bin/env python3
"""Compare two runs on identical samples. Agreement is not ground-truth accuracy."""
import argparse
import json
import math
from pathlib import Path

import numpy as np


def iou(a,b):
    area=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    return area/max((a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-area,1e-9)


def compare(reference,candidate):
    summaries=[json.loads((p/'summary.json').read_text()) for p in (reference,candidate)]
    if summaries[0]['input_sha256'] != summaries[1]['input_sha256']:
        raise ValueError('Runs must use the same video')
    rows=[{r['source_frame']:r for r in map(json.loads,(p/'frames.jsonl').read_text().splitlines())} for p in (reference,candidate)]
    if rows[0].keys()!=rows[1].keys():
        raise ValueError('Runs must use identical sampled frames')
    shifts,inside_shifts,probability_changes=[],[],[]
    agreements=unmatched=0
    for frame,a in rows[0].items():
        remaining=rows[1][frame]['faces'].copy()
        for face in a['faces']:
            if not remaining:
                unmatched+=1
                continue
            best=max(range(len(remaining)),key=lambda i:iou(face['bbox'],remaining[i]['bbox']))
            if iou(face['bbox'],remaining[best]['bbox'])<.9:
                unmatched+=1
                continue
            other=remaining.pop(best)
            shift=math.dist(face['heatmap_peak_xy_normalized'],other['heatmap_peak_xy_normalized'])
            shifts.append(shift)
            agreement=face['out_of_frame']==other['out_of_frame']
            agreements+=agreement
            if not face['out_of_frame'] and not other['out_of_frame']:
                inside_shifts.append(shift)
            probability_changes.append(abs(face['in_frame_probability']-other['in_frame_probability']))
        unmatched+=len(remaining)
    return dict(reference=str(reference),candidate=str(candidate),
                interpretation='Prediction agreement only. Neither run is ground truth; no accuracy claim.',
                sampled_frames=len(rows[0]),matched_heads=len(shifts),unmatched_heads=unmatched,
                inout_agreement=agreements/len(shifts) if shifts else None,
                mean_peak_shift_normalized=float(np.mean(shifts)) if shifts else None,
                p95_peak_shift_normalized=float(np.percentile(shifts,95)) if shifts else None,
                mean_peak_shift_both_in_frame=float(np.mean(inside_shifts)) if inside_shifts else None,
                mean_absolute_in_frame_score_change=float(np.mean(probability_changes)) if probability_changes else None)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    result=compare(args.reference,args.candidate)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()

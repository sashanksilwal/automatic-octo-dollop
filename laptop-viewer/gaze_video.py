#!/usr/bin/env python3
"""Sample a downloaded video at 8 fps and save laptop inference evidence."""
import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import cv2
import numpy as np
from gaze import Engine, MODEL


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True, help='New result directory')
    p.add_argument('--fps', type=float, default=8)
    p.add_argument('--max-faces', type=int, default=4)
    p.add_argument('--confidence', type=float, default=.6)
    p.add_argument('--source-url', required=True)
    p.add_argument('--model', choices=['mtgs','mobilegaze'], default='mtgs')
    p.add_argument('--device', choices=['auto','cpu','mps'], default='auto')
    p.add_argument('--scene-size', type=int, choices=[224,448], default=448)
    p.add_argument('--precision', choices=['float32','float16'], default='float32')
    p.add_argument('--warm-all-head-counts', action='store_true', help='Warm all configured head-count shapes before measurement')
    args = p.parse_args()
    if not 0 < args.fps <= 8 or not 1 <= args.max_faces <= 8 or not .5 <= args.confidence <= .99:
        p.error('Use fps >0 and <=8; max-faces 1–8; confidence .5–.99')
    cap = cv2.VideoCapture(str(args.video))
    source_fps = cap.get(cv2.CAP_PROP_FPS)
    if not cap.isOpened() or source_fps < args.fps:
        p.error('Video must open and have at least the requested sample rate')
    args.output.mkdir(parents=True, exist_ok=False)
    if args.model == 'mtgs':
        from mtgs_engine import MTGSEngine, MODEL as model_path, HEAD_MODEL
        engine = MTGSEngine(args.device, args.scene_size, args.precision)
    else:
        model_path = MODEL
        engine = Engine()
    # Warm models once, outside timing; warm-up is explicitly recorded.
    ok, first = cap.read()
    if not ok:
        p.error('Empty input video')
    warm = time.perf_counter()
    if args.warm_all_head_counts and args.model == 'mtgs':
        engine.warmup(args.max_faces)
    engine.process(first, args.max_faces, args.confidence)
    warm = time.perf_counter()-warm
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    w, h = first.shape[1], first.shape[0]
    writer = cv2.VideoWriter(str(args.output/'annotated.mp4'), cv2.VideoWriter_fourcc(*'avc1'), args.fps, (w,h))
    if not writer.isOpened():
        raise RuntimeError('H.264 video encoder unavailable')
    rows, timings, work_times = [], [], []
    detection_times, gaze_times, head_times = [], [], []
    index, sample = 0, 0
    started = time.perf_counter()
    pending_decode_ms = 0.
    try:
        with (args.output/'frames.jsonl').open('x') as log:
            while True:
                read_at = time.perf_counter()
                ok, image = cap.read()
                pending_decode_ms += (time.perf_counter()-read_at)*1000
                if not ok:
                    break
                timestamp = index/source_fps
                index += 1
                if timestamp + 1e-9 < sample/args.fps:
                    continue
                work_at = time.perf_counter()
                image, result = engine.process(image, args.max_faces, args.confidence)
                cv2.putText(image, f'Laptop gaze | {args.fps:g} fps samples | {result["pipeline_ms"]:.1f} ms',
                            (12,28), cv2.FONT_HERSHEY_SIMPLEX, .65, (0,255,255), 2)
                writer.write(image)
                result.update(sample=sample, source_frame=index-1, source_time_s=timestamp,
                              sample_time_s=sample/args.fps, faces_detected=len(result['faces']))
                result['processing_ms'] = pending_decode_ms + (time.perf_counter()-work_at)*1000
                pending_decode_ms = 0.
                log.write(json.dumps(result)+'\n')
                timings.append(result['pipeline_ms'])
                work_times.append(result['processing_ms'])
                detection_times.append(result['detection_ms'])
                gaze_times.append(result['gaze_and_overlay_ms'])
                if result['faces']:
                    head_times.append(result['processing_ms'])
                rows.append(len(result['faces']))
                if sample in (0,40):
                    cv2.imwrite(str(args.output/f'preview-{sample:04d}.jpg'),image)
                sample += 1
    finally:
        cap.release()
        writer.release()
    elapsed = time.perf_counter()-started
    # Verify the produced video decodes completely, independently of writing it.
    output = cv2.VideoCapture(str(args.output/'annotated.mp4'))
    encoded_fps = output.get(cv2.CAP_PROP_FPS)
    decoded = 0
    while output.read()[0]:
        decoded += 1
    output.release()
    if not sample or decoded != sample:
        raise RuntimeError(f'Output verification failed: {decoded}/{sample} frames')
    summary = dict(validation='downloaded video only; no physical streaming validation',
                   input=str(args.video), source_url=args.source_url,
                   input_sha256=hashlib.sha256(args.video.read_bytes()).hexdigest(),
                   model=str(model_path), model_sha256=hashlib.sha256(model_path.read_bytes()).hexdigest(),
                   model_source='https://github.com/idiap/MTGS' if args.model == 'mtgs' else 'https://github.com/yakhyo/gaze-estimation',
                   provider=engine.device if args.model == 'mtgs' else 'CPUExecutionProvider', machine=platform.platform(),
                   sample_fps=args.fps, encoded_fps=encoded_fps, source_fps=source_fps,
                   samples=sample, decoded_output_frames=decoded,
                   faces_total=sum(rows), frames_with_faces=sum(n>0 for n in rows),
                   max_faces=args.max_faces, confidence=args.confidence,
                   warmup_s=warm, wall_s=elapsed, actual_processing_fps=sample/elapsed,
                   warm_all_head_counts=args.warm_all_head_counts,
                   pipeline_mean_ms=float(np.mean(timings)), pipeline_p95_ms=float(np.percentile(timings,95)),
                   pipeline_max_ms=max(timings), pipeline_over_125ms=sum(t>125 for t in timings),
                   processing_mean_ms=float(np.mean(work_times)),
                   processing_p95_ms=float(np.percentile(work_times,95)),
                   processing_over_125ms=sum(t>125 for t in work_times),
                   average_throughput_at_least_8fps=sample/elapsed >= 8,
                   all_frames_within_125ms=all(t<=125 for t in work_times),
                   detection_mean_ms=float(np.mean(detection_times)),
                   gaze_and_overlay_mean_ms=float(np.mean(gaze_times)),
                   processing_with_heads_mean_ms=float(np.mean(head_times)) if head_times else None,
                   processing_with_heads_p95_ms=float(np.percentile(head_times,95)) if head_times else None)
    if args.model == 'mtgs':
        summary.update(head_model=str(HEAD_MODEL),head_model_sha256=hashlib.sha256(HEAD_MODEL.read_bytes()).hexdigest(),
                       model_image_size=args.scene_size,precision=args.precision,in_frame_threshold=.8,
                       heatmap_note='Largest head heatmap rendered; all per-head heatmaps saved in frames.jsonl')
    (args.output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()

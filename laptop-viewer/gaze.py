"""Laptop-only gaze engine shared by file validation and the live viewer.

MobileGaze decoding/preprocessing and projection follow yakhyo/gaze-estimation.
Angles describe a visible person's estimated gaze, not the glasses wearer's gaze.
"""
import json
import math
import os
import threading
import time
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from uniface import RetinaFace
from uniface.constants import RetinaFaceWeights

from streaming import FRESH_SECONDS, Frame

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / '.tools/gaze-models/mobileone_s0_gaze.onnx'


class Engine:
    def __init__(self, model=MODEL):
        os.environ.setdefault('UNIFACE_CACHE_DIR', str(ROOT / '.tools/gaze-models'))
        self.detector = RetinaFace(model_name=RetinaFaceWeights.MNET_025,
                                   input_size=(320, 320), confidence_threshold=.6,
                                   providers=['CPUExecutionProvider'])
        options = ort.SessionOptions()
        options.intra_op_num_threads = 4
        self.session = ort.InferenceSession(str(model), sess_options=options,
                                            providers=['CPUExecutionProvider'])
        self.input = self.session.get_inputs()[0].name
        self.size = tuple(self.session.get_inputs()[0].shape[2:][::-1])

    def process(self, image, max_faces=4, confidence=.6):
        started = time.perf_counter()
        faces = self.detector.detect(image)
        detected = time.perf_counter()
        annotated = image.copy()
        results = []
        # Prefer larger faces; small/distant faces are unreliable for gaze.
        faces = sorted(faces, key=lambda f: (f.bbox[2]-f.bbox[0])*(f.bbox[3]-f.bbox[1]), reverse=True)
        for face in faces:
            if float(face.confidence) < confidence or len(results) >= max_faces:
                continue
            x1, y1, x2, y2 = map(int, face.bbox[:4])
            h, w = image.shape[:2]
            x1, x2 = max(0, x1), min(w, x2)
            y1, y2 = max(0, y1), min(h, y2)
            if min(x2-x1, y2-y1) < 20:
                continue
            crop = cv2.cvtColor(image[y1:y2, x1:x2], cv2.COLOR_BGR2RGB)
            crop = cv2.resize(crop, self.size).astype(np.float32) / 255
            crop = (crop - np.array([.485, .456, .406], np.float32)) / np.array([.229, .224, .225], np.float32)
            tensor = crop.transpose(2, 0, 1)[None].astype(np.float32)
            outputs = self.session.run(['yaw', 'pitch'], {self.input: tensor})
            angles = []
            for logits in outputs:
                probs = np.exp(logits[0] - logits[0].max())
                probs /= probs.sum()
                angles.append(float(np.sum(probs * np.arange(90)) * 4 - 180))
            yaw, pitch = map(math.radians, angles)
            center = ((x1+x2)//2, (y1+y2)//2)
            length = max(60, x2-x1)
            end = (round(center[0]-length*math.sin(yaw)*math.cos(pitch)),
                   round(center[1]-length*math.sin(pitch)))
            cv2.rectangle(annotated, (x1,y1), (x2,y2), (80,230,80), 2)
            cv2.circle(annotated, center, 3, (0,180,255), -1)
            cv2.arrowedLine(annotated, center, end, (0,180,255), 2, cv2.LINE_AA, tipLength=.25)
            results.append(dict(bbox=[x1,y1,x2,y2], face_confidence=float(face.confidence),
                                yaw_deg=angles[0], pitch_deg=angles[1], arrow=[list(center),list(end)]))
        finished = time.perf_counter()
        return annotated, dict(faces=results, detection_ms=(detected-started)*1000,
                              gaze_and_overlay_ms=(finished-detected)*1000,
                              pipeline_ms=(finished-started)*1000)


class Worker:
    """Single consumer of the existing one-frame Hub; no inference queue."""
    def __init__(self, hub, engine, path):
        self.hub, self.engine = hub, engine
        self.lock = threading.RLock()
        self.settings = dict(fps=8., max_faces=4, confidence=.6)
        if hasattr(engine, 'image_size'):
            self.settings['scene_size'] = engine.image_size
        self.state, self.generation = 'stopped', 0
        self.result = None
        self.processed = self.skipped = 0
        self.last_ms = 0.
        self.error = ''
        self.done = threading.Event()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.log = path.open('x')
        self.thread = threading.Thread(target=self.run, daemon=True, name='laptop-gaze')
        self.thread.start()

    def control(self, data):
        action = data.get('action')
        if action not in ('start','resume','pause','stop','settings'):
            raise ValueError('Unknown inference action')
        with self.lock:
            settings = self.settings.copy()
            if action == 'settings':
                settings.update({k: data[k] for k in settings if k in data})
                if (not isinstance(settings['fps'], (float,int)) or not .5 <= settings['fps'] <= 8
                    or type(settings['max_faces']) is not int or not 1 <= settings['max_faces'] <= 8
                    or not isinstance(settings['confidence'], (float,int)) or not .5 <= settings['confidence'] <= .99):
                    raise ValueError('Use fps 0.5–8, max_faces 1–8, confidence 0.5–0.99')
                if 'scene_size' in settings and (type(settings['scene_size']) is not int or settings['scene_size'] not in (224,448)):
                    raise ValueError('Use scene_size 224 or 448')
            self.settings = settings
            self.generation += 1
            self.result = None
            if action != 'settings':
                self.state = {'start':'running','resume':'running','pause':'paused','stop':'stopped'}[action]
            self.error = ''

    def latest(self):
        with self.lock:
            source = self.hub.latest()
            if (self.state == 'running' and source and self.result
                and source.session == self.result[0].session
                and time.monotonic()-self.result[1] <= FRESH_SECONDS):
                return self.result[0]
        return None

    def status(self):
        with self.lock:
            frame = self.latest()
            return dict(state=self.state, settings=self.settings.copy(), processed=self.processed,
                        precision=getattr(self.engine, 'precision', 'float32'),
                        skipped=self.skipped, pipeline_ms=self.last_ms, error=self.error,
                        overlay_frame=f'{frame.session}:{frame.sequence}' if frame else None)

    def run(self):
        version, next_at = -1, 0.
        while not self.done.is_set():
            with self.lock:
                running = self.state == 'running'
                generation, settings = self.generation, self.settings.copy()
            if not running:
                self.done.wait(.05)
                continue
            if self.done.wait(max(0, next_at-time.monotonic())):
                break
            # Capture the frame and its receive time atomically.
            with self.hub.condition:
                sample = self.hub.next(version, timeout=.2)
                arrival = self.hub.arrival
            if sample is None:
                continue
            old, version = version, sample[0]
            frame = sample[1]
            started = time.monotonic()
            # Keep a fixed cadence instead of accumulating scheduler/receive jitter.
            # If inference misses a whole tick, resume from now without catch-up work.
            period = 1/settings['fps']
            next_at = (next_at or started) + period
            if next_at <= started:
                next_at = started + period
            try:
                if 'scene_size' in settings:
                    # Only the inference thread mutates engine configuration.
                    self.engine.image_size = settings['scene_size']
                image = cv2.imdecode(np.frombuffer(frame.jpeg, np.uint8), cv2.IMREAD_COLOR)
                if image is None:
                    raise ValueError('Cannot decode incoming JPEG')
                image, result = self.engine.process(image, settings['max_faces'], settings['confidence'])
                ok, jpeg = cv2.imencode('.jpg', image)
                if not ok:
                    raise ValueError('Cannot encode annotated JPEG')
                annotated = Frame(frame.session, frame.sequence, frame.capture_mono_ns,
                                  frame.capture_unix_ms, image.shape[1], image.shape[0], jpeg.tobytes())
                result.update(source_session=frame.session, sequence=frame.sequence,
                              inference_settings=settings.copy(),precision=getattr(self.engine,'precision','float32'),
                              local_receive_to_result_ms=(time.monotonic()-arrival)*1000,
                              worker_ms=(time.monotonic()-started)*1000)
                with self.lock:
                    current = self.hub.latest()
                    accepted = (generation == self.generation and self.state == 'running' and current
                                and current.session == frame.session and time.monotonic()-arrival <= FRESH_SECONDS)
                    result['published'] = bool(accepted)
                    self.log.write(json.dumps(result)+'\n')
                    self.log.flush()
                    self.processed += 1
                    self.skipped += max(0, version-old-1) if old >= 0 else 0
                    self.last_ms = result['pipeline_ms']
                    if accepted:
                        self.result = annotated, arrival
            except Exception as exc:
                with self.lock:
                    self.error, self.result, self.state = str(exc), None, 'stopped'

    def close(self):
        self.done.set()
        self.thread.join()
        self.log.close()

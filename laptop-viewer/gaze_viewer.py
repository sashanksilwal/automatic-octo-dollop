#!/usr/bin/env python3
"""Part B laptop viewer: --video downloaded.mp4 OR --source http://PHONE:8081."""
import argparse
import getpass
import json
import os
import threading
import time
import uuid
from pathlib import Path

import cv2
from gaze import Engine, Worker, ROOT
from server import Handler, Server
from streaming import Frame, Hub, Receiver, Trace


class InferenceHub(Hub):
    def clear(self, state):
        # Invalidate even if a reconnect reuses the same camera session.
        super().clear(state)
        worker = getattr(self, 'worker', None)
        if worker:
            with worker.lock:
                worker.generation += 1
                worker.result = None


class GazeHandler(Handler):
    def get(self):
        if self.path == '/':
            self.reply(200, 'text/html; charset=utf-8', Path(__file__).with_name('gaze_index.html').read_bytes(),
                       {'Content-Security-Policy': "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'"})
        elif self.path == '/ai':
            self.reply(200, 'application/json', json.dumps(self.server.worker.status()).encode())
        elif self.path == '/frame':
            frame = self.server.worker.latest()
            mode = 'gaze' if frame else 'raw'
            frame = frame or self.server.hub.latest()
            if frame:
                self.reply(200, 'image/jpeg', frame.jpeg,
                           {'X-Frame-Key':f'{mode}:{frame.session}:{frame.sequence}', 'X-Inference':mode})
            else:
                self.reply(204, 'image/jpeg')
        else:
            super().get()

    def do_POST(self):
        # Only same-origin JSON controls, on a loopback-bound server.
        expected = f'http://127.0.0.1:{self.server.server_port}'
        if (self.headers.get('Origin') not in (None, expected)
            or self.headers.get('Sec-Fetch-Site') not in (None, 'same-origin', 'none')
            or self.headers.get('Content-Type') != 'application/json'):
            self.reply(403, 'text/plain', b'Same-origin JSON required')
            return
        if self.path != '/ai/control':
            self.reply(404, 'text/plain', b'Not found')
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 1 <= length <= 2048:
                raise ValueError('Invalid control payload size')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('Expected a JSON object')
            self.server.worker.control(data)
            self.reply(200, 'application/json', json.dumps(self.server.worker.status()).encode())
        except (ValueError, TypeError) as exc:
            self.reply(400, 'application/json', json.dumps({'error':str(exc)}).encode())


class VideoSource:
    """Paced test input publishes into the very same one-frame Hub as Receiver."""
    def __init__(self, path, hub, loop=False):
        self.cap = cv2.VideoCapture(str(path))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        if not self.cap.isOpened() or self.fps < 8:
            raise ValueError('Video must open and contain at least 8 fps')
        self.hub, self.loop = hub, loop
        self.done = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True, name='downloaded-video')

    def start(self):
        self.thread.start()

    def run(self):
        session, sequence, index = uuid.uuid4().hex, 0, 0
        start = time.monotonic()
        try:
            while not self.done.is_set():
                ok, image = self.cap.read()
                if not ok:
                    if not self.loop:
                        break
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    session, sequence, index = uuid.uuid4().hex, 0, 0
                    start = time.monotonic()
                    continue
                timestamp = index/self.fps
                index += 1
                if timestamp + 1e-9 < sequence/8:
                    continue
                if self.done.wait(max(0, start+sequence/8-time.monotonic())):
                    break
                ok, jpeg = cv2.imencode('.jpg', image)
                if not ok:
                    raise ValueError('JPEG encoding failed')
                self.hub.publish(Frame(session,sequence,time.monotonic_ns(),time.time_ns()//1_000_000,
                                       image.shape[1],image.shape[0],jpeg.tobytes()))
                sequence += 1
        finally:
            self.cap.release()
            self.hub.clear('video ended')

    def close(self):
        self.done.set()
        self.thread.join()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    inputs = p.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--video', type=Path)
    inputs.add_argument('--source', help='Phone relay base URL')
    p.add_argument('--loop', action='store_true', help='Repeat downloaded test video')
    p.add_argument('--port', type=int, default=8000)
    p.add_argument('--model', choices=['mtgs','mobilegaze'], default='mtgs')
    p.add_argument('--device', choices=['auto','cpu','mps'], default='auto')
    p.add_argument('--scene-size', type=int, choices=[224,448], default=448)
    p.add_argument('--precision', choices=['float32','float16'], default='float32')
    p.add_argument('--log-dir', type=Path, default=ROOT/'data/raw')
    args = p.parse_args()
    trace = Trace(args.log_dir/f'part-b-stream-{time.time_ns()}.csv')
    hub = InferenceHub(trace)
    worker = source = server = None
    try:
        if args.model == 'mtgs':
            from mtgs_engine import MTGSEngine
            engine = MTGSEngine(args.device, args.scene_size, args.precision)
            print('Warming MTGS head-count shapes before opening viewer...',flush=True)
            engine.warmup(4)
        else:
            engine = Engine()
        worker = Worker(hub, engine, args.log_dir/f'part-b-gaze-{time.time_ns()}.jsonl')
        hub.worker = worker
        if args.video:
            source = VideoSource(args.video,hub,args.loop)
        else:
            token = os.environ.get('CS536_PAIRING_CODE') or getpass.getpass('Phone pairing code: ')
            source = Receiver(args.source,token,hub)
        server = Server(('127.0.0.1',args.port),hub,dashboard=True)
        server.worker = worker
        server.RequestHandlerClass = GazeHandler
        source.start()
        print(f'Part B viewer: http://127.0.0.1:{server.server_port} (inference stopped; click Start)', flush=True)
        print('Input: '+('downloaded video test' if args.video else 'phone relay; hardware validation pending'), flush=True)
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:
        pass
    finally:
        if source and source.thread.is_alive():
            source.close()
        hub.close()
        if worker:
            worker.close()
        if server:
            server.server_close()
        trace.close()


if __name__ == '__main__':
    main()

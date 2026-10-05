#!/usr/bin/env python3
"""Animated test source. Use --upstream to simulate the phone's relay role."""
import argparse
import os
from pathlib import Path
import sys
import threading
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "laptop-viewer"))
from streaming import Frame, Hub, Receiver, Trace
from server import Server


def generate(hub, stop, fps, fixtures=None):
    fixtures = fixtures or Path(__file__).with_name("fixtures")
    frames = [p.read_bytes() for p in sorted(fixtures.glob("*.jpg"))]
    if not frames:
        raise ValueError("Simulator fixtures are missing")
    session = str(uuid.uuid4())
    sequence = 0
    deadline = time.monotonic()
    while not stop.is_set():
        hub.publish(Frame(session, sequence, time.monotonic_ns(), time.time_ns() // 1_000_000,
                          640, 480, frames[sequence % len(frames)]))
        sequence += 1
        deadline += 1/fps
        stop.wait(max(0, deadline-time.monotonic()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--bind", default="127.0.0.1", help="Use 0.0.0.0 only when testing from a physical Android phone")
    parser.add_argument("--fps", type=int, choices=range(1,16), default=8, metavar="1-15")
    parser.add_argument("--upstream", help="Base URL to relay instead of generating test frames")
    args = parser.parse_args()
    token = os.environ.get("CS536_PAIRING_CODE", "demo536")
    upstream_token = os.environ.get("CS536_UPSTREAM_CODE", "demo536")
    trace = Trace()
    hub = Hub(trace)
    stop = threading.Event()
    server = Server((args.bind,args.port), hub, token=token)
    receiver = Receiver(args.upstream,upstream_token,hub) if args.upstream else None
    generator = None
    if receiver:
        receiver.start()
    else:
        generator = threading.Thread(target=generate,args=(hub,stop,args.fps),daemon=True)
        generator.start()
    print(f"SIMULATED {'phone relay' if receiver else 'glasses'}: http://{args.bind}:{server.server_port}",flush=True)
    print("Development pairing code is demo536 unless overridden by CS536_PAIRING_CODE.",flush=True)
    try:
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        if generator:
            generator.join(2)
        if receiver:
            receiver.close()
        hub.close()
        server.server_close()
        trace.close()


if __name__ == "__main__":
    main()

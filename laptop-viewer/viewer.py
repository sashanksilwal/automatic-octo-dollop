#!/usr/bin/env python3
"""Run: python3 laptop-viewer/viewer.py --source http://PHONE:8081"""
import argparse
import getpass
import os
import threading
import time
from pathlib import Path
from server import Server
from streaming import Hub, Receiver, Trace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Phone relay base URL (not the glasses for the Part A demo)")
    parser.add_argument("--port", type=int, default=8000, help="Local dashboard port, default 8000")
    parser.add_argument("--log-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data/raw")
    args = parser.parse_args()
    token = os.environ.get("CS536_PAIRING_CODE") or getpass.getpass("Phone pairing code: ")
    trace = Trace(args.log_dir / f"laptop-{time.time_ns()}.csv")
    hub = Hub(trace)
    receiver = server = None
    try:
        receiver = Receiver(args.source, token, hub)
        # Dashboard is intentionally local. No upstream credentials enter the browser.
        server = Server(("127.0.0.1", args.port), hub, dashboard=True)
        receiver.start()
        print(f"Laptop viewer: http://127.0.0.1:{server.server_port}", flush=True)
        print(f"Trace directory: {args.log_dir.resolve()}", flush=True)
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:
        pass
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Cannot start viewer: {exc}\n")
    finally:
        if receiver and receiver.thread.is_alive():
            receiver.close()
        hub.close()
        if server:
            server.server_close()
        trace.close()


if __name__ == "__main__":
    main()

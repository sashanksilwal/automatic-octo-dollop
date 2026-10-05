"""HTTP endpoints used by the laptop viewer and development simulator."""
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from streaming import CONTENT_TYPE, authenticated, encode_frame


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, hub, token=None, dashboard=False):
        self.hub, self.token, self.dashboard = hub, token, dashboard
        self.slots = threading.BoundedSemaphore(8)
        super().__init__(address, Handler)

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()

    def handle_error(self, request, address):
        self.hub.trace.event("http_error", detail="client disconnected or timed out")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(4)

    def log_message(self, fmt, *args):
        pass  # Do not log URLs or arbitrary request headers.

    def reply(self, status, content_type, body=b"", extra=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        for name, value in (extra or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def do_GET(self):
        try:
            self.get()
        except (OSError, BrokenPipeError):
            self.close_connection = True

    def get(self):
        server = self.server
        if server.token and not authenticated(self.headers, server.token):
            self.reply(401, "text/plain", b"Pairing code required")
            return
        if self.path == "/status":
            self.reply(200, "application/json", json.dumps(server.hub.status()).encode())
        elif self.path == "/frame":
            frame = server.hub.latest()
            if frame:
                self.reply(200, "image/jpeg", frame.jpeg,
                           {"X-Frame-Key": f"{frame.session}:{frame.sequence}"})
            else:
                self.reply(204, "image/jpeg")
        elif self.path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            version = -1
            while not server.hub.closed:
                sample = server.hub.next(version)
                if sample is None:
                    break
                previous, version = version, sample[0]
                frame = sample[1]
                self.wfile.write(encode_frame(frame))
                self.wfile.flush()
                server.hub.trace.event("frame_sent", frame,
                                       f"skipped={max(0, version-previous-1) if previous >= 0 else 0}")
        elif self.path == "/" and server.dashboard:
            self.reply(200, "text/html; charset=utf-8", Path(__file__).with_name("index.html").read_bytes(),
                       {"Content-Security-Policy": "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'"})
        else:
            self.reply(404, "text/plain", b"Not found")

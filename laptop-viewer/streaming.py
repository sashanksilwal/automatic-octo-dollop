"""CS536 MJPEG protocol, receiver and latest-frame store. Standard library only."""
from __future__ import annotations

import csv
import hmac
import http.client
import json
import re
import socket
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

BOUNDARY = b"cs536frame"
CONTENT_TYPE = "multipart/x-mixed-replace; boundary=cs536frame"
MAX_BYTES = 4 * 1024 * 1024
FRESH_SECONDS = 2.5


@dataclass(frozen=True)
class Frame:
    session: str
    sequence: int
    capture_mono_ns: int
    capture_unix_ms: int
    width: int
    height: int
    jpeg: bytes

    def __post_init__(self):
        if (not re.fullmatch(r"[A-Za-z0-9-]{1,64}", self.session)
                or min(self.sequence, self.capture_mono_ns, self.capture_unix_ms) < 0
                or max(self.sequence, self.capture_mono_ns, self.capture_unix_ms) > 2**63 - 1
                or not (1 <= self.width <= 4096 and 1 <= self.height <= 4096)
                or not 4 <= len(self.jpeg) <= MAX_BYTES
                or not self.jpeg.startswith(b"\xff\xd8") or not self.jpeg.endswith(b"\xff\xd9")):
            raise ValueError("Invalid frame metadata or JPEG envelope")


def read_line(stream):
    line = stream.readline(2049)
    if not line:
        raise EOFError("Stream ended")
    if len(line) > 2048 or not line.endswith(b"\r\n"):
        raise ValueError("Malformed or oversized multipart line")
    return line[:-2].decode("ascii")


def read_exact(stream, length):
    result = bytearray()
    while len(result) < length:
        part = stream.read(length - len(result))
        if not part:
            raise EOFError("Truncated frame")
        result.extend(part)
    return bytes(result)


def read_frame(stream):
    if read_line(stream) != "--cs536frame":
        raise ValueError("Unexpected multipart boundary")
    headers = {}
    total = 0
    for _ in range(40):
        line = read_line(stream)
        total += len(line)
        if total > 16384:
            raise ValueError("Headers too large")
        if not line:
            break
        key, sep, value = line.partition(":")
        key = key.strip().lower()
        if not sep or not key or key in headers:
            raise ValueError("Invalid or duplicate header")
        headers[key] = value.strip()
    else:
        raise ValueError("Too many headers")
    if headers.get("content-type") != "image/jpeg" or headers.get("x-protocol-version") != "1":
        raise ValueError("Unsupported frame format")
    length = int(headers["content-length"])
    if not 4 <= length <= MAX_BYTES:
        raise ValueError("Frame length outside limit")
    jpeg = read_exact(stream, length)
    if read_exact(stream, 2) != b"\r\n":
        raise ValueError("Missing frame terminator")
    return Frame(headers["x-source-session"], int(headers["x-frame-id"]),
                 int(headers["x-capture-mono-ns"]), int(headers["x-capture-unix-ms"]),
                 int(headers["x-width"]), int(headers["x-height"]), jpeg)


def encode_frame(frame):
    header = (f"--cs536frame\r\nContent-Type: image/jpeg\r\nContent-Length: {len(frame.jpeg)}\r\n"
              f"X-Protocol-Version: 1\r\nX-Source-Session: {frame.session}\r\nX-Frame-Id: {frame.sequence}\r\n"
              f"X-Capture-Mono-Ns: {frame.capture_mono_ns}\r\nX-Capture-Unix-Ms: {frame.capture_unix_ms}\r\n"
              f"X-Width: {frame.width}\r\nX-Height: {frame.height}\r\n\r\n").encode("ascii")
    return header + frame.jpeg + b"\r\n"


class Trace:
    def __init__(self, path=None):
        self.lock = threading.Lock()
        self.error = ""
        self.file = None
        self.last_flush = 0
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.file = open(path, "x", newline="", encoding="utf-8")
            self.writer = csv.writer(self.file)
            self.writer.writerow(["unix_ms", "local_mono_ns", "event", "source_session", "sequence",
                                  "capture_mono_ns", "capture_unix_ms", "jpeg_bytes", "width", "height", "detail"])
            self.file.flush()

    def event(self, event, frame=None, detail=""):
        with self.lock:
            if not self.file:
                return
            row = [time.time_ns() // 1_000_000, time.monotonic_ns(), event]
            row += ([frame.session, frame.sequence, frame.capture_mono_ns, frame.capture_unix_ms,
                     len(frame.jpeg), frame.width, frame.height] if frame else [""] * 7)
            try:
                self.writer.writerow(row + [detail])
                if time.monotonic() - self.last_flush >= 1:
                    self.file.flush()
                    self.last_flush = time.monotonic()
            except OSError as exc:
                self.error = f"Trace write failed: {type(exc).__name__}"

    def close(self):
        with self.lock:
            if self.file:
                self.file.close()
                self.file = None


class Hub:
    def __init__(self, trace=None):
        self.condition = threading.Condition()
        self.frame = None
        self.frames = self.jpeg_bytes = self.duplicates = 0
        self.last_session, self.last_sequence = "", -1
        self.arrival = None
        self.started = time.monotonic()
        self.state = "idle"
        self.closed = False
        self.trace = trace or Trace()

    def publish(self, frame):
        with self.condition:
            if self.closed:
                return False
            if frame.session == self.last_session and frame.sequence <= self.last_sequence:
                self.duplicates += 1
                return False
            self.frame = frame
            self.last_session, self.last_sequence = frame.session, frame.sequence
            self.frames += 1
            self.jpeg_bytes += len(frame.jpeg)
            self.arrival = time.monotonic()
            self.state = "streaming"
            self.trace.event("frame_received", frame)
            self.condition.notify_all()
            return True

    def clear(self, state):
        with self.condition:
            self.frame, self.state = None, state
            self.trace.event("state", detail=state)
            self.condition.notify_all()

    def latest(self):
        with self.condition:
            if self.frame and time.monotonic() - self.arrival <= FRESH_SECONDS:
                return self.frame
            return None

    def next(self, version, timeout=3):
        deadline = time.monotonic() + timeout
        with self.condition:
            while not self.closed:
                if self.latest() and self.frames != version:
                    return self.frames, self.frame
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self.condition.wait(remaining)
        return None

    def status(self):
        with self.condition:
            age = -1 if self.arrival is None else int((time.monotonic() - self.arrival) * 1000)
            return dict(protocol=1, state="stalled" if self.frame and age > 2500 else self.state,
                        frames=self.frames, jpeg_bytes=self.jpeg_bytes, duplicates=self.duplicates,
                        frame_age_ms=age, uptime_ms=int((time.monotonic() - self.started) * 1000),
                        source_session=self.last_session, sequence=self.last_sequence, log_error=self.trace.error)

    def close(self):
        with self.condition:
            self.closed = True
            self.clear("stopped")


class Receiver:
    def __init__(self, base_url, token, hub):
        self.url = urlsplit(base_url)
        if (self.url.scheme not in ("http", "https") or not self.url.hostname
                or self.url.username or self.url.password or self.url.path not in ("", "/")
                or self.url.query or self.url.fragment):
            raise ValueError("Use a base URL such as http://192.168.1.30:8081")
        if not re.fullmatch(r"[A-Za-z0-9_-]{6,128}", token):
            raise ValueError("Pairing code must be 6-128 letters, numbers, underscores or hyphens")
        self.url.port  # Validate an explicitly supplied port now.
        self.token, self.hub = token, hub
        self.stop_event = threading.Event()
        self.connection = None
        self.thread = threading.Thread(target=self.run, daemon=True, name="mjpeg-receiver")

    def start(self):
        self.thread.start()

    def run(self):
        backoff = .25
        while not self.stop_event.is_set():
            connection = None
            try:
                self.hub.clear("connecting")
                cls = http.client.HTTPSConnection if self.url.scheme == "https" else http.client.HTTPConnection
                connection = cls(self.url.hostname, self.url.port, timeout=4)
                self.connection = connection
                connection.request("GET", "/stream", headers={"Authorization": "Bearer " + self.token})
                response = connection.getresponse()
                if response.status in (401, 403):
                    self.hub.clear("pairing code rejected; restart with the correct code")
                    return
                if response.status != 200 or response.getheader("Content-Type") != CONTENT_TYPE:
                    raise ValueError("Unexpected stream response")
                while not self.stop_event.is_set():
                    frame = read_frame(response)
                    if self.stop_event.is_set():
                        break
                    self.hub.publish(frame)
                    backoff = .25
            except (OSError, EOFError, ValueError, KeyError, http.client.HTTPException) as exc:
                if not self.stop_event.is_set():
                    self.hub.clear(f"reconnecting ({type(exc).__name__})")
            finally:
                if connection:
                    connection.close()
                self.connection = None
            self.stop_event.wait(backoff)
            backoff = min(4, backoff * 2)

    def close(self):
        self.stop_event.set()
        connection = self.connection
        if connection and connection.sock:
            try:
                connection.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self.thread.join(timeout=5)


def authenticated(headers, token):
    return hmac.compare_digest(headers.get("Authorization", "").encode(), ("Bearer " + token).encode())

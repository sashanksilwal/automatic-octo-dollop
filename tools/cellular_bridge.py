#!/usr/bin/env python3
"""Authenticated upload-only WAN endpoint and separate loopback MJPEG source.

Expose ONLY --ingest-port through the HTTPS tunnel. Viewer/inference remain local.
"""
import argparse
import base64
import hashlib
import hmac
import io
from http.server import BaseHTTPRequestHandler
from pathlib import Path
import sys
import threading
import time
import struct

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'laptop-viewer'))
from streaming import CONTENT_TYPE, MAX_BYTES, Hub, Trace, read_frame, read_exact
from server import Server


class ChunkedReader(io.RawIOBase):
    """Bounded HTTP/1.1 chunk decoder; never buffers an entire upload."""
    def __init__(self, stream):
        self.stream, self.remaining, self.done = stream, 0, False

    def readable(self):
        return True

    def readinto(self, dest):
        if self.done:
            return 0
        if not self.remaining:
            line = self.stream.readline(128)
            if not line.endswith(b'\r\n') or len(line) > 127:
                raise ValueError('Invalid chunk header')
            size = line[:-2].split(b';', 1)[0]
            if not size or any(c not in b'0123456789abcdefABCDEF' for c in size):
                raise ValueError('Invalid chunk size')
            self.remaining = int(size, 16)
            if not 0 <= self.remaining <= MAX_BYTES + 32768:
                raise ValueError('Chunk too large')
            if not self.remaining:
                if self.stream.read(2) != b'\r\n':
                    raise ValueError('Trailers unsupported')
                self.done = True
                return 0
        data = self.stream.read(min(len(dest), self.remaining))
        if not data:
            raise EOFError('Truncated upload')
        dest[:len(data)] = data
        self.remaining -= len(data)
        if not self.remaining and self.stream.read(2) != b'\r\n':
            raise ValueError('Invalid chunk terminator')
        return len(data)


class UploadHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *_):
        pass

    def reply(self, status):
        self.send_response(status)
        self.send_header('Content-Length', '0')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True

    def do_GET(self):
        if self.path != '/ingest' or self.headers.get('Upgrade', '').lower() != 'websocket':
            self.reply(404)
            return
        if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + self.server.token):
            self.reply(401)
            return
        key = self.headers.get('Sec-WebSocket-Key', '')
        try:
            if len(base64.b64decode(key, validate=True)) != 16 or self.headers.get('Sec-WebSocket-Version') != '13':
                raise ValueError('Invalid WebSocket handshake')
        except (ValueError, TypeError):
            self.reply(400)
            return
        if not self.server.upload_slot.acquire(blocking=False):
            self.reply(409)
            return
        accept = base64.b64encode(hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
        self.send_response(101)
        self.send_header('Upgrade', 'websocket')
        self.send_header('Connection', 'Upgrade')
        self.send_header('Sec-WebSocket-Accept', accept)
        self.end_headers()
        self.wfile.flush()
        self.close_connection = True
        self.connection.settimeout(10)
        self.server.hub.trace.event('websocket_connected')
        try:
            while True:
                opcode, payload = read_websocket(self.rfile)
                if opcode == 8:
                    break
                if opcode == 9:
                    self.wfile.write(bytes([0x8a, len(payload)]) + payload)
                    self.wfile.flush()
                    continue
                if opcode == 10:
                    continue
                if opcode != 2:
                    raise ValueError('Binary frames required')
                body = io.BytesIO(payload)
                frame = read_frame(body)
                if body.read(1):
                    raise ValueError('One source frame per WebSocket message required')
                self.server.hub.publish(frame)
        except (EOFError, OSError, ValueError, KeyError) as exc:
            self.server.hub.trace.event('websocket_closed', detail=type(exc).__name__)
        finally:
            self.server.upload_slot.release()

    def do_POST(self):
        if self.path != '/ingest':
            self.reply(404)
            return
        if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + self.server.token):
            self.reply(401)
            return
        if (self.headers.get('Content-Type') != CONTENT_TYPE
                or self.headers.get('Transfer-Encoding', '').lower() != 'chunked'
                or self.headers.get('Content-Length') is not None):
            self.server.hub.trace.event('upload_rejected', detail=repr({k:self.headers.get(k) for k in ('Content-Type','Transfer-Encoding','Content-Length')}))
            self.reply(400)
            return
        if not self.server.upload_slot.acquire(blocking=False):
            self.reply(409)
            return
        self.connection.settimeout(10)
        self.server.hub.trace.event('upload_connected')
        code = 200
        try:
            body = io.BufferedReader(ChunkedReader(self.rfile), buffer_size=8192)
            while True:
                if not body.peek(1):
                    break
                self.server.hub.publish(read_frame(body))
        except (EOFError, OSError, ValueError, KeyError) as exc:
            code = 400
            self.server.hub.trace.event('upload_error', detail=type(exc).__name__)
        finally:
            # Completed 30-second uploads need not clear a still-fresh frame.
            # If reception stops, Hub freshness and the existing viewer expire it.
            self.server.hub.trace.event('upload_closed', detail=str(code))
            self.server.upload_slot.release()
        self.reply(code)


def read_websocket(stream):
    first, second = read_exact(stream, 2)
    opcode = first & 15
    if first & 0x70 or not first & 0x80 or not second & 0x80:
        raise ValueError('Unfragmented masked WebSocket message required')
    length = second & 127
    if length == 126:
        length = struct.unpack('!H', read_exact(stream, 2))[0]
    elif length == 127:
        length = struct.unpack('!Q', read_exact(stream, 8))[0]
    if length > MAX_BYTES + 32768 or (opcode >= 8 and length > 125):
        raise ValueError('WebSocket message too large')
    mask = read_exact(stream, 4)
    data = bytearray(read_exact(stream, length))
    for i in range(length):
        data[i] ^= mask[i % 4]
    return opcode, data


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--token-file', type=Path, required=True)
    p.add_argument('--trace', type=Path, required=True)
    p.add_argument('--ingest-port', type=int, default=8790)
    p.add_argument('--source-port', type=int, default=8791)
    args = p.parse_args()
    token = args.token_file.read_text().strip()
    if not 32 <= len(token) <= 128 or not all(c.isalnum() or c in '_-' for c in token):
        raise ValueError('Use a strong URL-safe bridge token')
    trace = Trace(args.trace)
    hub = Hub(trace)
    ingest = Server(('127.0.0.1', args.ingest_port), hub, token)
    ingest.RequestHandlerClass = UploadHandler
    ingest.upload_slot = threading.BoundedSemaphore(1)
    source = Server(('127.0.0.1', args.source_port), hub, token)
    threading.Thread(target=source.serve_forever, daemon=True).start()
    print('Upload-only bridge ready; local MJPEG source ready.', flush=True)
    try:
        ingest.serve_forever()
    finally:
        hub.close()
        source.shutdown()
        trace.close()


if __name__ == '__main__':
    main()

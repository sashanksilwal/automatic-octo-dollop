import http.client
import io
import base64
import socket
import struct
import time
from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from cellular_bridge import ChunkedReader, UploadHandler, Server, Hub, read_frame, read_websocket
from streaming import Frame, encode_frame, CONTENT_TYPE


class BridgeTests(unittest.TestCase):
    def test_websocket_limits(self):
        for payload in (b'\x02\x80', b'\x82\x00', b'\x82\xff'+struct.pack('!Q', 2**32)):
            with self.subTest(payload=payload), self.assertRaises((ValueError, EOFError)):
                read_websocket(io.BytesIO(payload))

    def test_live_websocket_frame_arrives_before_socket_closes(self):
        hub = Hub()
        server = Server(('127.0.0.1', 0), hub, 'a' * 40)
        server.RequestHandlerClass = UploadHandler
        server.upload_slot = threading.BoundedSemaphore(1)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with socket.create_connection(('127.0.0.1',server.server_port), timeout=2) as sock:
                key = base64.b64encode(b'0123456789abcdef').decode()
                request = ('GET /ingest HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: '+key+'\r\nAuthorization: Bearer '+'a'*40+'\r\n\r\n')
                sock.sendall(request.encode())
                response = sock.makefile('rb')
                self.assertIn(b'101', response.readline())
                while response.readline() != b'\r\n': pass
                frame = Frame('session', 8, 10, 20, 640, 480, b'\xff\xd8test\xff\xd9')
                payload = encode_frame(frame)
                mask = b'abcd'
                wire = b'\x82\xfe'+struct.pack('!H',len(payload))+mask+bytes(b^mask[i%4] for i,b in enumerate(payload))
                sock.sendall(wire)
                deadline=time.monotonic()+1
                while hub.latest() is None and time.monotonic()<deadline:time.sleep(.01)
                self.assertEqual(hub.latest(),frame)
                sock.sendall(b'\x88\x80abcd')
                response.close()
        finally:
            server.shutdown();server.server_close()

    def test_frame_spanning_small_chunks(self):
        frame = Frame('session', 4, 10, 20, 640, 480, b'\xff\xd8test\xff\xd9')
        data = encode_frame(frame)
        wire = b''.join(f'{len(data[i:i+7]):x}\r\n'.encode() + data[i:i+7] + b'\r\n'
                        for i in range(0, len(data), 7)) + b'0\r\n\r\n'
        reader = io.BufferedReader(ChunkedReader(io.BytesIO(wire)), buffer_size=16)
        self.assertEqual(read_frame(reader), frame)
        self.assertEqual(reader.read(), b'')

    def test_bad_or_oversized_chunks_rejected(self):
        for wire in (b'-1\r\n', b'fffffff\r\n', b'2\r\nxyXX', b'0\r\nxx'):
            with self.subTest(wire=wire), self.assertRaises((ValueError, EOFError)):
                io.BufferedReader(ChunkedReader(io.BytesIO(wire))).read()

    def test_upload_auth_and_no_public_read_endpoint(self):
        hub = Hub()
        server = Server(('127.0.0.1', 0), hub, 'a' * 40)
        server.RequestHandlerClass = UploadHandler
        server.upload_slot = threading.BoundedSemaphore(1)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        def request(method, path, headers=None, body=None, chunked=False):
            c = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=2)
            try:
                c.request(method, path, body, headers or {}, encode_chunked=chunked)
                response = c.getresponse()
                response.read()
                return response.status
            finally:
                c.close()
        try:
            self.assertEqual(request('GET', '/stream'), 404)
            self.assertEqual(request('POST', '/ingest'), 401)
            frame = Frame('session', 9, 10, 20, 640, 480, b'\xff\xd8test\xff\xd9')
            self.assertEqual(request('POST', '/ingest',
                {'Authorization': 'Bearer ' + 'a' * 40, 'Content-Type': CONTENT_TYPE},
                iter([encode_frame(frame)]), True), 200)
            self.assertEqual(hub.latest(), frame)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    unittest.main()

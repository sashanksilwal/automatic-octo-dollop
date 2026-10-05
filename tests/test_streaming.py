import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "laptop-viewer"), str(ROOT / "tools")]
from streaming import Frame, Hub, Receiver, Trace, encode_frame, read_frame, MAX_BYTES
from server import Server
from simulate import generate

JPEG = (ROOT / "tools/fixtures/frame-00.jpg").read_bytes()


def frame(sequence=0, session="test-source"):
    return Frame(session, sequence, 123, 456, 640, 480, JPEG)


def wait_until(check, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(.02)
    raise AssertionError("Condition did not become true before timeout")


class Fragmented(io.BytesIO):
    def read(self, n=-1):
        return super().read(min(n, 3))


class ProtocolTests(unittest.TestCase):
    def test_short_reads_preserve_frame(self):
        result = read_frame(Fragmented(encode_frame(frame(7))))
        self.assertEqual(result, frame(7))

    def test_truncation_oversize_and_duplicate_headers_fail(self):
        wire = encode_frame(frame())
        for bad in [wire[:-3], wire.replace(f"Content-Length: {len(JPEG)}".encode(),b"Content-Length: 999999999"),
                    wire.replace(b"X-Width: 640", b"X-Width: 640\r\nX-Width: 1"),
                    wire.replace(b"X-Protocol-Version: 1",b"X-Protocol-Version: 2")]:
            with self.assertRaises((EOFError,ValueError)):
                read_frame(io.BytesIO(bad))

    def test_latest_only_and_new_source_session(self):
        hub = Hub()
        for n in range(1000):
            hub.publish(frame(n))
        self.assertEqual(hub.latest().sequence,999)
        self.assertFalse(hub.publish(frame(998)))
        self.assertEqual(hub.frames,1000)
        hub.clear("paused")
        self.assertIsNone(hub.latest())
        self.assertTrue(hub.publish(frame(0,"new-source")))
        hub.close()
        self.assertFalse(hub.publish(frame(1,"new-source")))

    def test_stale_frame_is_not_presented_as_live(self):
        hub = Hub()
        hub.publish(frame())
        hub.arrival -= 3
        self.assertIsNone(hub.latest())
        self.assertEqual(hub.status()["state"],"stalled")

    def test_trace_is_parseable_and_does_not_contain_frame_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"trace.csv"
            trace = Trace(path)
            trace.event("state",detail='quoted, "detail"')
            trace.event("frame_received",frame())
            trace.close()
            with path.open() as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),2)
            self.assertEqual(rows[0]["detail"],'quoted, "detail"')
            self.assertEqual(int(rows[1]["jpeg_bytes"]),len(JPEG))
            self.assertNotIn(None,rows[0])


class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.hub=Hub()
        self.server=Server(("127.0.0.1",0),self.hub,token="source536")
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={"poll_interval":.05},daemon=True)
        self.thread.start()
        self.base=f"http://127.0.0.1:{self.server.server_port}"
        self.receivers=[]

    def tearDown(self):
        for receiver in self.receivers:
            receiver.close()
            self.assertFalse(receiver.thread.is_alive())
        self.hub.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def test_authentication_and_status(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(self.base+"/status",timeout=2)
        self.assertEqual(error.exception.code,401)
        error.exception.close()
        with urlopen(Request(self.base+"/status",headers={"Authorization":"Bearer source536"}),timeout=2) as response:
            self.assertEqual(json.load(response)["frames"],0)

    def test_relay_preserves_metadata_and_recovers_after_idle_disconnect(self):
        destination=Hub()
        receiver=Receiver(self.base,"source536",destination)
        self.receivers.append(receiver)
        receiver.start()
        self.hub.publish(frame(10))
        wait_until(lambda:destination.frames==1)
        self.assertEqual(destination.latest(),frame(10))
        self.hub.clear("paused")
        wait_until(lambda:destination.state.startswith("reconnecting"),timeout=5)
        self.hub.publish(frame(11))
        wait_until(lambda:destination.frames==2)
        self.assertEqual(destination.latest().sequence,11)

    def test_bad_code_is_terminal(self):
        destination=Hub()
        receiver=Receiver(self.base,"wrong536",destination)
        self.receivers.append(receiver)
        receiver.start()
        wait_until(lambda:not receiver.thread.is_alive())
        self.assertIn("pairing code rejected",destination.state)

    def test_dashboard_snapshot_returns_204_when_no_fresh_frame(self):
        request=Request(self.base+"/frame",headers={"Authorization":"Bearer source536"})
        with urlopen(request,timeout=2) as response:
            self.assertEqual(response.status,204)
        self.hub.publish(frame(4))
        with urlopen(request,timeout=2) as response:
            self.assertEqual(response.headers["X-Frame-Key"],"test-source:4")
            self.assertEqual(response.read(),JPEG)


class JavaInteropTests(unittest.TestCase):
    def test_python_source_through_actual_java_relay(self):
        import os
        java = Path(os.environ.get("JAVA_HOME", ROOT/".tools/jdk/Contents/Home"))/"bin/java"
        classes = ROOT/".tools/test-classes"
        core = ROOT/"stream-core/build/classes/java/main"
        if not java.exists() or not (classes/"RelayHarness.class").exists():
            self.skipTest("Run tools/check.sh with a JDK to enable Java/Python integration")
        hub=Hub()
        server=Server(("127.0.0.1",0),hub,token="source536")
        service=threading.Thread(target=server.serve_forever,kwargs={"poll_interval":.05},daemon=True)
        service.start()
        process=subprocess.Popen([str(java),"-cp",str(classes)+os.pathsep+str(core),"RelayHarness",
                                  f"http://127.0.0.1:{server.server_port}"],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        receiver=None
        try:
            import selectors
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout,selectors.EVENT_READ)
                self.assertTrue(selector.select(5),"Java relay did not start")
            port=int(process.stdout.readline().strip())
            destination=Hub()
            receiver=Receiver(f"http://127.0.0.1:{port}","relay536",destination)
            receiver.start()
            hub.publish(frame(40))
            wait_until(lambda:destination.frames==1)
            self.assertEqual(destination.latest(),frame(40))
            hub.clear("paused")
            time.sleep(3.3)
            hub.publish(frame(0,"restarted-source"))
            wait_until(lambda:destination.last_session=="restarted-source",timeout=7)
        finally:
            if receiver:
                receiver.close()
            process.terminate()
            process.communicate(timeout=8)
            hub.close()
            server.shutdown()
            server.server_close()
            service.join(2)


if __name__=="__main__":
    unittest.main()

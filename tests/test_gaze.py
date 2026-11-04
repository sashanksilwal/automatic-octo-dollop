"""Part B controls, bounded work and stale-result regression tests.

Run explicitly in the optional gaze environment; Part A stays stdlib-only.
"""
import http.client
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'laptop-viewer'))

try:
    import cv2
    import numpy as np
    from gaze import Worker
    from gaze_viewer import GazeHandler, InferenceHub
except ImportError:
    cv2 = None
from server import Server
from streaming import Frame


@unittest.skipIf(cv2 is None, 'Optional gaze environment required')
class GazeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.hub = InferenceHub()
        self.entered, self.release = threading.Event(), threading.Event()
        test = self
        class SlowEngine:
            image_size = 448
            def process(self,image,*args):
                test.entered.set()
                test.release.wait(2)
                image[:]=255
                return image,dict(faces=[],pipeline_ms=200)
        self.worker = Worker(self.hub,SlowEngine(),Path(self.temp.name)/'frames.jsonl')
        self.hub.worker = self.worker
        _, jpeg = cv2.imencode('.jpg',np.zeros((32,32,3),np.uint8))
        self.jpeg = jpeg.tobytes()

    def tearDown(self):
        self.release.set()
        self.hub.close()
        self.worker.close()
        self.temp.cleanup()

    def publish(self,n=0,session='test'):
        self.hub.publish(Frame(session,n,0,0,32,32,self.jpeg))

    def wait_for(self,fn):
        deadline=time.monotonic()+3
        while not fn() and time.monotonic()<deadline:
            time.sleep(.01)
        self.assertTrue(fn())

    def test_pause_during_inference_discards_result_and_resume_works(self):
        self.worker.control(dict(action='start'))
        self.publish()
        self.assertTrue(self.entered.wait(2))
        self.worker.control(dict(action='pause'))
        self.release.set()
        self.wait_for(lambda:self.worker.processed==1)
        self.assertIsNone(self.worker.latest())
        self.worker.control(dict(action='resume'))
        self.publish(1)
        self.wait_for(lambda:self.worker.latest() is not None)
        self.worker.control(dict(action='stop'))
        self.assertIsNone(self.worker.latest())

    def test_disconnect_invalidates_inflight_same_session_result(self):
        self.worker.control(dict(action='start'))
        self.publish()
        self.assertTrue(self.entered.wait(2))
        self.hub.clear('disconnected')
        self.publish(1)
        self.worker.control(dict(action='pause'))
        self.release.set()
        self.wait_for(lambda:self.worker.processed==1)
        self.assertIsNone(self.worker.latest())
        rows=[json.loads(line) for line in Path(self.worker.log.name).read_text().splitlines()]
        self.assertFalse(rows[0]['published'])

    def test_overload_keeps_newest_frame_and_counts_skips(self):
        self.worker.control(dict(action='start'))
        self.publish()
        self.assertTrue(self.entered.wait(2))
        for n in range(1,21):
            self.publish(n)
        self.release.set()
        self.wait_for(lambda:self.worker.processed>=2)
        self.assertEqual(self.worker.latest().sequence,20)
        self.assertEqual(self.worker.skipped,19)
        self.assertEqual(self.worker.processed,2)

    def test_overlay_expires_and_new_session_cannot_reuse_it(self):
        self.release.set()
        self.worker.control(dict(action='start'))
        self.publish()
        self.wait_for(lambda:self.worker.latest() is not None)
        with self.worker.lock:
            frame,_=self.worker.result
            self.worker.result=(frame,time.monotonic()-3)
        self.assertIsNone(self.worker.latest())
        self.publish(session='new-session')
        self.assertIsNone(self.worker.latest())

    def test_resolution_change_discards_inflight_result(self):
        self.worker.control(dict(action='start'))
        self.publish()
        self.assertTrue(self.entered.wait(2))
        self.worker.control(dict(action='settings',scene_size=224))
        self.release.set()
        self.wait_for(lambda:self.worker.processed==1)
        self.assertIsNone(self.worker.latest())
        self.publish(1)
        self.wait_for(lambda:self.worker.latest() is not None)
        self.assertEqual(self.worker.engine.image_size,224)
        self.assertEqual(self.worker.latest().sequence,1)

    def test_http_controls_validation_and_raw_fallback(self):
        server=Server(('127.0.0.1',0),self.hub,dashboard=True)
        server.worker=self.worker
        server.RequestHandlerClass=GazeHandler
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            def request(method,path,data=None,origin=None):
                conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
                headers={'Content-Type':'application/json'}
                if origin: headers['Origin']=origin
                conn.request(method,path,json.dumps(data) if data else None,headers)
                response=conn.getresponse()
                result=response.status,response.read(),dict(response.getheaders())
                conn.close()
                return result
            self.assertEqual(request('POST','/ai/control',dict(action='settings',fps=100))[0],400)
            self.assertEqual(request('POST','/ai/control',dict(action='start'),origin='https://example.com')[0],403)
            self.assertEqual(request('POST','/ai/control',dict(action='settings',scene_size=300))[0],400)
            self.assertEqual(self.worker.settings['scene_size'],448)
            self.assertEqual(request('POST','/ai/control',dict(action='settings',fps=4,max_faces=2,confidence=.7,scene_size=224))[0],200)
            self.assertEqual(self.worker.settings['fps'],4)
            self.assertEqual(self.worker.settings['scene_size'],224)
            self.publish()
            code,body,headers=request('GET','/frame')
            self.assertEqual(code,200)
            self.assertEqual(body,self.jpeg)
            self.assertEqual(headers['X-Inference'],'raw')
            self.hub.clear('disconnected')
            self.assertEqual(request('GET','/frame')[0],204)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__=='__main__':
    unittest.main()

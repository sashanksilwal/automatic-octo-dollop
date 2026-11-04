#!/usr/bin/env python3
"""Software-only Part B integration: paced video -> authenticated relay -> Receiver -> MTGS -> HTTP viewer."""
import http.client
import argparse
import json
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'laptop-viewer'))
from gaze import Worker
from gaze_viewer import GazeHandler, InferenceHub, VideoSource
from mtgs_engine import MTGSEngine
from server import Server
from streaming import Hub, Receiver


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene-size',type=int,choices=[224,448],default=448)
    parser.add_argument('--precision',choices=['float32','float16'],default='float32')
    parser.add_argument('--duration',type=float,default=8)
    parser.add_argument('--output',type=Path,default=ROOT/'output/part-b/stream-validation')
    args=parser.parse_args()
    if not 1<=args.duration<=60:
        parser.error('Use a measurement duration from 1 to 60 seconds')
    folder=args.output
    folder.mkdir(parents=True,exist_ok=True)
    upstream=Hub()
    relay=Server(('127.0.0.1',0),upstream,token='test536')
    relay_thread=threading.Thread(target=relay.serve_forever,daemon=True)
    relay_thread.start()
    source=VideoSource(ROOT/'output/part-b/inputs/classroom.mp4',upstream,loop=True)
    downstream=InferenceHub()
    engine=MTGSEngine(image_size=args.scene_size,precision=args.precision)
    engine.warmup(4)
    worker=Worker(downstream,engine,folder/f'frames-{time.time_ns()}.jsonl')
    downstream.worker=worker
    receiver=Receiver(f'http://127.0.0.1:{relay.server_port}','test536',downstream)
    viewer=Server(('127.0.0.1',0),downstream,dashboard=True)
    viewer.worker=worker
    viewer.RequestHandlerClass=GazeHandler
    viewer_thread=threading.Thread(target=viewer.serve_forever,daemon=True)
    viewer_thread.start()

    def request(method,path,data=None):
        conn=http.client.HTTPConnection('127.0.0.1',viewer.server_port,timeout=5)
        conn.request(method,path,json.dumps(data) if data else None,{'Content-Type':'application/json'})
        response=conn.getresponse()
        code,body,headers=response.status,response.read(),dict(response.getheaders())
        conn.close()
        assert code in (200,204),(code,body)
        return body,headers

    def wait_for(fn,timeout=15):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            if fn(): return
            time.sleep(.05)
        raise AssertionError('Timed out waiting for inference state')

    result=dict(validation='software simulation with downloaded video; not physical hardware',model='mtgs-static-vsgaze',device=engine.device,
                scene_size=args.scene_size,precision=args.precision,warm_all_head_counts=True)
    try:
        source.start()
        receiver.start()
        request('POST','/ai/control',dict(action='start'))
        wait_for(lambda:worker.latest() is not None)
        t0,n0,received=time.monotonic(),worker.processed,downstream.frames
        time.sleep(args.duration)
        result.update(measurement_s=time.monotonic()-t0,processed=worker.processed-n0,received=downstream.frames-received)
        result['actual_inference_fps']=result['processed']/result['measurement_s']
        result['status']=worker.status()
        body,headers=request('GET','/frame')
        assert headers['X-Inference']=='gaze'
        (folder/'viewer-frame.jpg').write_bytes(body)
        result['annotated_http_frame']=True
        request('POST','/ai/control',dict(action='pause'))
        assert worker.latest() is None
        assert request('GET','/frame')[1]['X-Inference']=='raw'
        result['pause_raw_fallback']=True
        request('POST','/ai/control',dict(action='settings',fps=8,max_faces=2,confidence=.6))
        request('POST','/ai/control',dict(action='resume'))
        wait_for(lambda:worker.latest() is not None)
        result['resume_and_settings']=True
        other_size=448 if args.scene_size==224 else 224
        request('POST','/ai/control',dict(action='settings',scene_size=other_size))
        assert worker.latest() is None
        wait_for(lambda:worker.latest() is not None)
        assert engine.image_size==other_size
        request('POST','/ai/control',dict(action='settings',scene_size=args.scene_size))
        wait_for(lambda:worker.latest() is not None)
        result['runtime_resolution_switch']=True
        source.close()
        wait_for(lambda:downstream.latest() is None,timeout=8)
        assert worker.latest() is None
        body,_=request('GET','/frame')
        assert body==b''
        result['disconnect_clears_video_and_overlay']=True
        # Fresh camera session, same phone relay and same laptop receiver.
        source=VideoSource(ROOT/'output/part-b/inputs/classroom.mp4',upstream,loop=True)
        source.start()
        wait_for(lambda:worker.latest() is not None)
        result['reconnect_new_session']=True
        request('POST','/ai/control',dict(action='stop'))
        assert worker.latest() is None
        result['stop_clears_overlay']=True
        (folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))
    finally:
        if source.thread.is_alive(): source.close()
        receiver.close()
        downstream.close()
        worker.close()
        for server,thread in [(viewer,viewer_thread),(relay,relay_thread)]:
            server.shutdown()
            server.server_close()
            thread.join()
        upstream.close()


if __name__=='__main__':
    main()

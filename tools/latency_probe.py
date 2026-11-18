#!/usr/bin/env python3
"""Local optical latency target and analysis of an external recording of both panels."""
import argparse
import csv
import json
import math
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import urllib.request
import urllib.error
import cv2
import numpy as np

STEP_MS=20
WRAP_MS=20000
DICTIONARY=cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_1000)

def marker_bits():
    return [(cv2.aruco.generateImageMarker(DICTIONARY,i,6)>127).astype(int).reshape(-1).tolist() for i in range(1000)]

class Target(BaseHTTPRequestHandler):
    def log_message(self,*_):pass
    def do_GET(self):
        headers={}
        if self.path=='/':
            code=200;kind='text/html; charset=utf-8';body=Path(__file__).with_name('latency').joinpath('index.html').read_bytes()
        elif self.path=='/dictionary':code=200;kind='application/json';body=self.server.dictionary
        elif self.path=='/frame':
            try:
                with urllib.request.urlopen('http://127.0.0.1:8000/frame',timeout=3) as response:
                    code=response.status;kind='image/jpeg';body=response.read(4*1024*1024+1)
                    if len(body)>4*1024*1024:raise ValueError('Image too large')
                    if response.headers.get('X-Inference')!='gaze':code=204;body=b''
                    headers['X-Frame-Key']=response.headers.get('X-Frame-Key','')
            except (urllib.error.URLError,TimeoutError,OSError,ValueError):code=204;kind='image/jpeg';body=b''
        else:code=404;kind='text/plain';body=b'Not found'
        self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
        for k,v in headers.items():self.send_header(k,v)
        self.end_headers();self.wfile.write(body)

def roi_arg(value):
    values=tuple(map(int,value.split(',')))
    if len(values)!=4 or min(values)<0 or min(values[2:])<1:raise argparse.ArgumentTypeError('Use x,y,width,height')
    return values

def identify(image,roi,detector):
    x,y,w,h=roi
    if x+w>image.shape[1] or y+h>image.shape[0]:raise ValueError('ROI exceeds recording dimensions')
    corners,ids,_=detector.detectMarkers(image[y:y+h,x:x+w])
    if ids is None or len(ids)!=1:return None
    return int(ids.reshape(-1)[0])

def analyze(args):
    cap=cv2.VideoCapture(str(args.video));fps=cap.get(cv2.CAP_PROP_FPS)
    if not cap.isOpened() or fps<=0:raise ValueError('Recording could not be opened')
    detector=cv2.aruco.ArucoDetector(DICTIONARY,cv2.aruco.DetectorParameters())
    index=0;next_sample=0.;rows=[]
    while True:
        ok,image=cap.read()
        if not ok:break
        t=index/fps;index+=1
        if t+1e-9<next_sample:continue
        next_sample+=1/args.sample_fps
        source=identify(image,args.source_roi,detector);received=identify(image,args.received_roi,detector)
        rows.append({'frame_index':index-1,'recording_s':t,'source_id':source,'received_id':received,
                     'optical_display_age_ms':((source-received)%1000)*STEP_MS if source is not None and received is not None else None})
    cap.release()
    if not rows:raise ValueError('No samples decoded')
    values=[r['optical_display_age_ms'] for r in rows if r['optical_display_age_ms'] is not None]
    def percentile(q):
        if not values:return None
        s=sorted(values);rank=(len(s)-1)*q;lo=int(rank);hi=math.ceil(rank)
        return s[lo]+(s[hi]-s[lo])*(rank-lo)
    args.output.mkdir(parents=True,exist_ok=False)
    with (args.output/'samples.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    result={'video':str(args.video),'recording_fps':fps,'sample_fps':args.sample_fps,'attempted_pairs':len(rows),
        'readable_pairs':len(values),'missing_or_ambiguous_pairs':len(rows)-len(values),
        'optical_display_age_ms':{'mean':sum(values)/len(values) if values else None,'p50':percentile(.5),'p95':percentile(.95),'max':max(values) if values else None},
        'source_roi':args.source_roi,'received_roi':args.received_roi,'marker_step_ms':STEP_MS,'marker_wrap_ms':WRAP_MS,
        'scope':'External simultaneous observation of source display and annotated laptop display; optical frame-age estimate.',
        'limits':['Assumes displayed video is less than 20 seconds old; marker IDs wrap every 20 seconds.',
        '20 ms marker quantization, monitor refresh and external-camera exposure/rolling shutter limit precision; not calibrated hardware capture timestamps.',
        'Unreadable markers remain missing observations, not zero-latency samples.',
        'Video-frame samples are correlated; they are not independent field runs.']}
    (args.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True)
    serve=s.add_parser('serve');serve.add_argument('--port',type=int,default=8800)
    a=s.add_parser('analyze');a.add_argument('--video',type=Path,required=True);a.add_argument('--source-roi',type=roi_arg,required=True);a.add_argument('--received-roi',type=roi_arg,required=True);a.add_argument('--sample-fps',type=float,default=10);a.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.command=='serve':
        server=ThreadingHTTPServer(('127.0.0.1',args.port),Target);server.dictionary=json.dumps(marker_bits()).encode()
        print(f'Optical latency target: http://127.0.0.1:{args.port}',flush=True);server.serve_forever()
    else:
        if not 0<args.sample_fps<=120:p.error('Use 0 < sample fps <= 120')
        analyze(args)

if __name__=='__main__':main()

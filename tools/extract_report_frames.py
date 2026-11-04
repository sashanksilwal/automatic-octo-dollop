#!/usr/bin/env python3
"""Review real recorded frames; never synthesize, redraw or alter predictions."""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image,ImageDraw

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video',type=Path,required=True)
    p.add_argument('--recording-log',type=Path,required=True)
    p.add_argument('--inference-log',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--exclude-context',action='store_true',help='Keep annotated gaze examples only')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    record=[json.loads(s) for s in a.recording_log.read_text().splitlines()]
    keys={(r.get('frame_key') or '').removeprefix('gaze:') for r in record}
    predictions={}
    with a.inference_log.open() as f:
        for line in f:
            try:r=json.loads(line)
            except json.JSONDecodeError:continue
            k=f'{r.get("source_session")}:{r.get("sequence")}'
            if k in keys:
                predictions[k]={k:v for k,v in r.items() if k!='faces'}
                predictions[k]['faces']=[{k:v for k,v in h.items() if k!='heatmap'} for h in r['faces']]
    cap=cv2.VideoCapture(str(a.video));fps=cap.get(cv2.CAP_PROP_FPS)
    candidates=[];seen=set();index=0
    while True:
        ok,image=cap.read()
        if not ok:break
        if index>=len(record):break
        entry=record[index];key=(entry.get('frame_key') or '').removeprefix('gaze:');r=predictions.get(key)
        if key in seen or not r or not r.get('published'):
            index+=1;continue
        seen.add(key);gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
        sharp=float(cv2.Laplacian(gray,cv2.CV_64F).var());h,w=image.shape[:2]
        faces=r['faces'];inside=[f for f in faces if not f['out_of_frame']]
        kind='in-frame' if inside else ('out-of-frame' if faces else 'walking-context')
        score=np.log1p(sharp)
        if faces:
            box=max(faces,key=lambda f:(f['bbox'][2]-f['bbox'][0])*(f['bbox'][3]-f['bbox'][1]))['bbox']
            x1,y1,x2,y2=box;area=(x2-x1)*(y2-y1)/(w*h)
            score+=2*min(area/.15,1)
            if min(x1,y1,w-x2,h-y2)<5:score-=3
            if area>.6:score-=2
        if inside:score+=2*max(f['in_frame_probability'] for f in inside)
        candidates.append({'sample':index,'time_s':index/fps,'kind':kind,'score':float(score),'sharpness':sharp,
                           'frame_key':entry.get('frame_key'),'prediction':r})
        index+=1
    cap.release()
    selected=[]
    for kind in ['in-frame','out-of-frame','walking-context']:
        if a.exclude_context and kind=='walking-context':continue
        group=sorted([r for r in candidates if r['kind']==kind],key=lambda r:r['score'],reverse=True)
        picks=[]
        for r in group:
            if all(abs(r['time_s']-x['time_s'])>=3 for x in picks):picks.append(r)
            if len(picks)==8:break
        selected+=picks
    selected.sort(key=lambda r:(['in-frame','out-of-frame','walking-context'].index(r['kind']),r['time_s']))
    cap=cv2.VideoCapture(str(a.video));tiles=[]
    for n,r in enumerate(selected,1):
        cap.set(cv2.CAP_PROP_POS_FRAMES,r['sample']);ok,image=cap.read()
        if not ok:raise RuntimeError('Cannot extract selected frame')
        filename=f'{n:02d}-{r["kind"]}-{r["sample"]:04d}.png';r['filename']=filename
        cv2.imwrite(str(a.output/filename),image)
        tile=Image.new('RGB',(320,268),'white')
        tile.paste(Image.fromarray(cv2.cvtColor(image,cv2.COLOR_BGR2RGB)).resize((320,240)),(0,0))
        ImageDraw.Draw(tile).text((8,246),f'{n:02d}  {r["time_s"]:.2f}s  {r["kind"]}',fill='black')
        tiles.append(tile)
    cap.release()
    if tiles:
        sheet=Image.new('RGB',(1280,268*((len(tiles)+3)//4)),(220,220,220))
        for n,tile in enumerate(tiles):sheet.paste(tile,((n%4)*320,(n//4)*268))
        sheet.save(a.output/'contact-sheet.jpg',quality=95)
    (a.output/'candidates.json').write_text(json.dumps(selected,indent=2)+'\n')
    print(json.dumps({'review_candidates':len(selected),'counts':{k:sum(r['kind']==k for r in candidates) for k in ['in-frame','out-of-frame','walking-context']},'output':str(a.output)}))

if __name__=='__main__':main()

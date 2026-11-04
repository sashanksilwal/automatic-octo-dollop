#!/usr/bin/env python3
"""Re-extract reviewed screenshots from exact encoded video-frame indices."""
import argparse,hashlib,json
from pathlib import Path
import cv2
from PIL import Image,ImageDraw

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--video',type=Path,required=True)
p.add_argument('--selection',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();rows=json.loads(a.selection.read_text());a.output.mkdir(parents=True,exist_ok=True)
cap=cv2.VideoCapture(str(a.video));fps=cap.get(cv2.CAP_PROP_FPS)
assert fps>0,'Cannot read input video'
sheet=Image.new('RGB',(1280,268*((len(rows)+3)//4)),(220,220,220))
for i,r in enumerate(rows):
 assert Path(r['filename']).name==r['filename'],'Filename must be local to output'
 assert abs(r['sample']/fps-r['time_s'])<.001,'Selection timestamp disagrees with encoded frame index'
 cap.set(cv2.CAP_PROP_POS_FRAMES,r['sample']);ok,frame=cap.read()
 if not ok:raise RuntimeError('Cannot decode selected frame '+str(r['sample']))
 cv2.imwrite(str(a.output/r['filename']),frame)
 tile=Image.new('RGB',(320,268),'white')
 tile.paste(Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)).resize((320,240)),(0,0))
 ImageDraw.Draw(tile).text((8,246),f"{i+1:02d}  {r['time_s']:.2f}s  {r['kind']}",fill='black')
 sheet.paste(tile,((i%4)*320,(i//4)*268))
cap.release();sheet.save(a.output/'contact-sheet.jpg',quality=95)
(a.output/'frames.json').write_text(json.dumps(rows,indent=2)+'\n')
with a.video.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
(a.output/'source.json').write_text(json.dumps({'video':str(a.video.resolve()),'sha256':digest,'encoded_fps':fps,
 'selection':str(a.selection.resolve()),'frames':len(rows),'method':'exact decoded frames; overlays unchanged'},indent=2)+'\n')
print(f'Re-extracted {len(rows)} exact selected video frames')

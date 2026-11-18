#!/usr/bin/env python3
"""Fetch a fixed, show-stratified VAT test subset from the official ZIP using ranges.

No training frames or inference outcomes enter selection. ZIP CRC validates each
member; SHA256 records downloaded labels/images. Raw copyrighted data stays local.
"""
import argparse, collections, concurrent.futures, csv, hashlib, io, json, random
import struct, time, urllib.request, zipfile, zlib, http.cookiejar
from pathlib import Path

SOURCE='https://dl.dropboxusercontent.com/scl/fi/x4uqgkwcfjk16l54hm69f/videoattentiontarget.zip?rlkey=5b626ifn2ppdahekfldlkg7nd&dl=1'
urllib.request.install_opener(urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())))
SHOWS=['CBS_This_Morning','Downton_Abby',"Hell's_Kitchen",'I_Wanna_Marry_Harry',"It's_Always_Sunny_in_Philadelphia",'Jamie_Oliver','MLB_Interview','Survivor','Titanic','West_World']
SHOWS=[show.replace('_',' ') for show in SHOWS]

def get_range(url,start,end):
    for attempt in range(5):
        try:
            req=urllib.request.Request(url,headers={'Range':f'bytes={start}-{end}','Accept-Encoding':'identity'})
            with urllib.request.urlopen(req,timeout=45) as r:
                if r.status!=206:raise ValueError(f'Range request returned {r.status}')
                cr=r.headers.get('Content-Range','')
                if not cr.startswith(f'bytes {start}-'):raise ValueError('Range start mismatch: '+cr)
                data=r.read(end-start+2)
                if len(data)!=end-start+1:raise ValueError('Range length mismatch')
                return data
        except Exception:
            if attempt==4:raise
            time.sleep(2**attempt)

class RangeFile(io.RawIOBase):
    def __init__(self,url,size):self.url,self.size,self.pos=url,size,0
    def seekable(self):return True
    def readable(self):return True
    def seek(self,offset,whence=0):
        self.pos=offset if whence==0 else self.pos+offset if whence==1 else self.size+offset
        return self.pos
    def tell(self):return self.pos
    def read(self,n=-1):
        if n<0:n=self.size-self.pos
        n=min(n,self.size-self.pos)
        if n<=0:return b''
        data=get_range(self.url,self.pos,self.pos+n-1);self.pos+=len(data);return data

def unpack(entry,data,offset):
    p=entry['offset']-offset
    vals=struct.unpack_from('<4s5H3I2H',data,p)
    if vals[0]!=b'PK\x03\x04':raise ValueError('Invalid local ZIP header')
    begin=p+30+vals[-2]+vals[-1]
    compressed=data[begin:begin+entry['compressed']]
    out=zlib.decompress(compressed,-15) if entry['method']==8 else compressed
    if len(out)!=entry['size'] or zlib.crc32(out)!=entry['crc']:raise ValueError('ZIP integrity failure')
    return out

def fetch_entries(url,size,entries,root):
    groups=[]
    for e in sorted(entries,key=lambda e:e['offset']):
        end=min(size-1,e['offset']+30+len(e['name'].encode())+4096+e['compressed'])
        if groups and e['offset']-groups[-1][1]<65536 and end-groups[-1][0]<8*1024*1024:
            groups[-1][1]=max(end,groups[-1][1]);groups[-1][2].append(e)
        else:groups.append([e['offset'],end,[e]])
    def fetch(group):
        start,end,es=group
        # Skip a group only when all existing members pass size and ZIP CRC checks.
        if all((root/e['name']).exists() and (root/e['name']).stat().st_size==e['size'] and zlib.crc32((root/e['name']).read_bytes())==e['crc'] for e in es):return
        data=get_range(url,start,end)
        for e in es:
            p=root/e['name'];p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(unpack(e,data,start))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for i,_ in enumerate(pool.map(fetch,groups),1):
            if i%20==0 or i==len(groups):print(f'Fetched {i}/{len(groups)} ranges',flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('data/raw/accuracy/vat-test-2026-11-18'));p.add_argument('--per-show',type=int,default=50);p.add_argument('--seed',type=int,default=20261118);a=p.parse_args();a.root.mkdir(parents=True,exist_ok=True)
    with urllib.request.urlopen(urllib.request.Request(SOURCE,method='HEAD'),timeout=45) as r:url=SOURCE;size=int(r.headers['Content-Length'])
    cache=a.root/'zip-index.json'
    if cache.exists():entries=json.loads(cache.read_text())
    else:
        with zipfile.ZipFile(RangeFile(url,size)) as z:
            entries=[dict(name=e.filename,offset=e.header_offset,compressed=e.compress_size,size=e.file_size,crc=e.CRC,method=e.compress_type) for e in z.infolist()]
        cache.write_text(json.dumps(entries))

    if any(Path(e['name']).is_absolute() or '..' in Path(e['name']).parts for e in entries):raise ValueError('Unsafe archive path')
    print('Archive entries:',len(entries),'bytes:',size,flush=True)
    ann=[e for e in entries if '/annotations/test/' in '/'+e['name'] and e['name'].endswith('.txt')]
    if not ann:
        print([e['name'] for e in entries[:30]],flush=True);raise ValueError('No official test labels found')
    print('Official test annotation files:',len(ann),flush=True);fetch_entries(url,size,ann,a.root)
    frames=collections.defaultdict(list)
    for e in sorted(ann,key=lambda e:e['name']):
        path=Path(e['name']);show,clip,track=path.parts[-3:]
        if show not in SHOWS:raise ValueError('Unexpected test show '+show)
        for row in csv.reader((a.root/e['name']).read_text().splitlines()):
            if len(row)!=7:raise ValueError('Invalid label row')
            frame,*vals=row;box=list(map(float,vals[:4]));gaze=list(map(float,vals[4:]));inside=gaze!=[-1.,-1.]
            key=f'{show}/{clip}/{frame}'
            frames[key].append(dict(track=track,head_bbox_pixels=box,gaze_pixels=gaze,inside=inside,annotation=e['name']))
    byname={e['name']:e for e in entries};selected=[];rng=random.Random(a.seed)
    for show in SHOWS:
        candidates=sorted(k for k in frames if k.split('/')[0]==show)
        if len(candidates)<a.per_show:raise ValueError('Insufficient test frames')
        for key in sorted(rng.sample(candidates,a.per_show)):
            matches=['images/'+key] if 'images/'+key in byname else []
            if len(matches)!=1:raise ValueError('Image resolution failed: '+key)
            selected.append(dict(key=key,image=matches[0],labels=frames[key]))
    manifest=dict(dataset='VideoAttentionTarget',split='official test',source=SOURCE,archive_bytes=size,archive_index_sha256=hashlib.sha256(cache.read_bytes()).hexdigest(),seed=a.seed,per_show=a.per_show,frames=selected,selection='Uniform sampling without replacement of unique annotated test frames within each of the 10 official test shows. All labeled tracks on selected frames retained. No outcome-based filtering.',training=False)
    frozen=a.root/'selection.json'
    if frozen.exists() and json.loads(frozen.read_text())!=manifest:raise ValueError('Refusing to change frozen selection')
    frozen.write_text(json.dumps(manifest,indent=2)+'\n')
    fetch_entries(url,size,[byname[r['image']] for r in selected],a.root)
    hashes={e['name']:hashlib.sha256((a.root/e['name']).read_bytes()).hexdigest() for e in ann+[byname[r['image']] for r in selected]}
    (a.root/'download-sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
    print('Ready:',len(selected),'test frames,',sum(len(f['labels']) for f in selected),'person labels',flush=True)
if __name__=='__main__':main()

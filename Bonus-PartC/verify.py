#!/usr/bin/env python3
"""Verify retained physical trace provenance and frame-metadata consistency."""
import argparse,csv,hashlib,json
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__);p.add_argument('batch',type=Path);a=p.parse_args()
report={'batch':str(a.batch),'complete_runs':[],'excluded_runs':[],'scope':'CSV/inference identity and envelope metadata; not image bytes or gaze accuracy'}
seen=set()
for folder in sorted(a.batch.glob('run-*')):
 m=json.loads((folder/'manifest.json').read_text())
 if m.get('status')!='complete':report['excluded_runs'].append(folder.name);continue
 source=m['source_session'];assert source not in seen,'Camera session reused across runs';seen.add(source)
 by_role={};hashes={}
 for role in ['glasses','phone','laptop']:
  path=folder/(role+'.csv')
  with path.open(newline='') as f:rows=list(csv.DictReader(f))
  assert all(None not in r for r in rows),f'{path}: malformed CSV fields'
  valid=[r for r in rows if r['event']=='frame_received' and r['source_session']==source]
  seqs=[int(r['sequence']) for r in valid]
  assert len(seqs)==len(set(seqs)),f'{path}: duplicated accepted frame'
  assert seqs==sorted(seqs),f'{path}: reordered accepted frame'
  assert all(int(b['local_mono_ns'])>=int(x['local_mono_ns']) for x,b in zip(valid,valid[1:])),f'{path}: receive clock reversed'
  by_role[role]={int(r['sequence']):r for r in valid}
 for seq,r in by_role['laptop'].items():
  for role in ['glasses','phone']:
   assert seq in by_role[role],f'{folder}: missing earlier-hop record for laptop sequence {seq}'
   for key in ['capture_mono_ns','capture_unix_ms','jpeg_bytes','width','height']:
    assert r[key]==by_role[role][seq][key],f'{folder}: relay altered {key}'
  assert m['measurement_start_mono_ns']<=int(r['local_mono_ns'])<=m['measurement_end_mono_ns']
 predictions=0
 with (folder/'inference.jsonl').open() as f:
  for line in f:
   r=json.loads(line);assert r['source_session']==source and r['sequence'] in by_role['laptop'];predictions+=1
 for filename in ['manifest.json','glasses.csv','phone.csv','laptop.csv','inference.jsonl','samples.jsonl','rtt.jsonl']:
  with (folder/filename).open('rb') as f:hashes[filename]=hashlib.file_digest(f,'sha256').hexdigest()
 report['complete_runs'].append({'run_id':folder.name,'laptop_frames':len(by_role['laptop']),'inferences':predictions,'sha256':hashes})
(a.batch/'trace-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(f"Verified {len(report['complete_runs'])} complete runs; frame envelope metadata preserved through all three devices.")

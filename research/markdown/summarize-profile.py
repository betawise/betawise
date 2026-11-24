#!/usr/bin/env python3
"""Compare emulated callback time, not host runtime or physical power."""
import json,argparse,statistics,struct
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('baseline',type=Path);ap.add_argument('current',type=Path);ap.add_argument('output',type=Path);a=ap.parse_args()
def read(path):
 checks=json.loads((path/'checks.json').read_text());events=json.loads((path/'timings.json').read_text().replace('\\"','"'))['events'];out=[];start=None;phases={}
 for e in events:
  if e['phase']==1:start=e;phases={1:e['time']}
  elif start:phases[e['phase']]=e['time']
  if e['phase']==4 and start and e['message']==0x1000001 and all(k in phases for k in (1,2,3,4)):
   out.append(dict(check=checks[e['check']-1]['name'],character=e['param'],total_ms=1000*(phases[4]-phases[1]),native_ms=1000*(phases[2]-phases[1]),markdown_ms=1000*(phases[3]-phases[2])))
 return out
old,new=read(a.baseline),read(a.current);rows=[]
checks=json.loads((a.current/'checks.json').read_text())
for i,c in enumerate(checks,1):
 if not c['name'].startswith('steady typing'):continue
 before=struct.unpack('>7I2H',(a.current/f'perf-{i-1:02d}.bin').read_bytes());after=struct.unpack('>7I2H',(a.current/f'perf-{i:02d}.bin').read_bytes())
 assert all(before[k]==after[k]for k in [1,3,4]),'steady typing decoded, parsed or rewrote the document'

for size in [50,500,1500]:
 before=next(x for x in old if x['check']=='type after '+str(size));first=next(x for x in new if x['check']=='type after '+str(size));steady=[x for x in new if x['check']=='steady typing after '+str(size)]
 rows.append(dict(source_characters=size,before_ms=before['total_ms'],first_key_ms=first['total_ms'],steady_ms=statistics.mean(x['total_ms']for x in steady),steady_markdown_ms=statistics.mean(x['markdown_ms']for x in steady)))
a.output.write_text(json.dumps(dict(method='Emulated time between guest phase writes around native editing and formatting. Not physical power; first/steady keys reported separately.',steady_no_scan_or_rewrite=True,rows=rows,before=old,after=new),indent=2)+'\n')
for r in rows:print(r)

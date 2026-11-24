#!/usr/bin/env python3
"""Audit native page-lookahead timing taps; no image/model inference."""
import argparse,json,statistics
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--viewport',action='store_true',help='audit raw append modes (private viewport or prewrapped), with no insertion taps');a=p.parse_args()
assert json.loads((a.run/'results.json').read_text())['status']=='passed'
events=json.loads((a.run/'timings.json').read_text());opened=next(e['time']for e in events if e['check']==2 and e['phase']==1)
inserts=[];idle=[];j=0
while j<len(events):
 e=events[j]
 if e['phase']==30 and e['time']>=opened:
  k=next(k for k in range(j+1,len(events))if events[k]['phase']==31);end=events[k]
  assert end['lcd_writes']==e['lcd_writes'],('idle append repainted LCD',e,end)
  idle.append(dict(prefix_bytes=e['file_bytes'],milliseconds=1000*(end['time']-e['time']),lcd_writes=0));j=k
 j+=1
for j,e in enumerate(events):
 if e['phase']!=33 or e['time']<opened:continue
 end=next(x for x in events[j+1:]if x['phase']==34)
 assert end['lcd_writes']==e['lcd_writes'],('insert repainted LCD',e,end)
 assert end['caret']==e['caret'],('insert changed native caret',e,end)
 inserts.append(dict(prefix_bytes=e['file_bytes'],milliseconds=1000*(end['time']-e['time']),lcd_writes=0))
assert idle
assert (not inserts) if a.viewport else bool(inserts)
r=dict(status='passed',run=str(a.run.resolve()),idle_slices=len(idle),idle_seconds=sum(x['milliseconds']for x in idle)/1000,max_idle_milliseconds=max(x['milliseconds']for x in idle),insert_calls=len(inserts),insert_seconds=sum(x['milliseconds']for x in inserts)/1000,lcd_data_writes=0,first_insert=inserts[0]if inserts else None,last_insert=inserts[-1]if inserts else None,inserts=inserts,idle=idle)
a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items()if k not in ('inserts','idle')},indent=2))

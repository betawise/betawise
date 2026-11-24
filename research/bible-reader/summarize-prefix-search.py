#!/usr/bin/env python3
"""Require MAME source/bitmap success and every backend hit-count/order checksum."""
from pathlib import Path
import argparse,json,struct
p=argparse.ArgumentParser(description=__doc__);p.add_argument('runs',nargs='+',type=Path);p.add_argument('--production',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();production={r['index']:r for r in json.loads((a.production/'results.json').read_text())};runs=[]
for folder in a.runs:
 result=json.loads((folder/'results.json').read_text());assert result['status']=='passed'
 meta=json.loads((folder/'search-option.json').read_text());expected=json.loads((folder/'prefix-expected.json').read_text());events=json.loads((folder/'timings.json').read_text());rows=[]
 for q,ref in enumerate(expected):
  q=ref.get("id",q)
  es=[e for e in events if e['phase']in(40,41,42,43)and e['search'][0]==q]
  start=next(e for e in es if e['phase']==40);setup=next(e for e in es if e['phase']==41);end=next(e for e in es if e['phase']==43);first=next((e for e in es if e['phase']==42),None);state=end['search']
  assert state[1]==ref['hits']and state[2]==ref['hash'],(meta['index'],ref,state)
  if ref['first']is not None:assert state[3:6]==ref['first']and first is not None
  else:assert state[3]==0xffffffff and first is None
  assert end['lcd_writes']==start['lcd_writes'],('backend unexpectedly repainted LCD',q)
  rows.append(dict(query=ref['query'],hits=state[1],hash=state[2],first=ref['first'],candidate_chapters=state[6],setup_seconds=setup['time']-start['time'],first_hit_seconds=first['time']-start['time']if first else None,all_hits_seconds=end['time']-start['time']))
 # The visible result is the first phase 4 following open_chapter after SearchStart.
 checks=json.loads((folder/'checks.json').read_text());ui=[]
 for i,c in enumerate(checks,1):
  if not c['name'].startswith('Prefix '):continue
  es=[e for e in events if e['check']==i];begin=next(e for e in es if e['phase']==9);j=next(j for j,e in enumerate(es)if e['time']>=begin['time']and e['phase']==1);end=next(e for e in es[j+1:]if e['phase']==4)
  ui.append(dict(query=c['name'][7:],accept_to_result_elapsed_seconds=end['time']-begin['time']))
 filepeak=max(struct.unpack_from('>I',(folder/f'metrics-{i:02}.bin').read_bytes(),24)[0]+sum(x*y for x,y in [(-1,struct.unpack_from('>I',(folder/f'editor-{i:02}.bin').read_bytes(),40)[0]),(1,struct.unpack_from('>I',(folder/f'editor-{i:02}.bin').read_bytes(),44)[0])])for i in range(1,len(checks)+1))
 runs.append(dict(index=meta['index'],status='passed',path=str(folder.resolve()),screen_states=len(result['results']),queries=rows,ui=ui,production=production[meta['index']],max_captured_file_bytes=filepeak))
a.output.write_text(json.dumps(dict(status='passed',scope='KJV Neo 3.21 MAME, backend service including common checksum bookkeeping; UI time includes idle gaps, index excluded from application code/assets',runs=runs),indent=2)+'\n')
for r in runs:
 print(r['index'],'ROM',r['production']['rom_bytes'],'A5',r['production']['a5_bytes'])
 for q in r['queries']:print(q['query'],q['hits'],q['candidate_chapters'],round(q['first_hit_seconds'],3)if q['first_hit_seconds']is not None else None,round(q['all_hits_seconds'],3))

#!/usr/bin/env python3
"""Require deterministic MAME checks and exact directional result coordinates."""
from pathlib import Path
import argparse,json
p=argparse.ArgumentParser(description=__doc__);p.add_argument('runs',nargs='+',type=Path);p.add_argument('--production',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();prod={r['index']:r for r in json.loads((a.production/'results.json').read_text())};runs=[]
for folder in a.runs:
 result=json.loads((folder/'results.json').read_text());assert result['status']=='passed'
 option=json.loads((folder/'search-option.json').read_text())['index'];cases=json.loads((folder/'navigation-expected.json').read_text());events=json.loads((folder/'timings.json').read_text());rows=[]
 for q,case in enumerate(cases):
  es=[e for e in events if e['phase']in(40,41,42,43)and e['search'][0]==q];start=next(e for e in es if e['phase']==40);setup=next(e for e in es if e['phase']==41);end=next(e for e in es if e['phase']==43);state=end['search'];expected=case['expected'];assert state[1]==int(expected is not None),(option,q,state,expected)
  if expected is None:assert state[3]==0xffffffff
  else:assert state[3:6]==expected,(option,q,state,expected)
  assert start['lcd_writes']==end['lcd_writes']
  rows.append(dict(case,setup_seconds=setup['time']-start['time'],scan_seconds=end['time']-setup['time'],total_seconds=end['time']-start['time']))
 runs.append(dict(index=option,status='passed',path=str(folder.resolve()),screen_checks=len(result['results']),production=prod[option],cases=rows))
a.output.write_text(json.dumps(dict(status='passed',scope='KJV Neo 3.21 MAME, cold query setup plus directional backend service; no LCD writes or UI idle gaps; 8-bit Huffman, no verse boost',runs=runs),indent=2)+'\n')
for i,c in enumerate(runs[0]['cases']):print(c.get('mode','legacy'),c['query'],c['chapter'],c['verse'],c['direction'],c['expected'],*[round(r['cases'][i]['total_seconds'],3)for r in runs])

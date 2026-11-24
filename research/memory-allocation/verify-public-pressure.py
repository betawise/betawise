#!/usr/bin/env python3
"""Verify public FileCreate low-memory fallback evidence independently."""
from pathlib import Path
import gzip, hashlib, json, sys
HERE = Path(__file__).resolve().parent
OUT = Path(sys.argv[1]) if len(sys.argv)>1 else HERE/'public-pressure-evidence'
m=json.loads((OUT/'manifest.json').read_text())
layouts={'as3000':(0x1042,0x4558,0x354e), 'neo_3_01':(0x109a,0x69c0,0x35a6), 'neo_3_21':(0x10d2,0x1509c,0x35de)}
assert {r['rom'] for r in m['runs']}==set(layouts)
for name,h in m['scripts'].items(): assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==h
for r in m['runs']:
 name=r['rom']; first,payload,floor=layouts[name]
 log=(OUT/name/'mame.log').read_bytes()
 assert hashlib.sha256(log).hexdigest()==r['log_sha256']
 assert b'PASS public pressure qualification complete '+name.encode() in log and b'FAIL ' not in log
 assert hashlib.sha256((OUT/name/'probe.lua').read_bytes()).hexdigest()==r['probe_sha256']
 assert len(r['artifacts'])==5
 for a in r['artifacts']:
  b=(OUT/a['file']).read_bytes();assert hashlib.sha256(b).hexdigest()==a['gzip_sha256']
  raw=gzip.decompress(b);assert hashlib.sha256(raw).hexdigest()==a['raw_sha256']
  num=lambda p:int.from_bytes(raw[p:p+4],'big')
  if 'pressure-before' in a['file']:
   assert num(floor)==payload+4096
   assert (num(first+4),num(first+8),num(first+72+8))==(200,256,1300)
  if 'pressure-after' in a['file']:
   assert num(floor)==payload+4096
   assert (num(first+4),num(first+8),num(first+72+8))==(0,0,1000)
   for i,retained in [(1,1000),(2,2000)]:
    e=first+i*72;ptr=num(e);cap=num(e+12)
    assert ptr+cap<=num(floor)
    assert raw[ptr:ptr+retained]==bytes(((i+1)*53+j*17)&255 for j in range(retained))
print('PASS three-ROM public FileCreate pressure fallback clears clipboard and snapshots saved lengths; live ordinary payloads survive')

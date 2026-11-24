#!/usr/bin/env python3
"""Verify independent captured RAM/vector records; supports retained gzip captures."""
from pathlib import Path
import gzip,hashlib,json,struct,sys
root=Path(sys.argv[1]).resolve()
def read(n):
 p=root/n
 return p.read_bytes() if p.exists() else gzip.decompress(Path(str(p)+'.gz').read_bytes())
u32=lambda b,a:struct.unpack_from('>I',b,a)[0]
checks=[];hashes={}
for n,expected in [('cold',0),('fline-executed',0x458000),('warm',0x458000),('ram-loader',0x458000),('hardware-reset',0)]:
 b=read(n+'.ram');assert len(b)==524288
 assert u32(b,0x2c)==expected,(n,hex(u32(b,0x2c)))
 assert u32(b,0x28)==0x426768
 if n in ['fline-executed','warm','ram-loader']:assert u32(b,0x30020)==0x464c494e
 if n=='ram-loader':assert u32(b,0x5c400)==0x52414d49
 hashes[n]=hashlib.sha256(b).hexdigest();checks.append(n+' RAM/vector assertions')
records=[json.loads(l) for l in read('vectors.jsonl').decode().splitlines()]
assert not [r for r in records if 0x2c<=r['address']<0x30 and r['phase']!='test-install']
assert any(r['phase']=='ram-loader' and r['address']==0x28 for r in records)
checks.append('no observed firmware F-line vector writes; native RAM loader rewrites A-line')
log=read('mame.log').decode();assert 'PASS vector lifecycle' in log and 'FAIL ' not in log
print(json.dumps({'result':'PASS','checks':checks,'ram_sha256':hashes,'reset_caveat':'MAME machine_reset mirrors SmallROM into first 256 SRAM bytes; physical retained-SRAM reset result unproven'},indent=2))

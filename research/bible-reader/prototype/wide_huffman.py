#!/usr/bin/env python3
"""Optional larger first-stage lookup; original container/payload stay unchanged."""
from pathlib import Path
import argparse,struct
p=argparse.ArgumentParser(description=__doc__);p.add_argument('container',type=Path);p.add_argument('bits',type=int,choices=[8,10,12]);p.add_argument('output',type=Path);a=p.parse_args()
if a.bits==8:a.output.write_bytes(b'');raise SystemExit
b=a.container.read_bytes();m,nt,ls,ms,nc,raw,ng,maxbits=struct.unpack_from('>8I',b,8);model=b[64+m+ls:64+m+ls+ms];order=struct.unpack_from('>'+str(nt+ng)+'H',model,4+8*maxbits);table=[0]*(1<<a.bits)
for n in range(1,min(a.bits,maxbits)+1):
 first,start,count=struct.unpack_from('>IHH',model,4+8*(n-1))
 for k in range(count):
  s=order[start+k]
  for prefix in range((first+k)<<(a.bits-n),(first+k+1)<<(a.bits-n)):table[prefix]=(s<<5)|n
blob=struct.pack('>'+str(len(table))+'I',*table);a.output.write_bytes(blob)

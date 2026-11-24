#!/usr/bin/env python3
"""Select full, grouped-prefix or scan-only metadata without recompressing text."""
from pathlib import Path
from collections import defaultdict
import argparse,json,re,struct,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'research/bible-reader'))
from packed_index import delta,elias_fano

def select(data,kind):
 if kind=='none':return b''
 old=(data/'search.bin').read_bytes()
 if kind=='full':return old
 if old[:8]!=b'IDXEXP02':raise ValueError('compact/scan require the packed-prune source profile')
 nw,nt=struct.unpack_from('>HH',old,8);mapping_start=20+4*(nw+1);mapping=old[mapping_start:mapping_start+(14*nt+7)//8]
 canonical=b''.join((struct.unpack_from('>I',old,20+4*i)[0]>>18).to_bytes(2,'big')for i in range(nw))
 lex=b'PFXLEX01'+struct.pack('>HHII',nw,nt,0,len(mapping))+canonical+mapping
 if kind=='scan':return lex
 books=json.loads((data/'source.json').read_text());chapters=[c for b in books for c in b['chapters']];buckets=defaultdict(set);group=8;U=(len(chapters)+group-1)//group
 for i,ch in enumerate(chapters):
  for verse in ch:
   for word in re.findall(r"[a-z]+(?:'[a-z]+)*",verse.lower()):buckets[word[:4]].add(i//group)
 keys=sorted(buckets);records=bytearray();body=bytearray();allgroups=set(range(U))
 for key in keys:
  xs=sorted(buckets[key]);comp=sorted(allgroups-buckets[key]);bm=sum(1<<x for x in xs).to_bytes((U+7)//8,'little')
  mode,payload=min([(0,delta(xs)),(1,elias_fano(xs,U)),(2,bm),(3,delta(comp)),(4,elias_fano(comp,U))],key=lambda x:len(x[1]))
  records+=key.encode('ascii').ljust(4,b'\0')+len(body).to_bytes(3,'big');body+=bytes([mode])+payload
 records+=len(body).to_bytes(3,'big')
 return lex+b'PFXGRP01'+struct.pack('>HHHHI',4,group,len(keys),U,len(body))+records+body
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('data',type=Path);p.add_argument('kind',choices=['full','compact','scan','none']);p.add_argument('output',type=Path);a=p.parse_args();a.output.write_bytes(select(a.data,a.kind))

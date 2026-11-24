#!/usr/bin/env python3
"""Materialize KJV device comparison resources from verified host experiments."""
import hashlib,json,shutil,struct
from pathlib import Path
root=Path(__file__).resolve().parents[3];base=root/'.research-work/bible-compression';source=base/'reader/kjv';experiment=base/'search-space-kjv-verified';out=base/'device-comparison'
old=(source/'container.bin').read_bytes();index=(source/'search.bin').read_bytes();nw,nt=struct.unpack_from('>II',index,8)
for name in ['word-scdc','huffman-prune']:
 p=out/name;p.mkdir(parents=True,exist_ok=True)
 for f in ['source.json','verses.bin']:shutil.copyfile(source/f,p/f)
 if name=='huffman-prune':
  blob=old;search=(experiment/'index-packed-group1.bin').read_bytes();shutil.copyfile(experiment/'grammar-scan-summaries.bin',p/'pruning.bin')
 else:
  dense=(experiment/'word-dense-s223.resource').read_bytes();_,m,ls,s,nr,ng,nc,np=struct.unpack_from('>8s7I',dense);assert ng==0 and nr==nt
  h=bytearray(old[:64]);h[:8]=b'KJVDNS01';struct.pack_into('>8I',h,8,m,nt,ls,2*nr,nc,4138567,0,s)
  hot=old[struct.unpack_from('>I',old,40)[0]:];struct.pack_into('>I',h,40,len(dense));blob=bytes(h)+dense[64:]+hot
  records=b''.join(index[20+5*i:22+5*i]for i in range(nw));mapping=index[20+5*(nw+1):20+5*(nw+1)+2*nt];search=struct.pack('>8sIII',b'BIBSRCH4',nw,nt,0)+records+mapping;(p/'pruning.bin').write_bytes(b'')
 (p/'container.bin').write_bytes(blob);(p/'search.bin').write_bytes(search)
 report=json.loads((source/'results.json').read_text());report.update(sha256=hashlib.sha256(blob).hexdigest(),bytes=len(blob),search_bytes=len(search),search_index_kind=name);(p/'results.json').write_text(json.dumps(report,indent=2)+'\n');print(name,len(blob),len(search))

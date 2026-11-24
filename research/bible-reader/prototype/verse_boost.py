#!/usr/bin/env python3
"""Experimental selective God-prefix verse postings and compact verse restarts."""
from pathlib import Path
from collections import defaultdict
import argparse,json,re,struct,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'research/bible-reader'))
from measure import unpack
from packed_index import delta
p=argparse.ArgumentParser(description=__doc__);p.add_argument('data',type=Path);p.add_argument('enabled',type=int);p.add_argument('output',type=Path);a=p.parse_args()
if not a.enabled:a.output.write_bytes(b'');raise SystemExit
b=(a.data/'container.bin').read_bytes();idx=(a.data/'search.bin').read_bytes();books=json.loads((a.data/'source.json').read_text());chapters=[c for book in books for c in book['chapters']];word=re.compile(r"[a-z]+(?:'[a-z]+)*");names=sorted({w for ch in chapters for v in ch for w in word.findall(v.lower())});selected=[w for w in names if w.startswith('god')];lo=names.index(selected[0]);assert names[lo:lo+len(selected)]==selected
m,nt,ls,ms,nc,raw,ng,maxbits=struct.unpack_from('>8I',b,8);mo=64+m+ls;model=b[mo:mo+ms];order=struct.unpack_from('>'+str(nt+ng)+'H',model,4+8*maxbits);codes={}
for n in range(1,maxbits+1):
 first,start,count=struct.unpack_from('>IHH',model,4+8*(n-1))
 for k in range(count):codes[order[start+k]]=(first+k,n)
gram=mo+ms;rules=[struct.unpack_from('>HH',b,gram+4*i)for i in range(ng)];rec=gram+4*ng;payload=rec+16*nc;mapstart=20+4*(len(names)+1);mapping=idx[mapstart:];norm=[]
for i in range(nt):
 bit=14*i;v=int.from_bytes(mapping[bit//8:bit//8+3].ljust(3,b'\0'),'big');norm.append((v>>(10-(bit&7)))&16383)
def varint(n):
 out=bytearray()
 while n>=128:out.append((n&127)|128);n>>=7
 out.append(n);return out
anchors=bytearray();records=bytearray();post=defaultdict(set);global_verse=0;maxskip=0;anchor_count=0
for ci,ch in enumerate(chapters):
 records+=global_verse.to_bytes(2,'big');off,size,count,_=struct.unpack_from('>4I',b,rec+16*ci);seq=unpack(b[payload+off:payload+off+size],codes,count);bitpos=0;begin=True;vi=0;starts=[]
 for root in seq:
  stack=[root];leaves=[]
  while stack:
   t=stack.pop()
   if t<nt:leaves.append(t)
   else:l,r=rules[t-nt];stack.extend([r,l])
  for skip,t in enumerate(leaves):
   if begin:
    assert skip<256 and bitpos<1<<24;starts.append((bitpos,skip));maxskip=max(maxskip,skip);begin=False
   if norm[t]==len(names):vi+=1;begin=True
  bitpos+=codes[root][1]
 assert vi==len(ch)and begin and len(starts)==len(ch)
 for vi,v in enumerate(ch):
  ws=set(word.findall(v.lower()))&set(selected)
  for w in ws:post[w].add(global_verse+vi)
  if ws:
   bitpos0,skip=starts[vi];anchors+=(global_verse+vi).to_bytes(2,'big')+bitpos0.to_bytes(3,'big')+bytes([skip]);anchor_count+=1
 global_verse+=len(ch)
records+=global_verse.to_bytes(2,'big');offsets=bytearray();body=bytearray()
for w in selected:offsets+=len(body).to_bytes(3,'big');body+=delta(sorted(post[w]))
offsets+=len(body).to_bytes(3,'big')
blob=struct.pack('>8s4H2I',b'VBOOST03',lo,lo+len(selected),global_verse,nc,len(anchors),len(body))+records+offsets+anchors+body;a.output.write_bytes(blob)
a.output.with_suffix('.json').write_text(json.dumps(dict(bytes=len(blob),anchor_bytes=len(anchors),anchor_records=anchor_count,chapter_record_bytes=len(records),posting_bytes=len(body),words=selected,lo=lo,hi=lo+len(selected),verses=global_verse,max_skip=maxskip,matching_verses=len(set().union(*(post[w]for w in selected)))),indent=2)+'\n')

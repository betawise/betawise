#!/usr/bin/env python3
"""Host-only KJV prefix/chapter-group filters; serialized posting round trips.

Does not change applets or establish MAME search speed.
"""
import sys,json,re,struct,argparse
from pathlib import Path
from collections import defaultdict
sys.path.insert(0,str(Path(__file__).resolve().parent))
from packed_index import delta,elias_fano
workspace=Path(__file__).resolve().parents[3];ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--data',type=Path,default=workspace/'.research-work/bible-compression/reader-viewer/kjv');ap.add_argument('--output',type=Path,default=workspace/'.research-work/bible-compression/prefix-filter-host');args=ap.parse_args();root=args.data;out=args.output;out.mkdir(parents=True,exist_ok=True);books=json.loads((root/'source.json').read_text());chapters=[c for b in books for c in b['chapters']];post=defaultdict(set);word=re.compile(r"[a-z]+(?:'[a-z]+)*")
for i,ch in enumerate(chapters):
 for verse in ch:
  for w in word.findall(verse.lower()):post[w].add(i)
names=sorted(post);index=(root/'search.bin').read_bytes();nw,nt=struct.unpack_from('>HH',index,8);assert nw==len(names)
base=20+2*nw+(14*nt+7)//8
records_start=20;mapping_start=20+4*(nw+1);mapping=index[mapping_start:mapping_start+(14*nt+7)//8]
canonical=b''.join((struct.unpack_from('>I',index,20+4*i)[0]>>18).to_bytes(2,'big')for i in range(nw))
lexicon=b'PFXLEX01'+struct.pack('>HHII',nw,nt,0,len(mapping))+canonical+mapping
assert len(lexicon)==base
(out/'lexicon-map.bin').write_bytes(lexicon)

def packed(xs,U):
 xs=sorted(xs);comp=sorted(set(range(U))-set(xs));bm=sum(1<<x for x in xs).to_bytes((U+7)//8,'little');return min([(0,delta(xs)),(1,elias_fano(xs,U)),(2,bm),(3,delta(comp)),(4,elias_fano(comp,U))],key=lambda x:len(x[1]))
def unpack(mode,b,U):
 if mode in (0,3):
  xs=[];n=shift=0;last=-1
  for x in b:
   n|=(x&127)<<shift
   if x&128:shift+=7
   else:last+=n;xs.append(last);n=shift=0
 elif mode==2:xs=[x for x in range(U)if b[x//8]>>(x%8)&1]
 else:
  n,l=struct.unpack_from('>HB',b);b=b[3:];xs=[];k=0
  for j in range(n*l,len(b)*8):
   if b[j//8]>>(j%8)&1:
    v=sum(((b[(k*l+t)//8]>>((k*l+t)%8))&1)<<t for t in range(l));xs.append(v+((j-n*l-k)<<l));k+=1
    if k==n:break
 if mode in(3,4):return set(range(U))-set(xs)
 return set(xs)
report=[]
for width in [3,4]:
 for group in [1,4,8]:
  buckets=defaultdict(set);U=(len(chapters)+group-1)//group
  for w,xs in post.items():buckets[w[:width]].update(x//group for x in xs)
  body=bytearray();records=bytearray();keys=sorted(buckets)
  for key in keys:
   mode,data=packed(buckets[key],U);assert unpack(mode,data,U)==buckets[key]
   records+=key.encode().ljust(width,b'\0')+len(body).to_bytes(3,'big');body+=bytes([mode])+data
  records+=len(body).to_bytes(3,'big');blob=b'PFXTEST1'+struct.pack('>HHHHI',width,group,len(keys),U,len(body))+records+body
  (out/f'prefix{width}-group{group}.bin').write_bytes(blob)
  parsed_width,parsed_group,parsed_keys,parsed_U,parsed_size=struct.unpack_from('>HHHHI',blob,8)
  assert (parsed_width,parsed_group,parsed_keys,parsed_U,parsed_size)==(width,group,len(keys),U,len(body))
  start=20+(width+3)*len(keys)+3
  for i,key in enumerate(keys):
   pos=20+i*(width+3);assert blob[pos:pos+width].rstrip(b'\0').decode()==key
   a=int.from_bytes(blob[pos+width:pos+width+3],'big');pos2=20+(i+1)*(width+3)
   b=int.from_bytes(blob[pos2+width:pos2+width+3],'big')if i+1<len(keys)else int.from_bytes(blob[pos2:pos2+3],'big')
   assert unpack(blob[start+a],blob[start+a+1:start+b],U)==buckets[key]
  queries=[]
  for q in ['methus','meth','jes','believ','love','th']:
   completions=[w for w in names if w.startswith(q)];exact=set().union(*(post[w]for w in completions))
   matched=[k for k in keys if k.startswith(q)]if len(q)<width else[q[:width]]
   groups=set().union(*(buckets.get(k,set())for k in matched));candidate={i for i in range(len(chapters))if i//group in groups};assert exact<=candidate
   queries.append(dict(query=q,words=completions[:12],matching_words=len(completions),exact_candidate_chapters=len(exact),prefix_bucket_chapters=len(candidate)))
  report.append(dict(prefix_characters=width,chapter_group=group,buckets=len(keys),filter_bytes=len(blob),existing_style_lexicon_map_bytes=base,total_with_lexicon_map=len(blob)+base,queries=queries))
(out/'results.json').write_text(json.dumps(dict(exact_index_bytes=len(index),lexicon_map_bytes=base,rows=report),indent=2)+'\n')
print('exact',len(index),'lexicon/map',base)
for r in report:print({k:v for k,v in r.items()if k!='queries'},'Methus',r['queries'][0])

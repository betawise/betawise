#!/usr/bin/env python3
"""KJV host-only lossless dense-code and compact chapter-index experiments.

Writes experimental resources outside the source tree. Never changes the applet.
CPU timings on the host are not Neo timing predictions.
"""
import argparse, collections, hashlib, heapq, json, math, re, struct, subprocess, sys, tempfile, time
from pathlib import Path
from compare_translations import TOKEN, front_dictionary
from measure import unpack

WORD=re.compile(rb"[A-Za-z]+(?:'[A-Za-z]+)*")
QUERIES=['God','the earth','in the beginning','Jesus','Jesus Jesus','believe','believed','zzzzunknown','love love','verily verily','I am that I am','a a',"LORD's","Jesus'"]
def varint(n):
 b=bytearray()
 while n>=128:b.append((n&127)|128);n>>=7
 b.append(n);return bytes(b)
def delta(xs):
 last=-1;b=bytearray()
 for x in xs:b+=varint(x-last);last=x
 return bytes(b)
def undelta(b):
 out=[];last=-1;n=shift=0
 for c in b:
  n|=(c&127)<<shift
  if c&128:shift+=7
  else:last+=n;out.append(last);n=shift=0
 assert not shift
 return out
def ef(xs,U):
 n=len(xs)
 if not n:return b'\0\0\0'
 l=max(0,(U//n).bit_length()-1);bits=n*l+(xs[-1]>>l)+n+1;b=bytearray((bits+7)//8)
 def put(i):b[i//8]|=1<<(i%8)
 for j,x in enumerate(xs):
  for k in range(l):
   if x>>k&1:put(j*l+k)
  put(n*l+(x>>l)+j)
 return struct.pack('>HB',n,l)+b
def unef(b):
 n,l=struct.unpack_from('>HB',b);b=b[3:];out=[]
 def bit(i):return b[i//8]>>(i%8)&1
 for i in range(n*l,len(b)*8):
  if bit(i):
   j=len(out);low=sum(bit(j*l+k)<<k for k in range(l));out.append(((i-n*l-j)<<l)|low)
   if len(out)==n:break
 assert len(out)==n
 return out

def dense_code(rank,s=128):
 # s stoppers and c=256-s continuers; ETDC is s=c=128.
 c=256-s;length=1;capacity=s
 while rank>=capacity:rank-=capacity;length+=1;capacity*=c
 tail=rank%s;rank//=s;digits=[]
 for _ in range(length-1):digits.append(rank%c);rank//=c
 assert rank==0
 return bytes(list(reversed(digits))+[c+tail])
def dense_decode(b,s):
 c=256-s;rank=0;base=0;capacity=s;out=[]
 for x in b:
  if x<c:rank=rank*c+x;base+=capacity;capacity*=c
  else:out.append(base+rank*s+x-c);rank=base=0;capacity=s
 assert rank==base==0
 return out

def main():
 ap=argparse.ArgumentParser(description=__doc__);root=Path(__file__).resolve().parents[3]
 ap.add_argument('--data',type=Path,default=root/'.research-work/bible-compression/reader/kjv');ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();out=a.output;out.mkdir(parents=True,exist_ok=False)
 source=(a.data/'source.json').read_bytes();books=json.loads(source);blocks=[('\n'.join(c)+'\n').encode()for b in books for c in b['chapters']];U=len(blocks)
 tokens=[TOKEN.findall(b.decode())for b in blocks];words=sorted({w for ts in tokens for w in ts});wid={w:i for i,w in enumerate(words)};seqs=[[wid[w]for w in ts]for ts in tokens];freq=collections.Counter(x for seq in seqs for x in seq)
 postings=collections.defaultdict(set)
 for ci,b in enumerate(blocks):
  for w in WORD.findall(b.lower()):postings[w].add(ci)
 names=sorted(postings);leaves=list(map(len,seqs));total_leaves=sum(leaves);terms=len(words);base=20+5*(len(names)+1)+2*terms
 index_reports=[];querysets={q:[set(postings.get(w,set()))for w in WORD.findall(q.lower().encode())]for q in QUERIES}
 def workload(candidate):
  results=[]
  for q,sets in querysets.items():
   exact=set.intersection(*sets)if sets else set();got=candidate(q,sets);assert exact<=got
   results.append(dict(query=q,exact_chapters=len(exact),candidate_chapters=len(got),terminal_leaves=sum(leaves[i]for i in got),exact_terminal_leaves=sum(leaves[i]for i in exact)))
  return results
 for group in [1,2,4,8,16,32,64]:
  universe=(U+group-1)//group;payload=bytearray();offsets=[];modes=collections.Counter()
  for w in names:
   xs=sorted({i//group for i in postings[w]});complement=sorted(set(range(universe))-set(xs));bitmap=sum(1<<x for x in xs).to_bytes((universe+7)//8,'little')
   options=[(0,delta(xs)),(1,ef(xs,universe)),(2,bitmap),(3,delta(complement)),(4,ef(complement,universe))];mode,b=min(options,key=lambda x:len(x[1]));record=bytes([mode])+b;offsets.append(len(payload));payload+=record;modes[mode]+=1
   if mode==0:restored=undelta(b)
   elif mode==1:restored=unef(b)
   elif mode==2:restored=[i for i in range(universe)if b[i//8]>>(i%8)&1]
   else:restored=sorted(set(range(universe))-set(undelta(b)if mode==3 else unef(b)))
   assert restored==xs
  # Serialize a complete experimental index, including real canonical IDs,
  # offset records and the terminal-normalization map from the baseline.
  old=(a.data/'search.bin').read_bytes();records=bytearray()
  for j,offset in enumerate(offsets):records+=old[20+5*j:22+5*j]+offset.to_bytes(3,'big')
  records+=bytes(2)+len(payload).to_bytes(3,'big')
  mapping=old[20+5*(len(names)+1):20+5*(len(names)+1)+2*terms]
  complete=struct.pack('>8sHHII',b'IDXEXP01',len(names),terms,group,len(payload))+records+mapping+payload
  assert len(complete)==base+len(payload)
  (out/f'index-hybrid-group{group}.bin').write_bytes(complete)
  def candidates(q,sets):
   groups=set.intersection(*[{x//group for x in s}for s in sets]);return {i for g in groups for i in range(g*group,min(U,(g+1)*group))}
  index_reports.append(dict(kind='hybrid',group=group,bytes=base+len(payload),payload_bytes=len(payload),record_modes=dict(modes),all_postings_roundtrip_exact=True,queries=workload(candidates)))
 # Plain grouped delta lists, compatible in principle with existing posting reader.
 for group in [1,2,4,8,16,32,64]:
  size=base+sum(len(delta(sorted({i//group for i in postings[w]})))for w in names)
  def candidates(q,sets):
   gs=set.intersection(*[{x//group for x in s}for s in sets]);return {i for g in gs for i in range(g*group,min(U,(g+1)*group))}
  index_reports.append(dict(kind='delta',group=group,bytes=size,queries=workload(candidates)))
 # Chapter Bloom filters need only canonical IDs + terminal mapping, no posting offsets.
 ids={w:i for i,w in enumerate(names)}
 for bits in [128,256,512,1024,2048,4096]:
  masks=[]
  for ci in range(U):
   mask=0
   for w in set(WORD.findall(blocks[ci].lower())):
    h=int.from_bytes(hashlib.blake2s(w,digest_size=4).digest(),'little');mask|=1<<(h%bits);mask|=1<<((h>>16)%bits)
   masks.append(mask)
  def candidates(q,sets):
   pattern=0
   for w in WORD.findall(q.lower().encode()):
    if w not in ids:return set()
    h=int.from_bytes(hashlib.blake2s(w,digest_size=4).digest(),'little');pattern|=1<<(h%bits);pattern|=1<<((h>>16)%bits)
   return {i for i,m in enumerate(masks)if m&pattern==pattern}
  index_reports.append(dict(kind='chapter-bloom-2hash',bits=bits,bytes=20+2*len(names)+2*terms+U*bits//8,queries=workload(candidates)))
 index_reports.append(dict(kind='none',bytes=2*len(names)+2*terms+20,queries=workload(lambda q,sets:set(range(U))if all(sets)else set()),note='Retains query lexicon and terminal normalization map; no chapter postings.'))
 # Parse the actual trained phrase stream, preserving all existing rules.
 image=(a.data/'container.bin').read_bytes();m,nt,ls,ms,nc,rawbytes,ng,maxbits=struct.unpack_from('>8I',image,8);assert nt==terms and nc==U
 model=image[64+m+ls:64+m+ls+ms];alphabet=struct.unpack_from('>H',model,2)[0];ordered=struct.unpack_from('>'+str(alphabet)+'H',model,4+8*maxbits);codes={}
 for n in range(1,maxbits+1):
  first,start,count=struct.unpack_from('>IHH',model,4+8*(n-1))
  for k in range(count):codes[ordered[start+k]]=(first+k,n)
 ix=64+m+ls+ms+4*ng;payload=ix+16*U;phrase=[]
 for ci in range(U):
  off,size,count,raw=struct.unpack_from('>4I',image,ix+ci*16);phrase.append(unpack(image[payload+off:payload+off+size],codes,count))
 codec_reports=[];dictionary=front_dictionary(words);frame=64+m+len(dictionary)+16*U
 binary=out/'dense-search-check'
 subprocess.run(['cc','-O2','-std=c99',str(Path(__file__).with_name('dense_search_check.c')),'-o',str(binary)],check=True)
 oracle={}
 for q in QUERIES:
  qw=WORD.findall(q.lower().encode());hits=[]
  for ci,ch in enumerate(c for b in books for c in b['chapters']):
   for vi,v in enumerate(ch,1):
    vs=WORD.findall(v.lower().encode())
    hits.extend((ci,vi,j)for j in range(len(vs))if vs[j:j+len(qw)]==qw)
  oracle[q]=hits
 rules_expanded=[struct.unpack_from('>HH',image,64+m+ls+ms+4*i)for i in range(ng)]
 for label,sequences,rules in [('word',seqs,0),('phrase',phrase,ng)]:
  f=collections.Counter(x for seq in sequences for x in seq);ranked=sorted(f,key=lambda x:(-f[x],x));ranks={x:i for i,x in enumerate(ranked)}
  def size_for(s):return sum(f[x]*len(dense_code(i,s))for i,x in enumerate(ranked))
  best=min(range(1,256),key=size_for)
  for s in sorted({128,best}):
   code={x:dense_code(i,s)for i,x in enumerate(ranked)};encoded=[];t=time.perf_counter()
   for ci,seq in enumerate(sequences):
    b=b''.join(code[x]for x in seq);restored=[ranked[i]for i in dense_decode(b,s)];assert restored==seq
    if label=='word':assert ''.join(words[x]for x in restored).encode()==blocks[ci]
    else:
     expanded=[];stack=[]
     for symbol in restored:
      stack.append(symbol)
      while stack:
       x=stack.pop()
       if x<terms:expanded.append(x)
       else:left,right=rules_expanded[x-terms];stack.extend([right,left])
     assert ''.join(words[x]for x in expanded).encode()==blocks[ci]
    encoded.append(b)
   blob=b''.join(encoded);blobpath=out/f'{label}-dense-s{s}.bin';blobpath.write_bytes(blob)
   offsets=[0]
   for b in encoded:offsets.append(offsets[-1]+len(b))
   # Prototype resource header: metadata/dictionary lengths, stopper count,
   # rank count, grammar count and chapter count. Chapter records retain the
   # baseline 16-byte framing. Rank entries resolve to original terminal IDs.
   ranktable=b''.join(struct.pack('>H',x)for x in ranked)
   chaptertable=b''.join(struct.pack('>4I',offsets[i],len(b),len(sequences[i]),len(blocks[i]))for i,b in enumerate(encoded))
   header=struct.pack('>8s7I',b'DENSEX01',m,len(dictionary),s,len(ranked),rules,U,len(blob)).ljust(64,b'\0')
   resource=header+image[64:64+m]+dictionary+ranktable+image[64+m+ls+ms:64+m+ls+ms+4*rules]+chaptertable+blob
   assert len(resource)==frame+2*len(ranked)+4*rules+len(blob)
   (out/f'{label}-dense-s{s}.resource').write_bytes(resource)
   codec_reports.append(dict(kind=label+'-dense',stoppers=s,continuers=256-s,payload_bytes=len(blob),dictionary_bytes=len(dictionary),rank_table_bytes=2*len(ranked),grammar_bytes=4*rules,resource_bytes=frame+2*len(ranked)+4*rules+len(blob),all_chapter_symbols_roundtrip_exact=True,full_text_roundtrip_exact=True,host_encode_and_verify_seconds=time.perf_counter()-t,sha256=hashlib.sha256(blob).hexdigest(),search_note='Word codes allow direct single-word search; phrase codes require expansion or grammar-aware matching.'))
   if label=='word':
    indexpath=out/f'word-s{s}.chapter-offsets';indexpath.write_bytes(struct.pack('>'+str(len(offsets))+'I',*offsets))
    norm=[]
    for x in ranked:
     w=words[x].encode();normal=w.lstrip(b' ').lower();norm.append(65534 if w==b'\n' else ids.get(normal,65535))
    mappath=out/f'word-s{s}.normalization';mappath.write_bytes(struct.pack('>'+str(len(norm))+'H',*norm))
    checks=[]
    for q in QUERIES:
     queryids=[ids.get(w,65533)for w in WORD.findall(q.lower().encode())];t=time.perf_counter()
     actual=subprocess.check_output([str(binary),str(blobpath),str(indexpath),str(mappath),str(s),*map(str,queryids)],text=True)
     got=[tuple(map(int,row.split()))for row in actual.splitlines()];assert got==oracle[q],(q,got[:5],oracle[q][:5]);checks.append(dict(query=q,occurrences=len(got),exact=True,host_process_seconds=time.perf_counter()-t))
    codec_reports[-1]['native_host_kmp_checks']=checks
   if label=='word'and s==128:
    # Direct codeword searches: enforce preceding stopper/start boundary. Every
    # case/leading-space variant is included, so whole-word search is exact.
    direct=[]
    for query in ['God','Jesus','believe','believed',"LORD's"]:
     variants=[x for x,w in enumerate(words)if w.lstrip(' ').lower()==query.lower()];patterns=[code[x]for x in variants];expected=sum(len([w for w in WORD.findall(b.lower())if w==query.lower().encode()])for b in blocks);hits=0;examined=0;t=time.perf_counter()
     for b in encoded:
      for p in patterns:
       start=0
       while True:
        at=b.find(p,start)
        if at<0:break
        examined+=1
        if at==0 or b[at-1]>=128:hits+=1
        start=at+1
     assert hits==expected,(query,hits,expected)
     direct.append(dict(query=query,occurrences=hits,raw_candidates=examined,variants=len(patterns),host_seconds=time.perf_counter()-t,exact=True))
    codec_reports[-1]['direct_single_word_search']=direct
 # Existing resource breakdown makes totals comparable (no applet code estimate).
 baseline=json.loads((a.data/'results.json').read_bytes());report=dict(source_sha256=hashlib.sha256(source).hexdigest(),chapters=U,terminal_leaves=total_leaves,vocabulary=len(names),baseline=baseline,index_fixed_overhead=base,index_experiments=index_reports,codec_experiments=codec_reports,notes=['All sizes include dictionaries, rank/model tables and 16-byte chapter framing; dense sizes exclude search index and hot cache.','Dense KMP correctness uses an auxiliary 2-byte-per-rank normalization table, not included in resource sizes; this could be avoided with per-query rank-variant sets.','Dense word streams preserve spelling/case/punctuation. Direct phrase byte search alone does not implement punctuation-insensitive case-insensitive semantics.','Bloom hashes computed on host; a device implementation can precompute per-word hashes, but their additional storage is not counted here.','Workload terminal leaves are scan-volume proxies, not measured CPU times.'])
 (out/'results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k not in ['index_experiments','codec_experiments']},indent=2));print('Done',out,flush=True)
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Count KJV scan work and size verse postings/restarts; not device timings."""
from pathlib import Path
from collections import Counter,defaultdict
import struct,json,re,argparse,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from measure import unpack
from packed_index import delta,elias_fano
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,default=Path(__file__).resolve().parents[3]/'.research-work/bible-compression/reader-viewer/kjv');p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
b=(a.data/'container.bin').read_bytes();idx=(a.data/'search.bin').read_bytes();books=json.loads((a.data/'source.json').read_text());chapters=[c for book in books for c in book['chapters']];m,nt,ls,ms,nc,raw,ng,maxbits=struct.unpack_from('>8I',b,8);mo=64+m+ls;model=b[mo:mo+ms];ordered=struct.unpack_from('>'+str(nt+ng)+'H',model,4+8*maxbits);codes={}
for n in range(1,maxbits+1):
 first,start,count=struct.unpack_from('>IHH',model,4+8*(n-1))
 for k in range(count):codes[ordered[start+k]]=(first+k,n)
grammar_offset=mo+ms;rules=[struct.unpack_from('>HH',b,grammar_offset+4*i)for i in range(ng)];rec=grammar_offset+4*ng;payload=rec+16*nc;nw=struct.unpack_from('>H',idx,8)[0];mapping=idx[20+5*(nw+1):];normal=[]
for i in range(nt):
 bit=14*i;v=int.from_bytes(mapping[bit//8:bit//8+3].ljust(3,b'\0'),'big');normal.append((v>>(10-(bit&7)))&16383)
word=re.compile(r"[a-z]+(?:'[a-z]+)*");names=sorted({w for ch in chapters for v in ch for w in word.findall(v.lower())});assert len(names)==nw
post=defaultdict(set);vid=0;verse_ch=[]
for ci,ch in enumerate(chapters):
 for vi,v in enumerate(ch):
  for w in set(word.findall(v.lower())):post[w].add(vid)
  verse_ch.append(ci);vid+=1
matching={i for i,w in enumerate(names)if w.startswith('god')};contains=[v in matching for v in normal];hitcount=[int(v in matching)for v in normal]
for l,r in rules:contains.append(contains[l]or contains[r]);hitcount.append(hitcount[l]+hitcount[r])
candidates={ci for ci,ch in enumerate(chapters)if any(any(w.startswith('god')for w in word.findall(v.lower()))for v in ch)};lengths=Counter();counts=Counter();clear_counts=Counter();anchors=0
for ci in range(nc):
 off,size,count,_=struct.unpack_from('>4I',b,rec+16*ci);seq=unpack(b[payload+off:payload+off+size],codes,count)
 if ci not in candidates:continue
 lengths.update(codes[s][1]for s in seq)
 for clear,dest in [(False,counts),(True,clear_counts)]:
  state=0
  for s in seq:
   dest['huffman_symbols']+=1;stack=[s]
   while stack:
    t=stack.pop();dest['nodes']+=1
    if t>=nt:
     if not state and not contains[t]:dest['pruned_rules']+=1;continue
     dest['expanded_rules']+=1;l,r=rules[t-nt];stack.extend([r,l]);continue
    dest['terminals']+=1;v=normal[t]
    if v==nw:dest['newlines']+=1;state=0
    elif v!=nw+1:
     dest['word_tests']+=1;state=int(v in matching)
     if state:dest['hits']+=1
     if clear:state=0
U=vid;allids=set(range(U))
def cost(xs):
 xs=sorted(xs);comp=sorted(allids-set(xs));bm=sum(1<<x for x in xs).to_bytes((U+7)//8,'little');return 1+min(map(len,[delta(xs),elias_fano(xs,U),bm,delta(comp),elias_fano(comp,U)]))
full_verse_body=sum(cost(post[w])for w in names);god_verses=set().union(*(post[w]for w in names if w.startswith('god')));god_payload=sum(cost(post[w])for w in names if w.startswith('god'));anchor4=4*vid+2*(nc+1);blocks={g:len({(verse_ch[x],sum(len(c)for c in chapters[:verse_ch[x]])+(x-sum(len(c)for c in chapters[:verse_ch[x]]))//g*g)for x in god_verses})for g in[1,4,8]}
r=dict(candidate_chapters=len(candidates),work=dict(counts),clear_complete_state_work=dict(clear_counts),huffman_code_length_counts=dict(sorted(lengths.items())),fast_coverage={n:sum(c for l,c in lengths.items()if l<=n)/sum(lengths.values())for n in [8,10,12]},grammar_rules=ng,rules_containing_god=sum(contains[nt:]),max_god_hits_in_rule=max(hitcount[nt:]),verses=vid,god_matching_verses=len(god_verses),god_prefix_words=[w for w in names if w.startswith('god')],verse_index_body_bytes=full_verse_body,verse_index_estimated_bytes=20+5*(nw+1)+(14*nt+7)//8+full_verse_body,all_verse_restart_bytes=anchor4,god_sparse_verse_posting_bytes=god_payload,god_blocks=blocks,note='Verse-posting estimate uses full 31,102-verse universe, same hybrid choices; uses 5-byte records because body exceeds 18-bit offsets. Restart record budget is 24-bit chapter-relative bit offset plus 8-bit grammar skip, per prior validated verse restart format. No device timings.')
(a.output/'results.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))

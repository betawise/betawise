#!/usr/bin/env python3
"""Host-only exact KMP with query-specific phrase-grammar pruning.

When KMP is at state zero, a grammar subtree lacking the query's first word
cannot contain a match. Skip it using static word/newline/trailing-word counts.
"""
import argparse,json,re,struct,time
from pathlib import Path
from compare_translations import TOKEN
from search_space import dense_decode,WORD,QUERIES

def main():
 ap=argparse.ArgumentParser(description=__doc__);root=Path(__file__).resolve().parents[3];ap.add_argument('experiment',type=Path);ap.add_argument('--data',type=Path,default=root/'.research-work/bible-compression/reader/kjv');a=ap.parse_args()
 books=json.loads((a.data/'source.json').read_bytes());chapters=[c for b in books for c in b['chapters']];blocks=[('\n'.join(c)+'\n').encode()for c in chapters];words=sorted({t for b in blocks for t in TOKEN.findall(b.decode())});nt=len(words)
 names=sorted({w for b in blocks for w in WORD.findall(b.lower())});ids={w:i for i,w in enumerate(names)};normal=[65534 if w=='\n' else ids.get(w.lstrip(' ').lower().encode(),65535)for w in words]
 resource=(a.experiment/'phrase-dense-s128.resource').read_bytes();magic,m,ls,s,nr,ng,nc,np=struct.unpack_from('>8s7I',resource);assert magic==b'DENSEX01'
 offset=64+m+ls;rank=struct.unpack_from('>'+str(nr)+'H',resource,offset);offset+=2*nr;rules=[struct.unpack_from('>HH',resource,offset+4*i)for i in range(ng)];offset+=4*ng;payload=offset+16*nc;sequences=[]
 for ci in range(nc):
  pos,n,count,raw=struct.unpack_from('>4I',resource,offset+16*ci);seq=[rank[i]for i in dense_decode(resource[payload+pos:payload+pos+n],s)];assert len(seq)==count;sequences.append(seq)
 summaries=[(0,1,0)if n==65534 else(0,0,0)if n==65535 else(1,0,1)for n in normal]
 for left,right in rules:
  lw,ll,lt=summaries[left];rw,rl,rt=summaries[right];summaries.append((lw+rw,ll+rl,rt if rl else lt+rw))
 maximum=max(max(x)for x in summaries[nt:]);width=1 if maximum<256 else 2
 summary_blob=b''.join(v.to_bytes(width,'big')for entry in summaries[nt:]for v in entry);(a.experiment/'grammar-scan-summaries.bin').write_bytes(summary_blob)
 results=[]
 for query in QUERIES:
  queryids=[ids.get(w,65533)for w in WORD.findall(query.lower().encode())];prefix=[0]*len(queryids)
  for j in range(1,len(queryids)):
   k=prefix[j-1]
   while k and queryids[j]!=queryids[k]:k=prefix[k-1]
   if queryids[j]==queryids[k]:k+=1
   prefix[j]=k
  contains=[x==queryids[0]for x in normal]
  for l,r in rules:contains.append(contains[l]or contains[r])
  hits=[];terminals=nodes=skipped=0;t=time.perf_counter()
  if 65533 not in queryids:
   for ci,seq in enumerate(sequences):
    matched=0;verse=1;ordinal=0
    for symbol in seq:
     stack=[symbol]
     while stack:
      x=stack.pop();nodes+=1
      if x>=nt and not matched and not contains[x]:
       nw,nl,tail=summaries[x];verse+=nl;ordinal=tail if nl else ordinal+nw;skipped+=1;continue
      if x>=nt:l,r=rules[x-nt];stack.extend([r,l]);continue
      terminals+=1;word=normal[x]
      if word==65534:verse+=1;ordinal=matched=0;continue
      if word==65535:continue
      ordinal+=1
      while matched and word!=queryids[matched]:matched=prefix[matched-1]
      if word==queryids[matched]:matched+=1
      if matched==len(queryids):hits.append((ci,verse,ordinal-len(queryids)));matched=prefix[matched-1]
  elapsed=time.perf_counter()-t;expected=[]
  for ci,ch in enumerate(chapters):
   for vi,v in enumerate(ch,1):
    tokens=WORD.findall(v.lower().encode());qw=WORD.findall(query.lower().encode());expected.extend((ci,vi,j)for j in range(len(tokens))if tokens[j:j+len(qw)]==qw)
  assert hits==expected,(query,hits[:5],expected[:5]);results.append(dict(query=query,occurrences=len(hits),exact=True,visited_nodes=nodes,visited_terminals=terminals,pruned_subtrees=skipped,python_host_scan_seconds=elapsed));print(query,terminals,flush=True)
 report=dict(all_occurrences_exact=True,queries=results,grammar_rules=ng,summary_bytes=len(summary_blob),summary_field_bytes=width,max_summary_field=maximum,query_grammar_bitmap_bytes=(ng+7)//8,baseline_terminal_leaves=sum(len(TOKEN.findall(b.decode()))for b in blocks),top_level_symbols=sum(map(len,sequences)),note='All top-level Huffman symbols still require decoding. Python scan timings exclude bit decoding and are not Neo timings. Query bitmap can be built bottom-up with no per-terminal bitmap: compare terminal IDs through the existing normalization map.')
 (a.experiment/'grammar-pruning-results.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Measure selective concordance postings; omitted known words filter no chapters."""
from pathlib import Path
import collections,hashlib,json,re,shutil,struct
root=Path(__file__).resolve().parents[3];base=root/'.research-work/bible-compression';data=base/'device-comparison/huffman-prune';old=(data/'search.bin').read_bytes();magic,nw,nt,group,np=struct.unpack_from('>8sHHII',old);assert magic==b'IDXEXP02'and group==1
books=json.loads((data/'source.json').read_bytes());chapters=[c for b in books for c in b['chapters']];word=re.compile(r"[a-z]+(?:'[a-z]+)*");freq=collections.Counter();post=collections.defaultdict(set)
for ci,ch in enumerate(chapters):
 for verse in ch:
  tokens=word.findall(verse.lower());freq.update(tokens)
  for w in tokens:post[w].add(ci)
names=sorted(post);assert len(names)==nw;mapping_start=20+4*(nw+1);mapping=old[mapping_start:mapping_start+(14*nt+7)//8];payload=old[mapping_start+len(mapping):];records=list(struct.unpack_from('>'+str(nw+1)+'I',old,20));stop=set('the a an and or of to in is it that for with as on be was were are by at not but from his he i you they them'.split());common=[w for w,_ in sorted(post.items(),key=lambda x:-len(x[1]))];top=[w for w,_ in freq.most_common()if w not in stop]
policies={'full':set(names),'omit-stopwords':set(names)-stop,'omit-128-most-chapters':set(names)-set(common[:128]),'frequency-at-least-5':{w for w in names if freq[w]>=5 and w not in stop},'top-2000-not-stopwords':set(top[:2000])};reports=[];queries=['the','the earth','Jesus Jesus','believe','God','Jesus','Abraham','Melchizedek','charity','forgiveness','in the beginning']
for label,keep in policies.items():
 body=bytearray();outrecords=[]
 for i,w in enumerate(names):
  off=records[i]&262143;end=records[i+1]&262143;outrecords.append((records[i]&~262143)|len(body));body+=payload[off:end]if w in keep else b'\x05'
 outrecords.append(len(body));blob=struct.pack('>8sHHII',magic,nw,nt,1,len(body))+struct.pack('>'+str(nw+1)+'I',*outrecords)+mapping+body
 checks=[]
 for query in queries:
  ws=word.findall(query.lower());exact=set.intersection(*[post[w]for w in ws]);candidate=set.intersection(*[post[w]if w in keep else set(range(len(chapters)))for w in ws]);assert exact<=candidate
  checks.append(dict(query=query,candidate_chapters=len(candidate),full_index_chapters=len(exact),indexed_terms=[w for w in ws if w in keep]))
 reports.append(dict(policy=label,bytes=len(blob),indexed_words=len(keep),known_words=nw,queries=checks))
 if label=='frequency-at-least-5':
  out=base/'device-comparison/huffman-prune-partial';out.mkdir(exist_ok=True)
  for n in ['container.bin','source.json','verses.bin','pruning.bin']:shutil.copyfile(data/n,out/n)
  (out/'search.bin').write_bytes(blob);r=json.loads((data/'results.json').read_text());r.update(search_bytes=len(blob),partial_policy=label);(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
(base/'device-comparison/partial-index-results.json').write_text(json.dumps(reports,indent=2)+'\n');print(json.dumps(reports,indent=2))

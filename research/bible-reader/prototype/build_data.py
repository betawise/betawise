#!/usr/bin/env python3
"""Build a translation-specific ASCII phrase-Huffman Bible and chapter search filter."""
import argparse,hashlib,json,re,struct,sys
from collections import Counter,defaultdict
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'research/bible-reader'))
from build_huffman import huffman
from measure import unpack
from context_models import decode_letter_dictionary
from compare_translations import TOKEN,front_dictionary,packed_json
from device_ascii import convert
from packed_index import build_index as packed_index,grammar_summaries

def varint(n):
 out=bytearray()
 while n>=128:out.append((n&127)|128);n>>=7
 out.append(n);return out

def corpus(repo,version):
 books=json.loads((repo/'data/books.json').read_bytes())
 counts={};parts=defaultdict(list)
 for row in json.loads((repo/'data/kjv/kjv.json').read_bytes()):
  if 'h'not in row:
   _,b,c,v=row['r'].split(':');k=(b,int(c));counts[k]=max(counts.get(k,0),int(v))
 source=repo/'data'/version/(version+'.json')
 for row in json.loads(source.read_bytes()):
  if 'h'in row:continue
  _,b,c,v=row['r'].split(':');k=(b,int(c));v=int(v)
  assert k in counts and 0<v<256
  counts[k]=max(counts[k],v)
  plain=re.sub(r'\*[a-z]+','',row['t']);assert '*'not in plain
  plain=convert(plain);assert all(32<=ord(c)<=126 for c in plain)
  parts[k+(v,)].append(plain)
 result=[dict(name=b['book'],chapters=[[' '.join(parts[(b['book'],c,v)]) for v in range(1,counts[(b['book'],c)]+1)]for c in range(1,b['numChapters']+1)])for b in books]
 return result,source

def verse_bloom_index(blocks,words,image):
 names=sorted({w for raw in blocks for w in re.findall(rb"[A-Za-z]+(?:'[A-Za-z]+)*",raw.lower())})
 ids={w:i for i,w in enumerate(names)};canonical={};mapping=[]
 for terminal,word in enumerate(words):
  raw=word.encode('ascii');normal=raw.lstrip(b' ').lower()
  if raw==b'\n':mapping.append(65534)
  elif normal in ids:mapping.append(ids[normal]);canonical.setdefault(normal,terminal)
  else:mapping.append(65535)
 m,nt,ls,ms,nc,raw_bytes,ng,maxbits=struct.unpack_from('>8I',image,8)
 model=image[64+m+ls:64+m+ls+ms];alphabet=struct.unpack_from('>H',model,2)[0]
 ordered=struct.unpack_from('>'+str(alphabet)+'H',model,4+8*maxbits);codes={}
 for n in range(1,maxbits+1):
  first,start,count=struct.unpack_from('>IHH',model,4+8*(n-1))
  for k in range(count):codes[ordered[start+k]]=(first+k,n)
 grammar_start=64+m+ls+ms
 rules=[struct.unpack_from('>HH',image,grammar_start+4*i)for i in range(ng)]
 index_start=grammar_start+4*ng;payload_start=index_start+16*nc
 records=bytearray();chapter_offsets=[0];max_skip=0
 for chapter,raw in enumerate(blocks):
  offset,size,count,raw_len=struct.unpack_from('>4I',image,index_start+16*chapter)
  sequence=unpack(image[payload_start+offset:payload_start+offset+size],codes,count)
  bit=0;begin=None;bloom=0;restored=[];verses=0
  for symbol in sequence:
   stack=[symbol];leaves=[]
   while stack:
    terminal=stack.pop()
    if terminal<nt:leaves.append(terminal)
    else:a,b=rules[terminal-nt];stack.extend([b,a])
   for skip,terminal in enumerate(leaves):
    restored.append(words[terminal])
    if begin is None:begin=(bit,skip);max_skip=max(max_skip,skip)
    word=mapping[terminal]
    if word==65534:
     assert begin[0]<1<<24 and begin[1]<256
     records.extend(struct.pack('>II',bloom&0xffffffff,bloom>>32)+begin[0].to_bytes(3,'big')+bytes([begin[1]]));verses+=1;begin=None;bloom=0
    elif word!=65535:bloom|=1<<((word^(word>>6))&63)
   bit+=codes[symbol][1]
  assert ''.join(restored).encode('ascii')==raw and begin is None and verses==raw.count(b'\n')
  chapter_offsets.append(chapter_offsets[-1]+verses)
 assert chapter_offsets[-1]<65536 and len(records)==12*chapter_offsets[-1]
 header=struct.pack('>8sIII',b'BIBSRCH3',len(names),len(words),chapter_offsets[-1])
 canon=struct.pack('>'+str(len(names))+'H',*(canonical[w]for w in names))
 index=header+canon+struct.pack('>'+str(len(mapping))+'H',*mapping)+struct.pack('>1190H',*chapter_offsets)+records
 return index,len(names)

def search_index(blocks,words):
 postings=defaultdict(set)
 for chapter,raw in enumerate(blocks):
  for word in re.findall(rb"[A-Za-z]+(?:'[A-Za-z]+)*",raw.lower()):postings[word].add(chapter)
 names=sorted(postings);ids={w:i for i,w in enumerate(names)};canonical={};mapping=[]
 for terminal,word in enumerate(words):
  raw=word.encode('ascii');normal=raw.lstrip(b' ').lower()
  if raw==b'\n':mapping.append(65534)
  elif normal in ids:mapping.append(ids[normal]);canonical.setdefault(normal,terminal)
  else:mapping.append(65535)
 payload=bytearray();records=bytearray()
 for word in names:
  assert len(payload)<1<<24
  records.extend(struct.pack('>H',canonical[word])+len(payload).to_bytes(3,'big'));last=-1
  for chapter in sorted(postings[word]):payload.extend(varint(chapter-last));last=chapter
 records.extend(bytes(2)+len(payload).to_bytes(3,'big'))
 return struct.pack('>8sIII',b'BIBSRCH2',len(names),len(words),len(payload))+records+struct.pack('>'+str(len(mapping))+'H',*mapping)+payload,len(names)

def hot_dictionary(words,frequencies):
 slots={};strings=bytearray();records=bytearray()
 for terminal in sorted(range(len(words)),key=lambda i:-frequencies[i]):
  slot=(terminal^(terminal>>8))&255
  if slot not in slots:slots[slot]=terminal
 for slot in range(256):
  terminal=slots.get(slot,65535);offset=len(strings)
  if terminal!=65535:strings.extend(words[terminal].encode('ascii')+b'\0')
  records.extend(struct.pack('>HH',terminal,offset))
 return records+strings

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--retrain',action='store_true');ap.add_argument('--search-index',choices=['chapter','verse-bloom','packed-prune'],default='chapter');ap.add_argument('--reuse',action='store_true');ap.add_argument('--version',choices=['kjv','nkjv','esv','niv','nasb','csb'],default='kjv');ap.add_argument('--repo',type=Path,default=HERE/'upstream');ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 a.output.mkdir(parents=True,exist_ok=True)
 builder_hash=hashlib.sha256(b''.join(p.read_bytes()for p in [Path(__file__),HERE.parents[1]/'research/bible-reader/build_huffman.py',HERE.parents[1]/'research/bible-reader/device_ascii.py',HERE.parents[1]/'research/bible-reader/packed_index.py'])).hexdigest()
 source=a.repo/'data'/a.version/(a.version+'.json')
 if a.reuse and not a.retrain and (a.output/'results.json').exists():
  prior=json.loads((a.output/'results.json').read_text())
  if prior.get('search_index_kind')==a.search_index and prior.get('builder_sha256')==builder_hash and prior['source_sha256']==hashlib.sha256(source.read_bytes()).hexdigest() and all((a.output/f).exists() for f in ['container.bin','search.bin','verses.bin','pruning.bin']):return
 books,source=corpus(a.repo,a.version);normalized=packed_json(books)
 prior=json.loads((a.output/'results.json').read_text())if(a.output/'results.json').exists()else{}
 reuse_codec=not a.retrain and prior.get('ascii_sha256')==hashlib.sha256(normalized).hexdigest()and(a.output/'compressed-dictionary/container.bin').exists()
 (a.output/'source.json').write_bytes(normalized)
 blocks=[('\n'.join(c)+'\n').encode('ascii')for b in books for c in b['chapters']]
 meta=[];n=0
 for b in books:meta.append([b['name'],n,len(b['chapters'])]);n+=len(b['chapters'])
 words=sorted({t for b in blocks for t in TOKEN.findall(b.decode())});ids={w:i for i,w in enumerate(words)}
 assert len(words)+2048<65536 and max(map(len,words))<64
 if reuse_codec:
  saved=(a.output/'compressed-dictionary/container.bin').read_bytes();mm,tt,ll=struct.unpack_from('>III',saved,8)
  reuse_codec=tt==len(words)and decode_letter_dictionary(saved[64+mm:64+mm+ll])==front_dictionary(words)
 if not reuse_codec:
  seqs=[[ids[t]for t in TOKEN.findall(b.decode())]for b in blocks];rules=[]
  for _ in range(16):
   pairs=Counter(p for seq in seqs for p in zip(seq,seq[1:]));selected=[p for p,n in pairs.most_common(128)if n>=16];mapping={p:len(words)+len(rules)+i for i,p in enumerate(selected)};rules+=selected;newseq=[]
   for seq in seqs:
    s=[];i=0
    while i<len(seq):
     symbol=mapping.get(tuple(seq[i:i+2]))
     if symbol is None:s.append(seq[i]);i+=1
     else:s.append(symbol);i+=2
    newseq.append(s)
   seqs=newseq
  result=huffman(blocks,meta,words,seqs,rules,a.output/'compressed-dictionary',a.version.upper())
 b=(a.output/'compressed-dictionary/container.bin').read_bytes();m,_,old=struct.unpack_from('>III',b,8);lex=front_dictionary(words);h=bytearray(b[:64]);h[:8]=b'KJVHUF02';struct.pack_into('>I',h,16,len(lex));image=bytes(h)+b[64:64+m]+lex+b[64+m+old:]
 frequencies=Counter(t for raw in blocks for t in TOKEN.findall(raw.decode('ascii')))
 hot=hot_dictionary(words,[frequencies[w]for w in words]);h=bytearray(image[:64]);struct.pack_into('>I',h,40,len(image));image=bytes(h)+image[64:]+hot
 (a.output/'container.bin').write_bytes(image)
 search,vocab=verse_bloom_index(blocks,words,image)if a.search_index=='verse-bloom'else packed_index(blocks,words)if a.search_index=='packed-prune'else search_index(blocks,words)
 if search is None:search,vocab=search_index(blocks,words)
 (a.output/'search.bin').write_bytes(search)
 (a.output/'pruning.bin').write_bytes(grammar_summaries(words,image)if a.search_index=='packed-prune'else b'')
 counts=[len(c)for b in books for c in b['chapters']];(a.output/'verses.bin').write_bytes(struct.pack('>'+str(len(counts))+'H',*counts))
 report=dict(search_index_kind=a.search_index,builder_sha256=builder_hash,version=a.version.upper(),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),ascii_sha256=hashlib.sha256((a.output/'source.json').read_bytes()).hexdigest(),sha256=hashlib.sha256(image).hexdigest(),bytes=len(image),search_bytes=len(search),search_index_magic=search[:8].decode('ascii'),pruning_bytes=(a.output/'pruning.bin').stat().st_size,search_words=vocab,hot_dictionary_bytes=len(hot),max_chapter_bytes=max(map(len,blocks)),max_dictionary_word=max(map(len,words)),dictionary_entries=len(words),chapters=len(blocks),verses=sum(counts),mapped_text_bytes=sum(map(len,blocks)))
 (a.output/'results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()

"""Full exact chapter index and fixed-ROM phrase summaries for the Neo reader."""
from collections import defaultdict
import re,struct
WORD=re.compile(rb"[A-Za-z]+(?:'[A-Za-z]+)*")
def delta(values):
 out=bytearray();last=-1
 for value in values:
  n=value-last;last=value
  while n>=128:out.append((n&127)|128);n>>=7
  out.append(n)
 return bytes(out)
def elias_fano(values,universe):
 n=len(values)
 if not n:return b'\0\0\0'
 low=max(0,(universe//n).bit_length()-1);data=bytearray((n*low+(values[-1]>>low)+n+8)//8)
 def setbit(i):data[i//8]|=1<<(i&7)
 for j,value in enumerate(values):
  for k in range(low):
   if value>>k&1:setbit(j*low+k)
  setbit(n*low+(value>>low)+j)
 return struct.pack('>HB',n,low)+data
def pack14(values):
 out=bytearray();acc=bits=0
 for value in values:
  assert 0<=value<16384
  acc=(acc<<14)|value;bits+=14
  while bits>=8:bits-=8;out.append((acc>>bits)&255)
 if bits:out.append((acc<<(8-bits))&255)
 return bytes(out)
def build_index(blocks,words):
 postings=defaultdict(set)
 for chapter,raw in enumerate(blocks):
  for word in WORD.findall(raw.lower()):postings[word].add(chapter)
 names=sorted(postings);ids={w:i for i,w in enumerate(names)};nw=len(names);nt=len(words)
 if nw+2>=16384 or nt>=16384:return None,nw
 canonical={};mapping=[]
 for terminal,word in enumerate(words):
  raw=word.encode('ascii');normal=raw.lstrip(b' ').lower()
  if raw==b'\n':mapping.append(nw)
  elif normal in ids:mapping.append(ids[normal]);canonical.setdefault(normal,terminal)
  else:mapping.append(nw+1)
 universe=len(blocks);allchapters=set(range(universe));body=bytearray();records=[]
 for name in names:
  xs=sorted(postings[name]);complement=sorted(allchapters-postings[name]);bitmap=sum(1<<x for x in xs).to_bytes((universe+7)//8,'little')
  choices=[(0,delta(xs)),(1,elias_fano(xs,universe)),(2,bitmap),(3,delta(complement)),(4,elias_fano(complement,universe))];mode,data=min(choices,key=lambda x:len(x[1]))
  records.append((canonical[name]<<18)|len(body));body+=bytes([mode])+data
 if len(body)>=1<<18:return None,nw
 records.append(len(body));header=struct.pack('>8sHHII',b'IDXEXP02',nw,nt,1,len(body))
 return header+struct.pack('>'+str(nw+1)+'I',*records)+pack14(mapping)+body,nw
def grammar_summaries(words,image):
 m,nt,ls,ms,nc,raw,ng,maxbits=struct.unpack_from('>8I',image,8);assert nt==len(words)
 summaries=[(0,1,0)if w=='\n'else(1,0,1)if WORD.fullmatch(w.lstrip(' ').encode('ascii'))else(0,0,0)for w in words]
 offset=64+m+ls+ms
 for i in range(ng):
  a,b=struct.unpack_from('>HH',image,offset+4*i);assert a<nt+i and b<nt+i
  aw,al,at=summaries[a];bw,bl,bt=summaries[b];summary=(aw+bw,al+bl,bt if bl else at+bw);assert max(summary)<256;summaries.append(summary)
 return bytes(v for entry in summaries[nt:]for v in entry)

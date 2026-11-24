#!/usr/bin/env python3
"""Independent token/matching oracle for verse, phrase and 20-word search modes."""
from prototype_support import prototype_app, prototype_test
from pathlib import Path
import argparse,json,re,subprocess,sys,random
ROOT=Path(__file__).resolve().parents[3];APP=prototype_app();sys.path.insert(0,str(APP));from search_options import select
WORD=re.compile(r"[a-z]+(?:'[a-z]+)*")
def covering(events,n):
 reach={0}
 for _,_,_,mask in events:
  reach|={bits|(1<<i)for bits in list(reach)for i in range(n)if mask&(1<<i)and not bits&(1<<i)}
 return (1<<n)-1 in reach
def unordered(events,n,mode):
 pending=[];out=[];last_verse=0;suppressed=False
 for pos,v,w,mask in events:
  if mode==0 and v!=last_verse:pending=[];suppressed=False
  last_verse=v
  if suppressed:continue
  if mode==2:pending=[e for e in pending if pos-e[0]<20]
  if mask:pending.append((pos,v,w,mask))
  if mask and covering(pending,n):
   while len(pending)>1 and covering(pending[1:],n):pending.pop(0)
   out.append((pending[0][1],pending[0][2]));pending=[];suppressed=mode==0
 return out
def oracle(chapters,query,mode):
 qs=[(m.group().lower(),query[m.end():m.end()+1]=='*')for m in re.finditer(r"[A-Za-z]+(?:'[A-Za-z]+)*",query)];out=[]
 for ci,ch in enumerate(chapters):
  events=[];pos=0
  for vi,v in enumerate(ch,1):
   words=WORD.findall(v.lower())
   if mode==1:
    out.extend((ci,vi,j)for j in range(len(words)-len(qs)+1)if all(words[j+k].startswith(q)if star else words[j+k]==q for k,(q,star)in enumerate(qs)))
   else:
    for wi,w in enumerate(words):
     mask=sum(1<<k for k,(q,star)in enumerate(qs)if(w.startswith(q)if star else w==q));events.append((pos,vi,wi,mask));pos+=1
  if mode!=1:out.extend((ci,v,w)for v,w in unordered(events,len(qs),mode))
 return out

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);data=ROOT/'.research-work/bible-compression/reader-viewer/kjv';chapters=[c for b in json.loads((data/'source.json').read_text())for c in b['chapters']]
 src='''#include "Search.h"
#include <stdio.h>
#include <stdlib.h>
static unsigned char*load(char*p,unsigned*n){FILE*f=fopen(p,"rb");fseek(f,0,2);*n=ftell(f);rewind(f);unsigned char*b=malloc(*n+1);fread(b,1,*n,f);fclose(f);return b;}
int main(int c,char**v){unsigned n,m;unsigned char*b=load(v[1],&n),*i=load(v[2],&m);BibleSearch s;int r;if(!SearchBegin(&s,b,n,i,m,v[3],atoi(v[4])))return 2;
if(c>5)SearchFrom(&s,atoi(v[5]),atoi(v[6]),atoi(v[7]),atoi(v[8]),atoi(v[9]));
while((r=SearchStep(&s,7))!=-1){if(r==-2)return 3;if(r==1){printf("%u %u %u\\n",s.chapter,s.verse,s.hit_word);if(c>5)break;}}return 0;}
'''
 src+='\nconst unsigned char BibleGrammarSummary[]={'+','.join(map(str,(data/'pruning.bin').read_bytes()))+'};\n';(a.output/'check.c').write_text(src)
 queries=['God','god*','believ*','Methus*','t d','t* d*','faith works','works faith','kingdom God','in the beginning','Jesus Jesus','God God','god* god','be* bel*',"LORD's",'Jesus Christ','the the','a a','holy spirit','fear not','zzzzunknown','show* show','maher shalal hash baz']
 expected={(q,m):oracle(chapters,q,m)for q in queries for m in range(3)};reports=[]
 for option in ['full','compact','scan']:
  exe=a.output/('check-'+option);subprocess.run(['cc','-O2','-DBIBLE_HUFFMAN=1','-DBIBLE_RAW_ONLY=1','-DBIBLE_PRUNE=1','-I'+str(APP),str(APP/'Search.c'),str(APP/'HuffmanDecoder.c'),str(a.output/'check.c'),'-o',str(exe)],check=True);idx=a.output/(option+'.bin');idx.write_bytes(select(data,option));count=0
  for(q,mode),want in expected.items():
   args=[str(exe),str(data/'container.bin'),str(idx),q,str(mode)];got=[tuple(map(int,l.split()))for l in subprocess.check_output(args,text=True).splitlines()];assert got==want,(option,q,mode,len(got),len(want),next(((i,x,y)for i,(x,y)in enumerate(zip(got,want))if x!=y),None));count+=1
   if q in ['God','faith works','kingdom God','Jesus Jesus','god* god','be* bel*']:
    for origin in [(0,1,0),(596,80,0),(999,16,0),(1188,22,30)]:
     for direction in [-1,1]:
      for inclusive in [0,1]:
       xs=[x for x in want if(x>=origin if inclusive else x>origin)]if direction>0 else[x for x in want if(x<=origin if inclusive else x<origin)];xs=xs[:1]if direction>0 else xs[-1:]
       got=[tuple(map(int,l.split()))for l in subprocess.check_output(args+list(map(str,(*origin,direction,inclusive))),text=True).splitlines()];assert got==xs,(option,q,mode,origin,direction,inclusive,got,xs);count+=1
  reports.append(dict(index=option,cases=count));print(option,'passed',count,flush=True)
 # Invalid wildcard placement must not silently turn into a different query.
 for q in ['*God','go*d','God**','*','faith * works']:
  assert subprocess.run([str(exe),str(data/'container.bin'),str(idx),q,'0'],stdout=subprocess.DEVNULL).returncode==2,q
 # Match-state property tests use arbitrary overlapping acceptance sets, not just
 # vocabulary-derived nested prefix intervals. C implementation versus full DP.
 unit='''#include "Search.h"
#include <string.h>
#include <stdio.h>
#include "SearchMatch.h"
int main(){BibleSearch s;unsigned n,m,mask,v,w;memset(&s,0,sizeof(s));scanf("%u %u",&n,&m);s.phrase_length=n;s.match_mode=m;while(scanf("%u %u %u",&mask,&v,&w)==3){if(m==0&&s.verse!=v)match_reset(&s);s.verse=v;s.word_count=w;if(match_word(&s,mask))printf("%u %u\\n",s.verse,s.hit_word);}return 0;}
'''
 (a.output/'unit.c').write_text(unit);subprocess.run(['cc','-O2','-DBIBLE_HUFFMAN=1','-DBIBLE_RAW_ONLY=1','-I'+str(APP),str(a.output/'unit.c'),'-o',str(a.output/'unit')],check=True);rng=random.Random(0xA1B1);units=0
 for n in range(1,9):
  for mode in [0,2]:
   for _ in range(20):
    es=[(i,1+i//17,i%17,rng.randrange(1<<n))for i in range(100)];want=unordered(es,n,mode);text=f'{n} {mode}\n'+''.join(f'{mask} {v} {w}\n'for _,v,w,mask in es);got=[tuple(map(int,l.split()))for l in subprocess.check_output([str(a.output/'unit')],input=text,text=True).splitlines()];assert got==want,(n,mode,got,want);units+=1
 (a.output/'results.json').write_text(json.dumps(dict(status='passed',results=reports,matcher_property_cases=units,invalid_queries=5),indent=2)+'\n')
if __name__=='__main__':main()

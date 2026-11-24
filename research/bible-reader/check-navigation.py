#!/usr/bin/env python3
"""Validate directional C searches against independent source-token occurrences."""
from prototype_support import prototype_app, prototype_test
from pathlib import Path
import argparse,json,re,subprocess,sys
from navigation_cases import cases
ROOT=Path(__file__).resolve().parents[3];APP=prototype_app();sys.path.insert(0,str(APP));from search_options import select
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);data=ROOT/'.research-work/bible-compression/reader-viewer/kjv';books=json.loads((data/'source.json').read_text());chs=[c for b in books for c in b['chapters']];rows=cases(books)
queries=['God','godl',"God's",'God said','God God','believ','Methus','in the beg','Jesus Jesus','zzunknown','be bel','a a'];hits={}
for q in queries:
 qw=re.findall(r"[a-z]+(?:'[a-z]+)*",q.lower());hs=[]
 for ci,ch in enumerate(chs):
  for vi,v in enumerate(ch,1):
   ws=re.findall(r"[a-z]+(?:'[a-z]+)*",v.lower());hs.extend((ci,vi,j)for j in range(len(ws)-len(qw)+1)if all(ws[j+k].startswith(w)for k,w in enumerate(qw)))
 hits[q]=hs
src='''#include "Search.h"
#include <stdio.h>
#include <stdlib.h>
static unsigned char*load(char*p,unsigned*n){FILE*f=fopen(p,"rb");fseek(f,0,2);*n=ftell(f);rewind(f);unsigned char*b=malloc(*n+1);fread(b,1,*n,f);fclose(f);return b;}
int main(int c,char**v){unsigned n,m;unsigned char*b=load(v[1],&n),*i=load(v[2],&m);BibleSearch s;int r,count=atoi(v[9]);if(!SearchStartMode(&s,b,n,i,m,v[3],1))return 2;
while(count--){SearchFrom(&s,atoi(v[4]),atoi(v[5]),atoi(v[6]),atoi(v[7]),atoi(v[8]));do{r=SearchStep(&s,7);}while(!r);if(r==-2)return 3;if(r==-1){puts("none");break;}printf("%u %u %u\\n",s.chapter,s.verse,s.hit_word);static char aa[20],bb[20],dd[20];sprintf(aa,"%u",s.chapter);sprintf(bb,"%u",s.verse);sprintf(dd,"%u",s.hit_word);v[4]=aa;v[5]=bb;v[6]=dd;}
return 0;}
'''
src+='\nconst unsigned char BibleGrammarSummary[]={'+','.join(map(str,(data/'pruning.bin').read_bytes()))+'};\n';(a.output/'check.c').write_text(src);reports=[]
for option in ['full','compact','scan','none']:
 exe=a.output/('check-'+option);subprocess.run(['cc','-O2','-DBIBLE_HUFFMAN=1','-DBIBLE_RAW_ONLY=1',f'-DBIBLE_PRUNE={int(option!="none")}',f'-DBIBLE_NOINDEX={int(option=="none")}','-I'+str(APP),str(APP/'Search.c'),str(APP/'HuffmanDecoder.c'),str(a.output/'check.c'),'-o',str(exe)],check=True);idx=a.output/(option+'.bin');idx.write_bytes(select(data,option));count=0
 tests=rows+[dict(query=q,chapter=c,verse=v,word=w,direction=d)for q in queries for c,v,w in [(0,1,0),(1188,22,30)]for d in [-1,1]]
 # Resume exactly at a hit, verify strict/inclusive semantics and continuation.
 tests += [dict(query=q,chapter=h[0],verse=h[1],word=h[2],direction=d)for q in ['God','a a','believ']for h in hits[q][2:3]for d in [-1,1]]
 for row in tests:
  for inclusive in [0,1]:
   origin=(row['chapter'],row['verse'],row['word']);d=row['direction'];expected=[]
   for k in range(3):
    xs=[h for h in hits[row['query']]if(h>=origin if inclusive and k==0 else h>origin)]if d>0 else[h for h in hits[row['query']]if(h<=origin if inclusive and k==0 else h<origin)]
    if not xs:expected.append('none');break
    origin=xs[0]if d>0 else xs[-1];expected.append(' '.join(map(str,origin)))
   got=subprocess.check_output([str(exe),str(data/'container.bin'),str(idx),row['query'],str(row['chapter']),str(row['verse']),str(row['word']),str(d),str(inclusive),'3'],text=True).splitlines();assert got==expected,(option,row,inclusive,got,expected);count+=1
 reports.append(dict(index=option,cases=count));print(option,'passed',count,flush=True)
(a.output/'results.json').write_text(json.dumps(dict(status='passed',results=reports),indent=2)+'\n')

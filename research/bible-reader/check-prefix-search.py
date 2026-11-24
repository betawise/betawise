#!/usr/bin/env python3
"""Compare prefix and whole-word C matcher with every independent source hit."""
from prototype_support import prototype_app, prototype_test
from pathlib import Path
import argparse,subprocess,json,re,sys,hashlib
ROOT=Path(__file__).resolve().parents[3];APP=prototype_app()
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--clear-complete',action='store_true');p.add_argument('--verse-boost',type=Path);p.add_argument('--data',type=Path,default=ROOT/'.research-work/bible-compression/reader-viewer/kjv');p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(APP));from search_options import select
queries=['godl','gods',"God's",'God said','God God','Methus','meth','believ','believe','God','love','th','in the beg','Jesus Jesus','a a','be bel','in i','I am that I am',"LORD's","Jesus'",'zzzzunknown']
source='''#include "Search.h"
#include <stdio.h>
#include <stdlib.h>
static unsigned char*load(char*p,unsigned*n){FILE*f=fopen(p,"rb");if(!f)exit(4);fseek(f,0,2);*n=ftell(f);rewind(f);unsigned char*b=malloc(*n);fread(b,1,*n,f);fclose(f);return b;}
int main(int c,char**v){unsigned n,m;unsigned char*b=load(v[1],&n),*i=load(v[2],&m);BibleSearch s;if(!SearchStartMode(&s,b,n,i,m,v[3],atoi(v[4])))return 2;int r;while((r=SearchStep(&s,7))!=-1){if(r==-2)return 3;if(r==1)printf("%u %u %u\\n",s.chapter,s.verse,s.hit_word);}return 0;}
'''
if a.verse_boost:source+='\nconst unsigned char BibleVerseBoost[]={'+','.join(map(str,a.verse_boost.read_bytes()))+'};\nasm(".global BibleVerseBoostEnd\\n.set BibleVerseBoostEnd,BibleVerseBoost+'+str(a.verse_boost.stat().st_size)+'");\n'
source+='\nconst unsigned char BibleGrammarSummary[]={'+','.join(map(str,(a.data/'pruning.bin').read_bytes()))+'};\n'
(a.output/'check.c').write_text(source);exe=a.output/'check';compile_args=(['cc','-O2','-DBIBLE_HUFFMAN=1','-DBIBLE_RAW_ONLY=1','-DBIBLE_DENSE=0','-DBIBLE_PRUNE=1',f'-DBIBLE_VERSE_BOOST={int(bool(a.verse_boost))}',f'-DBIBLE_SEARCH_CLEAR_COMPLETE={int(a.clear_complete)}','-I'+str(APP),str(APP/'Search.c'),str(APP/'HuffmanDecoder.c'),str(a.output/'check.c'),'-o',str(exe)])
subprocess.run(compile_args,check=True)
chapters=[c for b in json.loads((a.data/'source.json').read_text())for c in b['chapters']];tokens=[[re.findall(r"[a-z]+(?:'[a-z]+)*",v.lower())for v in ch]for ch in chapters];reports=[]
for option in ['full','compact','scan','none']:
 if option=='none':subprocess.run([x.replace('-DBIBLE_PRUNE=1','-DBIBLE_PRUNE=0') for x in compile_args]+['-DBIBLE_NOINDEX=1'],check=True)
 index=a.output/(option+'.bin');index.write_bytes(select(a.data,option))
 for prefix in [0,1]:
  for query in queries:
   qw=re.findall(r"[a-z]+(?:'[a-z]+)*",query.lower());expected=[]
   for ci,ch in enumerate(tokens):
    for vi,v in enumerate(ch,1):
     expected.extend((ci,vi,j)for j in range(len(v)-len(qw)+1)if all(v[j+k].startswith(w)if prefix else v[j+k]==w for k,w in enumerate(qw)))
   data=subprocess.check_output([str(exe),str(a.data/'container.bin'),str(index),query,str(prefix)],text=True);got=[tuple(map(int,l.split()))for l in data.splitlines()];assert got==expected,(option,prefix,query,len(got),len(expected),got[:5],expected[:5])
   reports.append(dict(index=option,prefix=bool(prefix),query=query,hits=len(got),sha256=hashlib.sha256(data.encode()).hexdigest()))
 print(option,'passed',flush=True)
(a.output/'results.json').write_text(json.dumps(dict(status='passed',cases=len(reports),results=reports),indent=2)+'\n')

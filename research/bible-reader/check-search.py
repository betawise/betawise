from prototype_support import prototype_app, prototype_test
from pathlib import Path
import subprocess,json,re
import argparse
root=Path(__file__).resolve().parents[3];app=prototype_app()
ap=argparse.ArgumentParser(description='Verify exact search against independent word/phrase matches across every source verse.')
ap.add_argument('--whole-word',action='store_true');ap.add_argument('--backend',choices=['chapter','bloom'],default='chapter');ap.add_argument('--data',type=Path,default=root/'.research-work/bible-compression/reader/kjv');args=ap.parse_args();data=args.data.resolve()
s='''#include "Search.h"
#include <stdio.h>
#include <stdlib.h>
static unsigned char*load(char*p,unsigned*n){FILE*f=fopen(p,"rb");fseek(f,0,2);*n=ftell(f);rewind(f);unsigned char*b=malloc(*n);fread(b,1,*n,f);fclose(f);return b;}
int main(int c,char**v){unsigned n,m;unsigned char*b=load(v[1],&n),*i=load(v[2],&m);BibleSearch s;if(!SearchStartMode(&s,b,n,i,m,v[3],PREFIX_MATCH))return 2;int r;while((r=SearchStep(&s,7))!=-1){if(r==-2)return 3;if(r==1)printf("%u %u %u\\n",s.chapter,s.verse,s.hit_word);}return 0;}
'''
s=s.replace('PREFIX_MATCH',str(int(not args.whole_word)))
if args.backend=='bloom':s=s.replace('SearchStartMode(&s,b,n,i,m,v[3],'+str(int(not args.whole_word))+')','SearchStart(&s,b,n,i,m,v[3])').replace('Search.h','SearchBloom.h').replace('BibleSearch','BibleBloomSearch').replace('SearchStart','BloomSearchStart').replace('SearchStep','BloomSearchStep')
assert (data/'search.bin').read_bytes()[:8]in ([b'BIBSRCH3']if args.backend=='bloom'else[b'BIBSRCH2',b'BIBSRCH4',b'IDXEXP02',b'PFXLEX01'])
dense=(data/'container.bin').read_bytes()[:8]==b'KJVDNS01';prune=(data/'pruning.bin').exists()and bool((data/'pruning.bin').stat().st_size)
if prune:s+='\nconst unsigned char BibleGrammarSummary[]={'+','.join(map(str,(data/'pruning.bin').read_bytes()))+'};\n'
Path('/tmp/check-bible-search.c').write_text(s);subprocess.run(['cc','-O2','-DBIBLE_HUFFMAN=1','-DBIBLE_RAW_ONLY=1',f'-DBIBLE_DENSE={int(dense)}',f'-DBIBLE_PRUNE={int(prune)}','-I'+str(app),'-I'+str(Path(__file__).resolve().parent),str(app/'Search.c')if args.backend=='chapter'else str(Path(__file__).resolve().parent/'SearchBloom.c'),str(app/'HuffmanDecoder.c'),'/tmp/check-bible-search.c','-o','/tmp/check-bible-search'],check=True)
books=json.loads((data/'source.json').read_bytes());chapters=[c for b in books for c in b['chapters']];report=[]
for query in ['God','god','the earth','in the beginning','Jesus','Jesus Jesus','believe','believed','zzzzunknown','love love','verily verily','I am that I am','a a','LORD\'s','Jesus\'']:
 words=re.findall(r"[a-z]+(?:'[a-z]+)*",query.lower());expected=[]
 for ci,ch in enumerate(chapters):
  for vi,verse in enumerate(ch,1):
   tokens=re.findall(r"[a-z]+(?:'[a-z]+)*",verse.lower())
   for j in range(len(tokens)):
    if len(tokens[j:j+len(words)])==len(words)and all(tokens[j+k]==w if args.whole_word or args.backend=="bloom"else tokens[j+k].startswith(w)for k,w in enumerate(words)):expected.append((ci,vi,j))
 out=subprocess.check_output(['/tmp/check-bible-search',str(data/'container.bin'),str(data/'search.bin'),query],text=True);got=[tuple(map(int,l.split()))for l in out.splitlines()];assert got==expected,(query,len(got),len(expected),got[:5],expected[:5]);report.append(dict(query=query,occurrences=len(got),exact=True))
print(json.dumps(report));(data/'search-tests.json').write_text(json.dumps(report,indent=2))

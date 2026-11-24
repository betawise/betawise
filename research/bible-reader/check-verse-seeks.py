#!/usr/bin/env python3
"""Verify every compressed verse restart against the mapped source text."""
from prototype_support import prototype_app, prototype_test
from pathlib import Path
import argparse,json,struct,subprocess,tempfile
root=Path(__file__).resolve().parents[3];app=prototype_app()
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--data',type=Path,default=root/'.research-work/bible-compression/verse-bloom-experiment');a=ap.parse_args();data=a.data.resolve()
assert(data/'search.bin').read_bytes()[:8]==b'BIBSRCH3'
source=r'''#include "Decoder.h"
#include <stdio.h>
#include <stdlib.h>
static unsigned b16(unsigned char*p){return p[0]*256u+p[1];}
static unsigned b24(unsigned char*p){return p[0]*65536u+p[1]*256u+p[2];}
static unsigned b32(unsigned char*p){return p[0]*16777216u+b24(p+1);}
static unsigned char*load(char*p,unsigned*n){FILE*f=fopen(p,"rb");if(!f)exit(2);fseek(f,0,2);*n=ftell(f);rewind(f);unsigned char*b=malloc(*n);if(fread(b,1,*n,f)!=*n)exit(2);fclose(f);return b;}
int main(int c,char**v){unsigned n,m,ch,k;unsigned char*b=load(v[1],&n),*s=load(v[2],&m);BibleDecoder d;
if(!BibleInit(&d,b,n))return 3;unsigned words=b32(s+8),terms=b32(s+12);unsigned char*counts=s+20+2*words+2*terms,*records=counts+2380;
for(ch=0;ch<1189;++ch)for(k=b16(counts+2*ch);k<b16(counts+2*(ch+1));++k){unsigned char*r=records+12*k;int byte;unsigned bytes=0;if(!BibleOpenVerse(&d,ch,b24(r+8),r[11]))return 4;
do{byte=BibleReadByte(&d);if(byte<0||++bytes>20000)return 5;putchar(byte);}while(byte!=10);}
return 0;}
'''
with tempfile.TemporaryDirectory(prefix='bible-verse-check-')as temp:
 p=Path(temp);(p/'check.c').write_text(source);subprocess.run(['cc','-O2','-DBIBLE_HUFFMAN=1','-DBIBLE_RAW_ONLY=1','-I'+str(app),str(app/'HuffmanDecoder.c'),str(p/'check.c'),'-o',str(p/'check')],check=True)
 decoded=subprocess.check_output([str(p/'check'),str(data/'container.bin'),str(data/'search.bin')])
 books=json.loads((data/'source.json').read_bytes());expected=''.join(v+'\n'for b in books for c in b['chapters']for v in c).encode('ascii');assert decoded==expected
 report=dict(status='passed',verses=sum(len(c)for b in books for c in b['chapters']),text_bytes=len(decoded),every_verse_restart_exact=True)
 (data/'verse-seeks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

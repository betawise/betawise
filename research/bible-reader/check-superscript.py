#!/usr/bin/env python3
"""Compare packed native font data with a preserved pre-packing source asset."""
import argparse,hashlib,json,subprocess
from prototype_support import prototype_app, prototype_test
from pathlib import Path
APP=prototype_app()
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--legacy-header',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
source='''#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#include LEGACY
#include CURRENT
int main(void){unsigned b,c,x,y,pixels=0;
 for(c=0;c<256;++c)assert(superscript_widths[c]==(c>=0x90&&c<=0x99?4:0));
 for(b=0;b<8;++b)for(c=0;c<256;++c){
  unsigned off=superscript_offsets[c];assert(off+4*(b+1)<=sizeof(superscript_bitmaps[b]));
  for(y=0;y<8*(b+1);++y)for(x=0;x<4;++x){
   unsigned before=(superscript_pages[b][c*4*(b+1)+(y/8)*4+x]>>(y%8))&1;
   unsigned after=(superscript_bitmaps[b][off+(y/8)*4+x]>>(y%8))&1;
   assert(before==after);++pixels;
  }
 }
 printf("%u\\n",pixels);return 0;
}
'''.replace('LEGACY',json.dumps(str(a.legacy_header.resolve()))).replace('CURRENT',json.dumps(str(APP/'Superscript.h')))
(out/'check.c').write_text(source);subprocess.run(['cc','-O2','-Wall','-Wextra',str(out/'check.c'),'-o',str(out/'check')],check=True);pixels=int(subprocess.check_output([str(out/'check')],text=True));assert pixels==294912
result=dict(status='passed',pixels=pixels,digit_pixels=11520,bands=8,digit_codes=10,unused_zero_width_codes=246,legacy_header_sha256=hashlib.sha256(a.legacy_header.read_bytes()).hexdigest(),packed_header_sha256=hashlib.sha256((APP/'Superscript.h').read_bytes()).hexdigest());(out/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

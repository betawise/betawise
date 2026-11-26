#!/usr/bin/env python3
"""Validate built IDs/headers and execute all five real font getters on m68000 QEMU.
Checks every packed glyph against editable BDF pixels; no screen or model oracle.
"""
import argparse,importlib.util,json,os,struct,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];FONTS=ROOT/'fonts'
spec=importlib.util.spec_from_file_location('fontgen',FONTS/'fontgen.py');fg=importlib.util.module_from_spec(spec);spec.loader.exec_module(fg)
STYLES=['Regular','Bold','Italic','BoldItalic'];FAMILIES=['Serif','Sans','Book','Mono']
SIZES={3:('Large','Large'),4:('Medium','Medium'),5:('Small','Small'),6:('Tiny','Tiny')}
START='''.text
.globl _start
_start:
 lea _GLOBAL_OFFSET_TABLE_,%a5
 jsr test
 move.l %d0,%d1
 moveq #1,%d0
 trap #0
.section .note.GNU-stack,"",@progbits
'''
def digest(glyphs):
 h=2166136261
 for im in glyphs:
  values=[im.width]+[sum(1<<(y-band)for y in range(band,min(band+8,im.height))if im.getpixel((x,y)))for band in range(0,im.height,8)for x in range(im.width)]
  for value in values:h=((h^value)*16777619)&0xffffffff
 return h

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path);args=p.parse_args();cross=os.environ.get('CROSS_COMPILE','m68k-linux-gnu-');results=[]
 for size, columns, lines in [('Medium',44,8),('Small',52,9),('Tiny',66,10)]:
  base=f'BetaWiseTerminal-{size}'
  data=(FONTS/(base+'.OS3KApp')).read_bytes()
  assert data[24:60].split(b'\0')[0].decode()==f'BetaWise - Terminal {size} ({columns}x{lines})'
 with tempfile.TemporaryDirectory(prefix='reader-font-check-')as td:
  td=Path(td);(td/'start.S').write_text(START)
  subprocess.run([cross+'gcc','-m68000','-c',td/'start.S','-o',td/'start.o'],check=True)
  for familyidx,family in enumerate(FAMILIES):
   for lines in range(3,7):
    base=f'BetaWise{family}-{SIZES[lines][0]}';data=(FONTS/(base+'.OS3KApp')).read_bytes();expectedid=0xaff0+4*familyidx+lines-3
    assert struct.unpack_from('>I',data)[0]==0xc0ffeead
    assert struct.unpack_from('>H',data,20)[0]==expectedid
    assert data[24:60].split(b'\0')[0].decode()==f'BetaWise - {family} {SIZES[lines][1]} ({lines} lines)'
    faces=[fg.load(FONTS/'build/bdf'/('BetaWise'+family)/f'{base}-{style}.bdf','iso8859-1',0x3f)for style in STYLES];faces.append(fg.load(FONTS/'build/bdf'/('BetaWise'+family)/'private'/f'{base}-SmallCaps.bdf','iso8859-1','blank'));height=faces[0][0].height
    hashes=[digest(face)for face in faces]
    source='''#include "os3k.h"
void BwProcessMessage(Message_e,uint32_t,uint32_t*);
void Os3kEntry(Message_e m,uint32_t p,uint32_t*s) {}
static const uint32_t expected[5]={HASHES};
int test(void) {
 FontHeader_t *seen[5]; uint32_t status; unsigned int s,c,j;
 for(s=0;s<5;s++) {
  FontHeader_t *f=0; uint32_t h=2166136261u;
  BwProcessMessage(s==4?MSG_FONT_GET_PRIVATE:MSG_FONT_GET_NORMAL+s,(uint32_t)&f,&status);
  if(status || !f || f->height!=EXPECTED_HEIGHT) return 1;
  seen[s]=f;
  for(j=0;j<s;j++) if(seen[j]==f) return 2;
  for(c=0;c<256;c++) {
   unsigned int w=f->width_table?f->width_table[c]:f->max_width;
   unsigned int off=f->offset_table?f->offset_table[c]:c*f->max_bytes;
   h=(h^w)*16777619u;
   if(!w || w>f->max_width) return 3;
   for(j=0;j<w*((f->height+7)/8);j++) h=(h^f->bitmap_data[off+j])*16777619u;
  }
  if(h!=expected[s]) return 4+s;
 }
 {uint32_t guard[3]={0x12345678,0,0xabcdef01};
  BwProcessMessage(MSG_FONT_GET_HEIGHT,(uint32_t)&guard[1],&status);
  if(status || guard[0]!=0x12345678 || guard[1]!=EXPECTED_HEIGHT || guard[2]!=0xabcdef01) return 8;
 }
 {const char *name=0; const char *want="EXPECTED_NAME";
  BwProcessMessage(MSG_FONT_GET_NAME,(uint32_t)&name,&status);
  if(status || !name) return 9;
  while(*want) if(*want++!=*name++) return 10;
  if(*name) return 11;
 }
 BwProcessMessage(MSG_INIT,0,&status);
 for(s=0;s<5;s++) {FontHeader_t *f=0;
  BwProcessMessage(s==4?MSG_FONT_GET_PRIVATE:MSG_FONT_GET_NORMAL+s,(uint32_t)&f,&status);
  if(status || f!=seen[s]) return 12;
 }
 return 0;
}
'''.replace('HASHES',','.join(f'0x{h:08x}u'for h in hashes)).replace('EXPECTED_HEIGHT',str(height)).replace('EXPECTED_NAME',f'BetaWise {family} {SIZES[lines][1]}')
    (td/'test.c').write_text(source)
    subprocess.run([cross+'gcc','-m68000','-msoft-float','-msep-data','-fomit-frame-pointer','-fshort-enums','-fno-store-merging','-Os','-fno-builtin','-ffreestanding','-I'+str(ROOT/'os3k'),'-nostdlib','-static','-Wl,--build-id=none','-Wl,--defsym,__os3k_rom_size=0','-Wl,--defsym,__os3k_ram_size=0',td/'start.o',td/'test.c',FONTS/'build'/base/'FontApplet.o',ROOT/'os3k/libos3k.a','-o',td/'test.elf'],check=True)
    subprocess.run(['qemu-m68k','-cpu','m68000',td/'test.elf'],check=True,timeout=10)
    results.append(dict(applet=base,id=f'{expectedid:04X}',height=height,style_hashes=hashes,glyphs=1280,passed=True))
 report=dict(applets=results,validated_applets=len(results),validated_style_tables=len(results)*5,validated_glyphs=len(results)*1280,passed=True,scope='Offline compiled m68000 handlers and image headers; not native editor acceptance')
 if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')
 print(f'PASS {len(results)} IDs/headers, 80 style/private getters, 20,480 packed glyphs, scalar height guards and init-independent lookups on m68000 QEMU')
if __name__=='__main__':main()

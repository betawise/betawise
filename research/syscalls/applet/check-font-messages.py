#!/usr/bin/env python3
"""Execute production font-provider messages under QEMU; no LCD or guest session."""
import argparse
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
BW = HERE.parents[2]
p = argparse.ArgumentParser()
p.add_argument('output', type=Path)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
start = a.output / 'start.S'
start.write_text('''.text
.globl _start
_start:
    lea _GLOBAL_OFFSET_TABLE_(%pc),%a5
    bsr check
    move.l %d0,%d1
    moveq #1,%d0
    trap #0
.section .note.GNU-stack,"",@progbits
''')
source = a.output / 'check.c'
source.write_text('''#include "os3k.h"
_Static_assert(sizeof(Message_e)==4,"message ABI width");
#ifndef EXPECTED_HEIGHT
#error missing height
#endif
void Os3kEntry(Message_e m,uint32_t p,uint32_t *s) {(void)m;(void)p;(void)s;}
int check(void) {
    struct { uint32_t before,value,after; } result;
    result.before=0x12345678;result.value=0;result.after=0xabcdef01;
    uint32_t reply=0x76543210;
    FontHeader_t *font=0;
    const char *font_name=0, *want=EXPECTED_NAME;
    BwProcessMessage(MSG_FONT_GET_NAME,(uint32_t)&font_name,&reply);
    if(reply||!font_name) return 6;
    while(*want) if(*want++!=*font_name++) return 7;
    if(*font_name) return 8;
    BwProcessMessage(MSG_FONT_GET_HEIGHT,(uint32_t)&result.value,&reply);
    if(reply||result.value!=EXPECTED_HEIGHT) return 1;
    if(result.before!=0x12345678||result.after!=0xabcdef01) return 2;
    BwProcessMessage(MSG_INIT,0,&reply);
    if(reply) return 5;
    BwProcessMessage(MSG_FONT_GET_NORMAL,(uint32_t)&font,&reply);
    if(!font||font->height!=EXPECTED_HEIGHT||!font->bitmap_data) return 3;
    for(uint32_t message=MSG_FONT_GET_BOLD; message<=MSG_FONT_GET_BOLD_ITALIC; ++message) {
        font=(FontHeader_t*)0x12345678;
        BwProcessMessage((Message_e)message,(uint32_t)&font,&reply);
        if(font||reply) return 4;
    }
    font=(FontHeader_t*)0x12345678;
    BwProcessMessage(MSG_FONT_GET_PRIVATE,(uint32_t)&font,&reply);
    if(font||reply) return 9;
    return 0;
}
''')
common = ['m68k-linux-gnu-gcc','-m68000','-msoft-float','-msep-data',
          '-fshort-enums','-fomit-frame-pointer','-fno-store-merging','-Os',
          '-ffunction-sections','-fdata-sections','-I'+str(BW/'os3k'),'-I'+str(BW/'fonts')]
for name, height, glyphs in [('Medium',8,'build/BetaWiseTerminal-Medium/glyphs.h'),
                             ('Small',7,'build/BetaWiseTerminal-Small/glyphs.h'),
                             ('Tiny',6,'build/BetaWiseTerminal-Tiny/glyphs.h')]:
    exe = a.output / (name+'.elf')
    cmd = common + ['-nostdlib','-static','-Wl,-e,_start,--gc-sections',
                    '-Wl,--defsym,__os3k_rom_size=0,--defsym,__os3k_ram_size=0',
                    f'-DEXPECTED_HEIGHT={height}',f'-DFONT_LINES={64//height}', '-DFONT_ID=0xA1F0', '-DFONT_INFO="Font message test"',
                    '-DFONT_NAME="BetaWise Terminal'+({'Medium':' Medium','Small':' Small','Tiny':' Tiny'}[name])+'"',
                    '-DEXPECTED_NAME="BetaWise Terminal'+({'Medium':' Medium','Small':' Small','Tiny':' Tiny'}[name])+'"',
                    f'-DFONT_GLYPHS="{glyphs}"',str(start),str(source),
                    str(BW/'fonts/FontApplet.c'),'-o',str(exe)]
    build = subprocess.run(cmd,capture_output=True,text=True)
    (a.output/(name+'.build.log')).write_text(build.stdout+build.stderr)
    build.check_returncode()
    result = subprocess.run(['qemu-m68k',str(exe)],capture_output=True,text=True,timeout=10)
    (a.output/(name+'.log')).write_text(result.stdout+result.stderr+f'\nexit={result.returncode}\n')
    assert result.returncode == 0, (name,result.returncode,result.stderr)
    print(f'PASS {name}: height={height}, output canaries, normal descriptor, optional faces')

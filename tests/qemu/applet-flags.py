#!/usr/bin/env python3
"""Check production metadata adapters with hostile A0 failures and narrow status."""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
cross=os.environ.get('CROSS_COMPILE','m68k-linux-gnu-')
source=r'''
#include "os3k_applet_internal.h"
#include <stddef.h>
AppletHeader_t first={.flags=0xff000030,.id=0xafee,.name="Neo Font - Fixture"};
AppletHeader_t second={.flags=0x10,.id=0xa123,.name="Neo Font - Not a font"};
AppletHeader_t third={.flags=0x20,.id=0xafef,.name="XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"};
uint32_t calls;
int test(void) {
 if(_OS3K_AppletHeaderById(0xafee)!=&first) return 1;
 if(_OS3K_AppletHeaderById(0xffff)) return 2;
 if(_OS3K_AppletHeaderByIndex(1)!=&first) return 3;
 if(_OS3K_AppletHeaderByIndex(2)!=&second) return 4;
 if(_OS3K_AppletHeaderByIndex(3)!=&third) return 5;
 if(_OS3K_AppletHeaderByIndex(31)) return 6;
 if(AppletGetFlags(1)!=0xff000030 || AppletGetFlags(2)!=0x10 || AppletGetFlags(3)!=0x20) return 7;
 if(AppletGetFlags(31)!=0) return 8;
 if(!AppletIsFont(1) || AppletIsFont(2) || !AppletIsFont(3)) return 12;
 if(AppletGetId(1)!=0xafee || AppletGetId(2)!=0xa123 || AppletGetId(3)!=0xafef || AppletGetId(31)) return 13;
 uint32_t before=calls;
 if(AppletGetFlags(0) || AppletGetFlags(32) || AppletGetFlags(0xffffffff) || _OS3K_AppletHeaderById(0)) return 9;
 if(before!=calls) return 10;
 return 0;
}
'''
mocks=r'''
.text
.globl AppletFindById
AppletFindById:
 move.l calls@GOT.w(%a5),%a0
 addq.l #1,(%a0)
 cmpi.w #0xafee,6(%sp)
 bne.s .Lbadid
 move.l first@GOT.w(%a5),%a0
 moveq #1,%d0
 rts
.Lbadid:
 movea.l #1,%a0
 moveq #0,%d0
 rts
.globl AppletGetName
AppletGetName:
 move.l calls@GOT.w(%a5),%a0
 addq.l #1,(%a0)
 move.l 4(%sp),%d0
 cmpi.l #1,%d0
 bne.s .Lsecond
 move.l first@GOT.w(%a5),%a0
 lea 24(%a0),%a0
 bra.s .Lcopy
.Lsecond:
 cmpi.l #2,%d0
 bne.s .Lthird
 move.l second@GOT.w(%a5),%a0
 lea 24(%a0),%a0
 bra.s .Lcopy
.Lthird:
 cmpi.l #3,%d0
 bne.s .Lbadname
 move.l third@GOT.w(%a5),%a0
 lea 24(%a0),%a0
.Lcopy:
 move.l 8(%sp),%a1
 moveq #35,%d1
.Lloop:
 tst.b (%a0)
 beq.s .Ldone
 move.b (%a0)+,(%a1)+
 dbra %d1,.Lloop
.Ldone:
 clr.b (%a1)
 move.l #0xabcdef01,%d0
 rts
.Lbadname:
 movea.l #1,%a0
 move.l #0xdeadbe00,%d0
 rts
.globl _start
_start:
 lea _GLOBAL_OFFSET_TABLE_(%pc),%a5
 move.l #0x12345678,%d2
 bsr.w test
 cmpi.l #0x12345678,%d2
 beq.s .Lexit
 moveq #11,%d0
.Lexit:
 move.l %d0,%d1
 moveq #1,%d0
 trap #0
.section .note.GNU-stack,"",@progbits
'''
with tempfile.TemporaryDirectory(prefix='applet-flags-') as temp:
    out=Path(temp);(out/'test.c').write_text(source);(out/'mocks.S').write_text(mocks)
    subprocess.run(['make','-s','-C',str(ROOT/'os3k')],check=True)
    subprocess.run([cross+'gcc','-m68000','-msoft-float','-msep-data','-fshort-enums',
        '-fomit-frame-pointer','-fno-store-merging','-Os','-ffreestanding','-fno-builtin',
        '-I'+str(ROOT/'os3k'),'-nostdlib','-static','-Wl,--build-id=none',
        str(out/'mocks.S'),str(out/'test.c'),str(ROOT/'os3k/build/os3k_applet.o'),
        '-o',str(out/'test')],check=True)
    subprocess.run([os.environ.get('QEMU_M68K','qemu-m68k'),'-cpu','m68000',str(out/'test')],check=True)
print('PASS metadata adapters: ID/index lookup, full names, flags, failure poison, narrow status, range guards')

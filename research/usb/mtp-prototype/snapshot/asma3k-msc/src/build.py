#!/usr/bin/env python3
from pathlib import Path
import subprocess,sys,json,hashlib
here=Path(__file__).resolve().parent;out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=True)
def run(a):subprocess.run(list(map(str,a)),check=True)
run(['m68k-linux-gnu-gcc','-m68000','-msoft-float','-fno-pic','-fno-pie','-fno-builtin','-fomit-frame-pointer','-Os','-Wall','-Wextra','-Werror','-c',here/'msc.c','-o',out/'msc.o'])
(out/'link.ld').write_text('ENTRY(msc_main)\nSECTIONS { . = 0x30000; .text : { *(.text*) *(.rodata*) } . = ALIGN(4); .data : { *(.data*) } .bss : { *(.bss*) *(COMMON) } end = .; }\n')
run(['m68k-linux-gnu-ld','-T',out/'link.ld',out/'msc.o','-o',out/'msc.elf']);run(['m68k-linux-gnu-objcopy','-O','binary',out/'msc.elf',out/'msc.bin'])
symbols={r.split()[2]:int(r.split()[0],16)for r in subprocess.check_output(['m68k-linux-gnu-nm',str(out/'msc.elf')],text=True).splitlines()if len(r.split())==3}
assert symbols['end']<0x3d000
(out/'symbols.json').write_text(json.dumps(symbols,indent=2))
with(out/'msc.dis').open('w')as f:subprocess.run(['m68k-linux-gnu-objdump','-d',str(out/'msc.elf')],stdout=f,check=True)
# Independently authored FAT12 superfloppy, 64 sectors, 512-byte sectors.
disk=bytearray(64*512);disk[:3]=bytes.fromhex('eb3c90');disk[3:11]=b'AS3KMSC '
def w16(o,v):disk[o:o+2]=v.to_bytes(2,'little')
w16(11,512);disk[13]=1;w16(14,1);disk[16]=2;w16(17,16);w16(19,64);disk[21]=0xf8;w16(22,1);w16(24,1);w16(26,1);disk[36]=0x80;disk[38]=0x29;disk[39:43]=b'MSC1';disk[43:54]=b'AS3K TEST  ';disk[54:62]=b'FAT12   ';disk[510:512]=b'\x55\xaa'
for start in [512,1024]:disk[start:start+5]=bytes.fromhex('f8ffffff0f')
text=b'AlphaSmart 3000 USB mass-storage prototype.\r\nRead-only FAT12 volume; device code runs on the emulated m68k.\r\n'
root=1536;disk[root:root+11]=b'README  TXT';disk[root+11]=1;w16(root+26,2);disk[root+28:root+32]=len(text).to_bytes(4,'little');disk[2048:2048+len(text)]=text
(out/'disk.img').write_bytes(disk)
print(json.dumps({'entry':hex(symbols['msc_main']),'end':hex(symbols['end']),'code_bytes':(out/'msc.bin').stat().st_size,'disk_sha256':hashlib.sha256(disk).hexdigest()}))

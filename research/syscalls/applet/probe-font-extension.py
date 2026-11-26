#!/usr/bin/env python3
"""Execute original provider binaries' unsupported-message paths on m68000 QEMU."""
import argparse
import json
from pathlib import Path
import struct
import subprocess

ROOT=Path(__file__).resolve().parents[3]
WORKSPACE=ROOT.parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    out=parser.parse_args().output.resolve();out.mkdir(parents=True,exist_ok=True)
    groups={}
    for path in (WORKSPACE/'Ghidra').rglob('*'):
        if not path.is_file() or path.suffix.lower()!='.os3kapp':continue
        data=path.read_bytes()
        if len(data)<148 or data[:4]!=bytes.fromhex('c0ffeead'):continue
        if struct.unpack_from('>I',data,16)[0]&0x30!=0x30:continue
        groups.setdefault(data,[]).append(str(path.relative_to(WORKSPACE)))
    records=[]
    for index,(data,paths) in enumerate(groups.items()):
        folder=out/str(index);folder.mkdir(exist_ok=True)
        (folder/'provider.bin').write_bytes(data)
        entry=struct.unpack_from('>I',data,0x84)[0]
        ram=struct.unpack_from('>I',data,8)[0]
        asm='''.text
.globl _start
_start:
 jsr check
 move.l %d0,%d1
 moveq #1,%d0
 trap #0
.globl write_results
write_results:
 movem.l %d2-%d3,-(%sp)
 moveq #4,%d0
 moveq #1,%d1
 move.l 12(%sp),%d2
 move.l 16(%sp),%d3
 trap #0
 movem.l (%sp)+,%d2-%d3
 rts
.balign 4
.globl provider
provider:
.incbin "PROVIDER"
.globl invoke_provider
invoke_provider:
 move.l %a5,-(%sp)
 movea.l 8(%sp),%a0
 movea.l 12(%sp),%a5
 move.l 24(%sp),-(%sp)
 move.l 24(%sp),-(%sp)
 move.l 24(%sp),-(%sp)
 jsr (%a0)
 lea 12(%sp),%sp
 movea.l (%sp)+,%a5
 rts
.section .note.GNU-stack,"",@progbits
'''.replace('PROVIDER',str(folder/'provider.bin'))
        (folder/'provider.S').write_text(asm)
        (folder/'test.c').write_text('''#include <stdint.h>
extern void write_results(const void*,uint32_t);
extern const uint8_t provider[];
extern void invoke_provider(const void*,void*,uint32_t,void*,void*);
static uint8_t ram[RAM_SIZE];
int check(void) {
 uint32_t results[6];
 uint32_t seeds[]={0,0x12345678};
 for(unsigned i=0;i<2;i++) {
  struct {uint32_t before,value,after;} output={0xABCDEF01,seeds[i],0x10203040};
  uint32_t status=0x87654321;
  invoke_provider(provider+ENTRY,ram,0x01000007,&output.value,&status);
  if(output.before!=0xABCDEF01 || output.after!=0x10203040) return 2;
  results[3*i]=seeds[i];results[3*i+1]=output.value;results[3*i+2]=status;
 }
 write_results(results,sizeof(results));
 return 0;
}
'''.replace('RAM_SIZE',str(max(4096,ram))).replace('ENTRY',str(entry)))
        build=subprocess.run(['m68k-linux-gnu-gcc','-m68000','-msoft-float','-O2','-static','-nostdlib','-ffreestanding','-fno-builtin','-Wl,--build-id=none',str(folder/'test.c'),str(folder/'provider.S'),'-o',str(folder/'test')],capture_output=True,text=True)
        build.check_returncode()
        run=subprocess.run(['qemu-m68k','-cpu','m68000',str(folder/'test')],capture_output=True,timeout=10)
        values=[list(struct.unpack_from('>III',run.stdout,i)) for i in range(0,len(run.stdout),12)] if len(run.stdout)==24 else []
        (folder/'run.log').write_text(repr(values)+'\n'+run.stderr.decode(errors='replace'))
        record=dict(paths=paths,entry=hex(entry),ram=ram,exit=run.returncode,results=values,stderr=run.stderr.decode(errors='replace'))
        records.append(record)
        print(paths[0],run.returncode,values,flush=True)
    (out/'results.json').write_text(json.dumps(records,indent=2)+'\n')
    assert all(r['exit']==0 and r['results']==[[0,0,0],[0x12345678,0,0]] for r in records)
    print(f'{len(records)} distinct binaries, {sum(len(r["paths"]) for r in records)} provider files')


if __name__=='__main__':main()

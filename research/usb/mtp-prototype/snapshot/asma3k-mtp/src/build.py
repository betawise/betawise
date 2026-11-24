#!/usr/bin/env python3
from pathlib import Path
import argparse,json,subprocess
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('out',type=Path);p.add_argument('--writable',action='store_true');p.add_argument('--ptp',action='store_true');a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
stems=['usb','mtp','native_fs','runtime','syscalls']
for stem in stems:
 src=HERE/(stem+('.S'if stem=='syscalls'else'.c'))
 subprocess.run(['m68k-linux-gnu-gcc','-m68000','-msoft-float','-fno-pic','-fno-pie','-fno-builtin','-fomit-frame-pointer','-fstack-usage','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-DWRITABLE='+str(int(a.writable)),'-DPLAIN_PTP='+str(int(a.ptp)),'-c',str(src),'-o',str(out/(stem+'.o'))],check=True)
(out/'link.ld').write_text('ENTRY(msc_main)\nSECTIONS { . = 0x30000; .text : { *(.text*) *(.rodata*) } . = ALIGN(4); .data : { *(.data*) } .bss : { *(.bss*) *(COMMON) } end = .; }\n')
subprocess.run(['m68k-linux-gnu-ld','-T',str(out/'link.ld'),*[str(out/(s+'.o'))for s in stems],'-o',str(out/'msc.elf')],check=True)
subprocess.run(['m68k-linux-gnu-objcopy','-O','binary',str(out/'msc.elf'),str(out/'msc.bin')],check=True)
nm=subprocess.check_output(['m68k-linux-gnu-nm',str(out/'msc.elf')],text=True);symbols={r.split()[2]:int(r.split()[0],16)for r in nm.splitlines()if len(r.split())==3};assert symbols['end']<0x3c000
(out/'symbols.json').write_text(json.dumps(symbols,indent=2)+'\n')
size=subprocess.check_output(['m68k-linux-gnu-size','-A',str(out/'msc.elf')],text=True);(out/'size.txt').write_text(size)
report={'writable':a.writable,'plain_ptp':a.ptp,'code_bytes':(out/'msc.bin').stat().st_size,'static_ram_bytes':sum(int(r.split()[1])for r in size.splitlines()if r.startswith(('.bss ','.data '))),'stack_reserved_bytes':8192,'telemetry_bytes':84,'max_session_file_handles':256 if a.writable else 0,'whole_file_buffer_bytes':0,'upload_chunk_bytes':128 if a.writable else 0,'entry':hex(symbols['msc_main']),'end':hex(symbols['end'])};(out/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

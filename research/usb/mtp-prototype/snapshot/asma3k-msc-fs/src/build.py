#!/usr/bin/env python3
"""Build only. Does not start MAME, create sockets or attach VHCI."""
from pathlib import Path
import argparse,json,subprocess
HERE=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('out',type=Path);args=ap.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
def run(a,**kw):return subprocess.run(list(map(str,a)),check=True,**kw)
for stem in ['msc','fat12','native_fs','runtime']:
 run(['m68k-linux-gnu-gcc','-m68000','-msoft-float','-fno-pic','-fno-pie','-fno-builtin','-fomit-frame-pointer','-fstack-usage','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-c',HERE/(stem+'.c'),'-o',out/(stem+'.o')])
(out/'link.ld').write_text('ENTRY(msc_main)\nSECTIONS { . = 0x30000; .text : { *(.text*) *(.rodata*) } . = ALIGN(4); .data : { *(.data*) } .bss : { *(.bss*) *(COMMON) } end = .; }\n')
run(['m68k-linux-gnu-ld','-T',out/'link.ld',*[out/(stem+'.o')for stem in ['msc','fat12','native_fs','runtime']],'-o',out/'msc.elf'])
run(['m68k-linux-gnu-objcopy','-O','binary',out/'msc.elf',out/'msc.bin'])
symbols={r.split()[2]:int(r.split()[0],16)for r in subprocess.check_output(['m68k-linux-gnu-nm',str(out/'msc.elf')],text=True).splitlines()if len(r.split())==3}
assert symbols['end']<0x3c000
(out/'symbols.json').write_text(json.dumps(symbols,indent=2)+'\n')
with(out/'msc.dis').open('w')as f:run(['m68k-linux-gnu-objdump','-d',out/'msc.elf'],stdout=f)
sections=subprocess.check_output(['m68k-linux-gnu-size','-A',str(out/'msc.elf')],text=True);(out/'size.txt').write_text(sections)
sizes={r.split()[3]:int(r.split()[1],16)for r in subprocess.check_output(['m68k-linux-gnu-nm','-S',str(out/'msc.elf')],text=True).splitlines()if len(r.split())==4}
report={'static_ram_bytes':sum(int(row.split()[1])for row in sections.splitlines()if row.startswith(('.bss ','.data '))),'fat_view_state_bytes':sum(sizes[k]for k in ['volume','naming','directory_cursor']),'test_telemetry_bytes':84,'test_stack_reserved_bytes':8192,'entry':hex(symbols['msc_main']),'end':hex(symbols['end']),'code_bytes':(out/'msc.bin').stat().st_size,'disk_image_bytes':0,'sector_buffer_bytes':0,'sectors':4096,'scope':'build only; filesystem export and AS3000 runtime awaiting validation'}
(out/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));print(sections)

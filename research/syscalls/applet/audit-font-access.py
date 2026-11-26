#!/usr/bin/env python3
"""Audit actual pinned dispatch tables and probe secondary header results in MAME."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
WORKSPACE=REPO.parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=HERE/'build/font-access')
    parser.add_argument('--ghidra',action='store_true')
    parser.add_argument('--mame',action='store_true')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    symbols={int(n):name for n,name in re.findall(r'^DEFINE_SYSCALL(?:_NEO)?\((\d+),\s*(\w+)\)',(REPO/'os3k/syscall.c').read_text(),re.M)}
    reports=[];bodies={}
    roms=json.loads((REPO/'research/abi-audit/rom-inventory.json').read_text())
    for rom in roms:
        data=(WORKSPACE/rom['path']).read_bytes()
        assert hashlib.sha256(data).hexdigest()==rom['sha256']
        targets=list(struct.unpack_from('>'+str(rom['slots'])+'I',data,rom['table_offset']))
        assert targets==rom['targets']
        slots=[dict(slot=i,opcode=f'A{4*i:03X}',target=f'{target:08X}',annotation=symbols.get(i)) for i,target in enumerate(targets)]
        reports.append(dict(name=rom['name'],slots=slots,populated=sum(bool(x)for x in targets),
            unnamed_populated=[i for i,x in enumerate(targets)if x and i not in symbols]))
        bodies[rom['name']]={}
        for slot,length,table_operand in [(143,56,6),(144,108,26)]:
            start=targets[slot]-rom['base'];body=bytearray(data[start:start+length])
            body[table_operand:table_operand+4]=b'\0'*4
            bodies[rom['name']][slot]=body.hex()
    assert all(bodies[name]==bodies['neo_3_21']for name in bodies)
    (out/'tables.json').write_text(json.dumps(reports,indent=2)+'\n')
    (out/'matched-header-services.json').write_text(json.dumps(bodies,indent=2)+'\n')
    neo=next(r for r in roms if r['name']=='neo_3_21');rom=WORKSPACE/neo['path']
    ranges=[(0x426768,0x426782),(0x439b00,0x439c60),(0x425f22,0x42616c),
            (0x4222e4,0x422300),(0x4224ac,0x422738),(0x42284e,0x422d56),
            (0x4383c2,0x4383e4),(0x427a22,0x427a70),(0x4298ae,0x429982)]
    text=[]
    for start,end in ranges:
        text.append(subprocess.check_output(['m68k-linux-gnu-objdump','-D','-b','binary','-m','m68k:68000',
            '--adjust-vma=0x410000',f'--start-address={start}',f'--stop-address={end}',rom],text=True))
    (out/'selected-paths.asm').write_text('\n'.join(text))
    if args.ghidra:
        (out/'java-home').mkdir(exist_ok=True)
        # A fresh project avoids mutating the user's analyzed firmware project.
        import tempfile
        project=Path(tempfile.mkdtemp(prefix='ghidra-',dir=out))
        command=[os.environ.get('GHIDRA_HOME','/opt/ghidra')+'/support/analyzeHeadless',str(project),'audit',
            '-import',str(rom),'-loader','BinaryLoader','-loader-baseAddr','0x410000',
            '-processor','68000:BE:32:default','-noanalysis','-scriptPath',str(HERE),
            '-postScript','InspectFontAccess.java',str(out)]
        with(out/'ghidra.log').open('w')as log:
            subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,
                env=dict(os.environ,JAVA_TOOL_OPTIONS='-Duser.home='+str(out/'java-home')))
        assert (out/'functions.txt').exists()
    if args.mame:
        probe=out/'probe';(probe/'roms/asneo').mkdir(parents=True,exist_ok=True)
        firmware=rom.parent
        for name in ['os3kneorom.os3kos','smallos3kneorom.os3kos']:
            path=probe/'roms/asneo'/name
            if not path.exists():path.symlink_to(firmware/name)
        subprocess.run(['make','-s','-C',str(REPO/'os3k')],check=True)
        flags=['-m68000','-msoft-float','-msep-data','-fomit-frame-pointer',
            '-fshort-enums','-fno-store-merging','-Os','-ffreestanding','-fno-builtin',
            '-ffunction-sections','-fdata-sections','-I'+str(REPO/'os3k')]
        subprocess.run(['m68k-linux-gnu-gcc',*flags,'-c',str(HERE/'applet-flags-probe.c'),'-o',str(probe/'sdk.o')],check=True)
        (probe/'link.ld').write_text('SECTIONS { . = 0x70400; .text : { *(.text*) *(.rodata*) } . = ALIGN(4); .got : { _GLOBAL_OFFSET_TABLE_ = .; *(.got*) } .data : { *(.data*) } .bss : { *(.bss*) } }')
        subprocess.run(['m68k-linux-gnu-ld','--gc-sections','-e','sdk_flags_probe',
            '-T',str(probe/'link.ld'),str(probe/'sdk.o'),str(REPO/'os3k/build/os3k_applet.o'),
            str(REPO/'os3k/build/syscall.o'),'-o',str(probe/'sdk.elf')],check=True)
        subprocess.run(['m68k-linux-gnu-objcopy','-O','binary',str(probe/'sdk.elf'),str(probe/'sdk.bin')],check=True)
        blob=(probe/'sdk.bin').read_bytes();assert len(blob)<0x1800
        names={line.split()[2]:int(line.split()[0],16)for line in subprocess.check_output(['m68k-linux-gnu-nm',str(probe/'sdk.elf')],text=True).splitlines()if len(line.split())==3}
        preamble='local RESULT_PATH='+json.dumps(str(probe/'results.json'))+'\n'
        preamble+='local SDK_BLOB={'+','.join(map(str,blob))+'}\n'
        preamble+='local SDK_GOT='+str(names['_GLOBAL_OFFSET_TABLE_'])+'\nlocal SDK_ENTRY='+str(names['sdk_flags_probe'])+'\n'
        (probe/'run.lua').write_text(preamble+(HERE/'probe-header-results.lua').read_text())
        command=[str(WORKSPACE/'mame/neodiag'),'asneo','-rompath',str(probe/'roms'),
            '-nvram_directory',str(probe/'nvram'),'-cfg_directory',str(probe/'cfg'),
            '-video','none','-sound','none','-nothrottle','-seconds_to_run','12',
            '-autoboot_delay','0','-autoboot_script',str(probe/'run.lua')]
        with(probe/'mame.log').open('w')as log:
            subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,
                env=dict(os.environ,SDL_VIDEODRIVER='dummy'),timeout=120)
        assert 'PASS header result registers 9 cases' in (probe/'mame.log').read_text()
    print('PASS pinned tables; lookup/name bodies match across three ROMs after table-base normalization')
    print('Neo 3.21:',reports[-1]['populated'],'populated entries;',reports[-1]['unnamed_populated'],'unnamed')
    print('Evidence:',out)


if __name__=='__main__':main()

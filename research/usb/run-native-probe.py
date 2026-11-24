#!/usr/bin/env python3
"""Compile ABI assertions and execute the original Neo direct USB dispatcher.

Tests a RAM-resident applet callback, not USB enumeration or a physical cable.
All emulator state is disposable; no LCD images are evaluated.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
here=Path(__file__).resolve().parent
workspace=here.parents[2]
out=Path(sys.argv[1]).resolve()
out.mkdir(parents=True,exist_ok=True)
def run(args,**kwargs):return subprocess.run(list(map(str,args)),check=True,**kwargs)
run(['python3',here/'audit-static.py'],stdout=(out/'static.json').open('w'))
roms=out/'roms/asneo';roms.mkdir(parents=True,exist_ok=True)
for name in ['os3kneorom.os3kos','smallos3kneorom.os3kos']:
    p=roms/name
    if not p.exists():p.symlink_to(workspace/'Ghidra/Alphasmart Neo/SmartApplets'/name)
run(['m68k-linux-gnu-gcc','-m68000','-msoft-float','-fshort-enums','-fomit-frame-pointer','-fno-pic','-fno-pie','-fno-builtin','-Os','-Wall','-Wextra','-Werror','-I',workspace/'betawise/os3k','-c',here/'native-probe.c','-o',out/'probe.o'])
(out/'link.ld').write_text('SECTIONS { . = 0x70400; .text : { *(.text*) *(.rodata*) } .data : { *(.data*) } .bss : { *(.bss*) } }\n')
run(['m68k-linux-gnu-ld','-T',out/'link.ld','-e','usb_probe_callback',out/'probe.o','-o',out/'probe.elf'])
run(['m68k-linux-gnu-objcopy','-O','binary',out/'probe.elf',out/'probe.bin'])
blob=(out/'probe.bin').read_bytes();assert len(blob)<0x1000
symbols=subprocess.check_output(['m68k-linux-gnu-nm',str(out/'probe.elf')],text=True)
callback=next(int(row.split()[0],16)for row in symbols.splitlines()if row.endswith(' usb_probe_callback'))
lua=(here/'native-probe.lua.in').read_text().replace('@BYTES@',','.join(map(str,blob))).replace('@CALLBACK@',str(callback)).replace('@OUTPUT@',json.dumps(str(out),ensure_ascii=False));assert '@'not in lua
(out/'probe.lua').write_text(lua)
with (out/'mame.log').open('w')as log:
 run([workspace/'mame/neodiag','asneo','-rompath',out/'roms','-nvram_directory',out/'nvram','-cfg_directory',out/'cfg','-video','none','-sound','none','-nothrottle','-autoboot_delay','0','-autoboot_script',out/'probe.lua','-seconds_to_run','32'],stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'SDL_VIDEODRIVER':'dummy'},timeout=90,cwd=out)
log=(out/'mame.log').read_text();assert 'PASS native USB dispatcher 4 cases'in log and 'FAIL native USB'not in log,log[-2000:]
records=[json.loads((out/f'case-{i}.json').read_text()) for i in range(1,5)]
result={'result':'PASS','cases':4,'records':records,'scope':'original Neo 3.21 dispatcher, custom applet callback, no actual USB transactions', 'callback_sha256':hashlib.sha256(blob).hexdigest(),'log_sha256':hashlib.sha256(log.encode()).hexdigest()}
(out/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

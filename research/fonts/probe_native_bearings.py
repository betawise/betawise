#!/usr/bin/env python3
"""Disposable Neo 3.21 CPU probe of widths, scanner flags and coordinate math.

No ROM patch, screenshot oracle, or saved user state. Evidence is CPU/RAM only.
"""
from pathlib import Path
import argparse
import json
import os
import subprocess

REPO = Path(__file__).resolve().parents[2]
WORKSPACE = REPO.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    template = (REPO/'research/syscalls/text/probe.lua.in').read_text()
    prefix = template[:template.index('local cases=')].replace('@NEO@', 'true')
    setup = r'''
local cases,results={},{}
local function add(slot,args,prep,check)cases[#cases+1]={slot,args,prep,check}end
local font,widths,offsets,bitmap=data+0xb00,data+0xc00,data+0xd00,data+0xf00
local function descriptor(width)
 fill(font,16);fill(widths,256,width);fill(offsets,512);fill(bitmap,512,0xff)
 m:write_u8(font,8);m:write_u8(font+1,width);m:write_u32(font+4,widths)
 m:write_u32(font+8,offsets);m:write_u32(font+12,bitmap)
end
local function record(name,want,actual)
 eq(actual,want);results[#results+1]=string.format('{"name":%q,"expected":%d,"actual":%d}',name,want,actual)
end
'''
    for width in range(256):
        setup += f"add({10000+0x42bece},{{font,0,106}},function()descriptor({width})end,function()record('unsigned width {width}',{width},cpu.state.D0.value&65535)end)\n"
    for width in (0,1,5,127,128,255):
        setup += f"add({10000+0x42bece},{{font,0,106}},function()descriptor({width});m:write_u32(font+4,0)end,function()record('fixed unsigned width {width}',{width},cpu.state.D0.value&65535)end)\n"
    for width, x in ((0,10),(5,10),(128,10),(255,10),(10,32760),(10,65530)):
        want=(width+x)&65535
        setup += f"add({10000+0x42c120},{{editor,buffer,buffer,buffer+1,data+0x820,data+0x824,data+0x828,data+0x82c,data+0x830}},function()file('j');state();descriptor({width});m:write_u32(data+0x820,font);m:write_u16(data+0x824,0);m:write_u16(data+0x828,{x});m:write_u16(data+0x82c,0);m:write_u16(data+0x830,0)end,function()record('scanner width {width} x {x}',{want},m:read_u16(data+0x828))end)\n"
    for flags in (1,2,4,8,16,32,64,128,255):
        want=10 if flags&1 else 15
        setup += f"add({10000+0x42c120},{{editor,buffer,buffer,buffer+1,data+0x820,data+0x824,data+0x828,data+0x82c,data+0x830}},function()file('j');state();descriptor(5);for i=0,3 do m:write_u32(editor+0x4e+4*i,font)end;m:write_u32(data+0x820,font);m:write_u16(data+0x824,{flags});m:write_u16(data+0x828,10);m:write_u16(data+0x82c,0);m:write_u16(data+0x830,0)end,function()record('scanner flags {flags}',{want},m:read_u16(data+0x828))end)\n"
    tokens = [(f'opaque {c:02X}', bytes([c, 4, c]), 3, 10) for c in (0xB3, 0xB4, 0xB7)]
    tokens += [(f'opaque {c:02X}', bytes([c, 7, 65, 66, 67, 7, c]), 7, 10) for c in (0xB8, 0xB9, 0xBA, 0xBB, 0xBE, 0xBF)]
    tokens += [('literal j', bytes([0xB0, ord('j'), 0xB0]), 3, 15)]
    tokens += [(f'ordinary {c:02X}', bytes([c]), 1, 15) for c in (0x08, 0x0A, 0x16, 0xA1, 0xA2)]
    for name, text, length, want in tokens:
        literal = 'string.char(' + ','.join(map(str, text)) + ')'
        setup += f"add({10000+0x42c120},{{editor,buffer,buffer,buffer+{len(text)},data+0x820,data+0x824,data+0x828,data+0x82c,data+0x830}},function()file({literal});state();descriptor(5);m:write_u32(data+0x820,font);m:write_u16(data+0x824,0);m:write_u16(data+0x828,10);m:write_u16(data+0x82c,0);m:write_u16(data+0x830,0)end,function()record('{name} advance',{want},m:read_u16(data+0x828));record('{name} length',{length},cpu.state.D0.value)end)\n"
    setup += "assert(m~=nil)\n"
    engine = template[template.index('local frame,index,phase,failed='):]
    done = "local f=assert(io.open("+json.dumps(str(out/'results.json'))+",'w'));f:write('['..table.concat(results,',')..']');f:close();print('PASS text probe '..#cases..' cases');machine:exit();return"
    engine = engine.replace("print('PASS text probe '..#cases..' cases');machine:exit();return", done)
    (out/'probe.lua').write_text(prefix+setup+engine)
    roms=out/'roms/asneo';roms.mkdir(parents=True,exist_ok=True)
    for name in ('os3kneorom.os3kos','smallos3kneorom.os3kos'):
        path=roms/name
        if not path.exists():path.symlink_to(WORKSPACE/'Ghidra/Alphasmart Neo/SmartApplets'/name)
    command=[str(WORKSPACE/'mame/neodiag'),'asneo','-rompath',str(out/'roms'),'-nvram_directory',str(out/'nvram'),'-cfg_directory',str(out/'cfg'),'-video','none','-sound','none','-nothrottle','-seconds_to_run','90','-autoboot_delay','0','-autoboot_script',str(out/'probe.lua')]
    with (out/'mame.log').open('w') as log:
        subprocess.run(command,cwd=out,env={**os.environ,'SDL_VIDEODRIVER':'dummy'},stdout=log,stderr=subprocess.STDOUT,timeout=150,check=True)
    log=(out/'mame.log').read_text()
    assert 'PASS text probe' in log and 'FAIL ' not in log,log[-1800:]
    print(f'PASS {len(json.loads((out/"results.json").read_text()))} native CPU assertions: {out}')


if __name__=='__main__':
    main()

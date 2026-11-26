#!/usr/bin/env python3
"""Execute Neo 3.21 token/flag conversion and printer-poll paths in disposable RAM."""
import argparse
import json
import os
from pathlib import Path
import subprocess

REPO = Path(__file__).resolve().parents[3]
WORKSPACE = REPO.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    out = parser.parse_args().output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    template = Path(__file__).with_name('probe.lua.in').read_text()
    prefix = template[:template.index('local cases=')].replace('@NEO@', 'true')
    setup = '''
local cases,results={},{}
local function add(slot,args,prep,check)cases[#cases+1]={slot,args,prep,check}end
local function hex(s)return(s:gsub('.',function(c)return string.format('%02X',c:byte())end))end
local function record(name,want,actual)
 assert(want==actual,name..': '..tostring(actual)..' ~= '..tostring(want))
 results[#results+1]=string.format('{"name":%q,"expected":%q,"actual":%q}',name,tostring(want),tostring(actual))
end
local function scanstate(text)
 file(text);state();local desc=m:read_u32(0x5c68)
 for i=0,3 do m:write_u32(editor+0x4e+4*i,desc)end
 fill(cursor,44);m:write_u32(cursor,editor);m:write_u32(cursor+0x10,desc)
 fill(data+0x800,256,0xa5)
end
'''
    rows=[]
    for mask in (1,2,4,8,16,32,64,128,0xF0):
        rows.append((f'flags {mask:02X}',b'a'+bytes([0xb1,mask,0xb1])+b'b'+bytes([0xb2,mask,0xb2])+b'c',b'ac' if mask&1 else b'abc'))
    for marker in (0xB3,0xB4,0xB7,0xB8,0xB9,0xBA,0xBB,0xBE,0xBF):
        token=bytes([marker,0x41,marker]) if marker<0xb8 else bytes([marker,7,0x41,0x42,0x43,7,marker])
        rows.append((f'opaque {marker:02X}',b'a'+token+b'b',b'ab'))
    for name,text,plain in rows:
        literal='string.char('+','.join(map(str,text))+')'
        for mode in (0,1):
            want=text if mode==0 else plain
            # Plain export uses skip_hidden; raw mode preserves all metadata.
            skip=mode
            setup+=f"add(179,{{cursor,200,data+0x800,0,{mode},{skip},0,0,0,0}},function()scanstate({literal})end,function()local n=cpu.state.D0.value;record('{name} read {mode} count',{len(want)},n);record('{name} read {mode} bytes','{want.hex().upper()}',hex(bytes(data+0x800,n)))end)\n"
        setup+=f"add({10000+0x42e81e},{{buffer,data+0x800,{len(text)},data+0x980}},function()scanstate({literal});m:write_u32(data+0x980,200)end,function()local n=m:read_u32(data+0x980);record('{name} block count',{len(plain)},n);record('{name} block bytes','{plain.hex().upper()}',hex(bytes(data+0x800,n)))end)\n"
        # Genuine printer MSG_TRANSFER_READ path through native transfer handler.
        setup+=f"add(186,{{transfer,0x6000d,data+0x900,data+0x980}},function()scanstate({literal});fill(transfer,124);m:write_u16(transfer,1);m:write_u8(transfer+2,7);m:write_u16(transfer+0x1e,40);m:write_u32(transfer+0x4c,{len(plain)});for i=0,43 do m:write_u8(transfer+0x50+i,m:read_u8(cursor+i))end;fill(data+0x900,20);m:write_u32(data+0x908,200);m:write_u32(data+0x910,data+0x800)end,function()local n=m:read_u32(data+0x90c);record('{name} printer reply',4,m:read_u32(data+0x980));record('{name} printer count',{len(plain)},n);record('{name} printer bytes','{plain.hex().upper()}',hex(bytes(data+0x800,n)))end)\n"
    for mask in (16,32,64,128,0xF0):
        for marker, reverse, initial, expected in ((0xB1,0,0,mask),(0xB2,0,mask,0),(0xB1,1,mask,0),(0xB2,1,0,mask)):
            text=bytes([marker,mask,marker])
            literal='string.char('+','.join(map(str,text))+')'
            setup+=f"add(179,{{cursor,3,data+0x800,{reverse},0,0,0,0,0,0}},function()scanstate({literal});m:write_u16(cursor+0x0c,{initial});m:write_u32(cursor+4,{3 if reverse else 0})end,function()record('flag {mask:02X} marker {marker:02X} reverse {reverse} count',3,cpu.state.D0.value);record('flag {mask:02X} marker {marker:02X} reverse {reverse} state',{expected},m:read_u16(cursor+0x0c))end)\n"
    engine=template[template.index('local frame,index,phase,failed='):]
    done="local f=assert(io.open("+json.dumps(str(out/'results.json'))+",'w'));f:write('['..table.concat(results,',')..']');f:close();print('PASS text probe '..#cases..' cases');machine:exit();return"
    engine=engine.replace("print('PASS text probe '..#cases..' cases');machine:exit();return",done)
    (out/'probe.lua').write_text(prefix+setup+engine)
    roms=out/'roms/asneo';roms.mkdir(parents=True,exist_ok=True)
    for name in ('os3kneorom.os3kos','smallos3kneorom.os3kos'):
        path=roms/name
        if not path.exists():path.symlink_to(WORKSPACE/'Ghidra/Alphasmart Neo/SmartApplets'/name)
    command=[str(WORKSPACE/'mame/neodiag'),'asneo','-rompath',str(out/'roms'),'-nvram_directory',str(out/'nvram'),'-cfg_directory',str(out/'cfg'),'-video','none','-sound','none','-nothrottle','-seconds_to_run','60','-autoboot_delay','0','-autoboot_script',str(out/'probe.lua')]
    with(out/'mame.log').open('w')as log:
        subprocess.run(command,cwd=out,env={**os.environ,'SDL_VIDEODRIVER':'dummy'},stdout=log,stderr=subprocess.STDOUT,timeout=120,check=True)
    log=(out/'mame.log').read_text()
    assert 'PASS text probe' in log and 'FAIL ' not in log,log[-1800:]
    print(f'PASS {len(json.loads((out/"results.json").read_text()))} assertions: {out}')


if __name__=='__main__':main()

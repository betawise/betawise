#!/usr/bin/env python3
"""Execute stock USB protocol entry points without endpoint transport.

Uses disposable MAME state. No screens, radio hardware or ROM patches.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
WORKSPACE = REPO.parent
out = Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=True)
row = next(r for r in json.loads((REPO/'research/abi-audit/rom-inventory.json').read_text())
           if r['name'] == 'neo_3_21')
assert hashlib.sha256((WORKSPACE/row['path']).read_bytes()).hexdigest() == row['sha256']
roms = out/'roms/asneo'
roms.mkdir(parents=True, exist_ok=True)
for name in ['os3kneorom.os3kos', 'smallos3kneorom.os3kos']:
    target = roms/name
    if not target.exists():
        target.symlink_to(WORKSPACE/'Ghidra/Alphasmart Neo/SmartApplets'/name)
script = r'''
local machine=manager.machine
local cpu=machine.devices[':maincpu'];local m=cpu.spaces.program
local frame,index,active,deadline=0,0,false,0
local input,output,request,result,stack,stop=0x72000,0x72400,0x72800,0x72840,0x78000,0x70000
local accesses=0
local taps={}
taps[1]=m:install_read_tap(0x2000000,0x2000007,'usb-read',function() if active then accesses=accesses+1 end end)
taps[2]=m:install_write_tap(0x2000000,0x2000007,'usb-write',function() if active then accesses=accesses+1 end end)
local function eq(a,b)assert(a==b,string.format('%x ~= %x',a,b))end
local cases={
 {name='protocol identification',bytes={1},event=0x40002,reply={2,0x30},status=4},
 {name='wrong event ignored',bytes={1},event=0x40007,reply={},status=0},
 {name='missing applet switch',bytes={0x3f,0x53,0x77,0x74,0x63,0x68,0xff,0xff},event=0x40002,
  reply={0x4e,0x6f,0x41,0x70,0x70,0x6c,0x65,0x74},status=4},
 {name='registered applet switch deferred (synthetic registry)',bytes={0x3f,0x53,0x77,0x74,0x63,0x68,0x12,0x34},event=0x40002,
  reply={0x53,0x77,0x69,0x74,0x63,0x68,0x65,0x64},status=4,pending=4},
 {name='shared parser checksum rejection',parser=true,bytes={0x19,0,0,0,0,0,0,0},reply={0x8f,0,0,0,0,0,0,0x8f}},
 {name='shared parser command 19',parser=true,bytes={0x19,0,0,0,0,0,0,0x19},reply={0x57,0,0,0,0,0,0,0x57}},
 {name='shared parser command 20',parser=true,bytes={0x20,0,0,0,0,0,0,0x20},reply={0x94,0,0,0,0,0,0,0x94}},
}
local function begin(c)
 -- Isolate the lookup from boot UI/installed-app state. No applet is executed.
 for i=0,31 do m:write_u32(0xe0a+4*i,0)end
 if c.pending then m:write_u32(0xe0a+12,0x72c00);m:write_u16(0x72c14,0x1234)end
 for a=input,input+16 do m:write_u8(a,0)end
 for a=output,output+32 do m:write_u8(a,0xa5)end
 for i,v in ipairs(c.bytes)do m:write_u8(input+i-1,v)end
 m:write_u32(request,#c.bytes);m:write_u32(request+4,input)
 m:write_u32(request+8,32);m:write_u32(request+12,0);m:write_u32(request+16,output)
 m:write_u32(result,1);m:write_u8(0x3dfd,0)
 m:write_u32(stack,stop);m:write_u32(stack+4,c.event)
 m:write_u32(stack+8,request);m:write_u32(stack+12,result)
 m:write_u16(stop,0x60fe)
 cpu.state.SR.value=0x2700;cpu.state.SP.value=stack;cpu.state.PC.value=0x441064
 if c.parser then
  m:write_u32(stack+4,input);m:write_u32(stack+8,#c.bytes)
  m:write_u32(stack+12,output);m:write_u32(stack+16,result);m:write_u32(stack+20,32)
  cpu.state.PC.value=0x410c82
 end
 accesses=0;active=true;deadline=frame+60
end
emu.register_frame_done(function()
 frame=frame+1;if frame<150 then return end
 local ok,err=pcall(function()
  if not active then
   index=index+1
   if index>#cases then print('PASS USB buffer dispatcher 7 cases; no USB endpoint accesses');machine:exit();return end
   begin(cases[index]);return
  end
  assert(frame<deadline,string.format('handler deadline exceeded PC=%x',cpu.state.PC.value))
  if cpu.state.PC.value~=stop and cpu.state.PC.value~=stop+2 then return end
  local c=cases[index]
  eq(cpu.state.SP.value,stack+4)
  if c.parser then eq(m:read_u32(result),#c.reply)
  else eq(m:read_u32(result),c.status);eq(m:read_u32(request+12),#c.reply)end
  for i,v in ipairs(c.reply)do eq(m:read_u8(output+i-1),v)end
  eq(m:read_u8(output+#c.reply),0xa5)
  eq(m:read_u8(0x3dfd),c.pending or 0);eq(accesses,0)
  print('PASS '..c.name);active=false
 end)
 if not ok then print('FAIL '..tostring(err));machine:exit()end
end)
'''
(out/'probe.lua').write_text(script)
args = [WORKSPACE/'mame/neodiag', 'asneo', '-rompath', out/'roms',
        '-nvram_directory', out/'nvram', '-cfg_directory', out/'cfg',
        '-video', 'none', '-sound', 'none', '-nothrottle', '-seconds_to_run', '15',
        '-autoboot_delay', '0', '-autoboot_script', out/'probe.lua']
with (out/'mame.log').open('w') as log:
    subprocess.run(list(map(str,args)), cwd=out, env={**os.environ,'SDL_VIDEODRIVER':'dummy'},
                   stdout=log, stderr=subprocess.STDOUT, check=True)
log = (out/'mame.log').read_text()
print(log)
assert 'PASS USB buffer dispatcher 7 cases' in log and 'FAIL' not in log and 'LUA ERROR' not in log
(out/'result.json').write_text(json.dumps(dict(rom_sha256=row['sha256'], cases=7,
    result='PASS', scope='Original buffer handler; no USB endpoint or wireless transport'),indent=2)+'\n')

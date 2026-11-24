#!/usr/bin/env python3
"""Exercise the built applet entry and original ROM services; no vision oracle."""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

from run import HERE, ROOT, prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    subprocess.run(['make', '-C', str(ROOT/'betawise/os3k')], check=True)
    subprocess.run(['make', '-C', str(HERE)], check=True)
    out = args.output.resolve() if args.output else Path(tempfile.mkdtemp(prefix='neo-dialog-check-'))
    if args.output:
        out.mkdir(parents=True, exist_ok=False)
    emulator = ROOT/'mame/neodiag'
    command = prepare(out, ROOT/'Ghidra/Alphasmart Neo/SmartApplets', emulator)
    blob = (HERE/'FontDialogDemo.OS3KApp').read_bytes()
    entry = 0x60000 + struct.unpack_from('>I', blob, 132)[0]
    symbols = {s.split()[2]:0x64000+(int(s.split()[0],16)&0x7fffffff)
               for s in subprocess.check_output(['m68k-linux-gnu-nm',str(HERE/'FontDialogDemo.elf')],text=True).splitlines() if len(s.split())==3}
    base = (HERE.parent/'screenshots/gallery.lua').read_text()
    header = base[:base.index('local lcd=')]
    harness = base[base.index('local index,frame,phase,failed='):]
    harness=harness.replace('if failed then return end;frame=frame+1;if frame<150 then return end', '''if failed then return end;frame=frame+1
 if bootKey and frame>=releaseAt then bootKey:clear_value();bootKey=nil end
 if bootChoice and not bootSeen[bootChoice] and not bootKey then
  local name=bootChoice==0xf and 'Y' or 'Enter'
  for row=0,15 do for _,field in pairs(machine.ioport.ports[':ROW'..row].fields)do
   if field.name:sub(1,#name+2)==name..' ['then bootKey=field end
  end end
  assert(bootKey,'missing bootstrap key');bootKey:set_value(1);releaseAt=frame+6;bootSeen[bootChoice]=true
 end
 if index==0 and (m:read_u16(0x35f8)~=0x2675 or m:read_u32(0xe0a)==0 or bootKey) then
  if frame>1800 then print('FAIL boot deadline');machine:exit()end
  return
 end''')
    cases = r'''
local bootChoice,bootKey,releaseAt;local bootSeen={}
local bootTap=m:install_read_tap(0x426466,0x426467,'first_boot_prompt',function()
 local a=cpu.state.A4.value
 if a>0x400 and a<0x80000 then local q=m:read_u8(a);if q==0xf or q==0x69 then bootChoice=q end end
end)
local lcd=dofile('@LCD@')
local function active()return m:read_u32(@demo_dialog@)end
local function poolcount()local n=0;for i=0,19 do if m:read_u16(0x7e92+i*1504)~=0 then n=n+1 end end;return n end
local function dispatch(message,param,check)
 add(10000+@ENTRY@,{message,param,0x73c00},nil,function()eq(m:read_u32(0x73c00),0);if check then check()end end)
end
add(10000+0x433afc,{},function()
 local b={@BYTES@};for i,v in ipairs(b)do m:write_u8(0x60000+i-1,v)end
 cpu.state.A5.value=0x64000
end,function()end)
add(174,{0,0x1000,data},nil,function()print(string.format('VERSION=%x',m:read_u32(data)))end)
add(174,{0,0,data+4},nil,function()print(string.format('HW=%x',m:read_u32(data+4)))end)
dispatch(0x18,0,function()eq(m:read_u8(@supported@),1)end)
dispatch(0x19,0,function()assert(active()~=0);eq(poolcount(),1)end)
local layouts={5,6,7,8,9,11,12,13,14,15,16,17,18,19,20,21}
for i,id in ipairs(layouts)do
 dispatch(0x20,13,function()eq(m:read_u8(@demo_in_layout@),1);eq(m:read_u8(active()+3),id);eq(poolcount(),1)end)
 if id==12 then
  dispatch(0x20,string.byte('C'),function()local e=m:read_u32(active()+4+0xd8);eq(m:read_u16(e+2),string.byte('C'))end)
 elseif id==15 then
  dispatch(0x20,string.byte('Z'),function()
   local e=m:read_u32(active()+4+0xd8);eq(m:read_u8(e+85),7);eq(m:read_u8(e+10),string.byte('Z'))
  end)
  dispatch(0x21,3,function()local e=m:read_u32(active()+4+0xd8);eq(m:read_u8(e+85),6)end)
 end
 if id==5 or id==6 or id==11 or id==16 or id==17 or id==19 or id==20 or id==21 then
  dispatch(0x20,9,function()end)
 end
 -- Toggle customization twice; native region flags must agree with the app.
 dispatch(0x21,0x8046,function()eq(m:read_u8(@demo_menu@),0)end)
 dispatch(0x21,0x8046,function()eq(m:read_u8(@demo_menu@),1)end)
 dispatch(0x21,0x48,function()eq(m:read_u8(@demo_in_layout@),0);eq(poolcount(),1);eq(m:read_u32(0xf416),active()+4)end)
 if i<#layouts then dispatch(0x21,0x0d,function()eq(m:read_u8(@demo_index@),i)end)end
end
dispatch(0x1a,0,function()eq(active(),0);eq(poolcount(),0)end)
dispatch(0x19,0,function()assert(active()~=0);eq(poolcount(),1)end)
-- Hide already requested by the applet through the normal API. Observe the
-- return/state before collecting identical controller records.
add(6,{12},function()eq(m:read_u8(0x48be),12)end,function()eq(m:read_u8(0x48be),12)end)
local samples,last={},nil
add(268,{255},nil,function()lcd.save('@OUT@/selector.lcd.json',samples)end)
cases[#cases][9]=function()local raw=lcd.refresh();if raw~=last then samples={}end;last=raw;samples[#samples+1]=lcd.frame();return #samples>=3 end
add(6,{12},nil,function()eq(m:read_u8(0x48be),12)end)
'''
    values = {**symbols,'ENTRY':entry,'BYTES':','.join(map(str,blob)),
              'LCD':ROOT/'betawise/tests/mame/asneo/NeoLCD.lua','OUT':out}
    for key,value in values.items():
        cases=cases.replace('@'+key+'@',str(value))
    if '@' in cases:
        raise ValueError('Unresolved Lua placeholder')
    (out/'check.lua').write_text(header+cases+harness)
    cmd = command[:command.index('-window')] + ['-video','none','-sound','none','-nothrottle',
        '-seconds_to_run','120','-autoboot_delay','0','-autoboot_script',str(out/'check.lua')]
    with (out/'mame.log').open('w') as log:
        subprocess.run(cmd,cwd=out,env={**os.environ,'SDL_VIDEODRIVER':'dummy'},stdout=log,stderr=subprocess.STDOUT,check=True)
    text=(out/'mame.log').read_text()
    if 'PASS extended probe' not in text or 'FAIL ' in text or 'LUA ERROR' in text:
        raise RuntimeError(text[-2400:])
    import sys
    sys.path.insert(0,str(ROOT/'betawise/tests/mame/asneo'))
    from neo_reader import lcd_frames
    lcd_frames(out/'selector.lcd.json')
    result={'layouts':16,'choice_edit':'C','text_edit':'Name: Z then backspace',
            'pool_lifecycle':'one live object; zero on kill-focus','lcd_stable_samples':3,
            'rendering_assertions':False,'evidence':str(out)}
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()

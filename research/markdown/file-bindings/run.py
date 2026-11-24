from pathlib import Path
import sys,json,subprocess,os
root=Path(__file__).resolve().parents[4];sys.path.insert(0,str(root/'betawise/tests/mame/asneo'))
from check import prepare_session
out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False)
fw=root/'Ghidra/Alphasmart Neo/SmartApplets';mame=root/'mame/neodiag'
prepare_session(out,fw,'extra',mame)
flash=bytearray((out/'nvram/asneo/flashnv').read_bytes());flash[0x70000:]=b'\xff'*(len(flash)-0x70000);aw=(fw/'alphawordplus.os3kapp').read_bytes();flash[0x70000:0x70000+len(aw)]=aw;(out/'nvram/asneo/flashnv').write_bytes(flash)
script=r'''
local machine=manager.machine;local cpu=machine.devices[':maincpu'];local mem=cpu.spaces.program
local out=OUT
io.stdout:setvbuf('no')
local function key(name)for row=0,15 do for _,f in pairs(machine.ioport.ports[':ROW'..row].fields)do if f.name:sub(1,#name+2)==name..' ['then return f end end end;error(name)end
local function dump(name,a,n)local f=assert(io.open(out..'/'..name,'wb'));for i=0,n-1 do f:write(string.char(mem:read_u8(a+i)))end;f:close()end
local function alpha()for i=1,31 do local p=mem:read_u32(0xe0a+4*i);if p>=0x400000 and p<0x800000 and mem:read_u16(p+20)==0xa000 then return mem:read_u32(0x355e+4*i)end end;error('AlphaWord missing')end
local frame,phase,index,start=0,'boot',1,0
local steps={{name='empty',keys={}},{name='typed',keys={{'A'},{'B'},{'C'}}},{name='selected',keys={{'Left Shift','Left'}}},{name='home',keys={{'Home'}}},{name='file2',keys={{'File 2'}}},{name='reopened',keys={{'File 1'}}}}
local events={};local function press(t,name)events[t]=function()key(name):set_value(1)end;events[t+4]=function()key(name):clear_value()end end
press(150,'Y');press(360,'Enter')
local held,ki,stable,last= {},1,0,''
local function capture()
 local a=alpha();assert(a>=0x1000 and a<0x80000);local ed=a+0x12;local rec=mem:read_u32(0x34d2)
 assert(rec>=0x1000 and rec+72<0x80000,'file record')
 assert(mem:read_u16(ed)==mem:read_u16(rec+0x44),'file identity')
 assert(mem:read_u16(a+0x16a)==0,'unexpected CoWriter companion')
 for off=0x24,0x30,4 do assert(mem:read_u32(rec+off)==0,'nonzero bind destination at '..off)end
 dump(steps[index].name..'-fileinfo.bin',rec,72);dump(steps[index].name..'-editor.bin',ed,94)
 local f=assert(io.open(out..'/'..steps[index].name..'-addresses.json','w'));f:write(string.format('{"file_record":%d,"editor":%d}',rec,ed));f:close()
 print('PASS '..steps[index].name..' bindings all zero; caret '..mem:read_u32(ed+0x24)..' anchor '..mem:read_u32(ed+0x38)..' selection '..mem:read_u16(ed+0x36)..' file position '..mem:read_u32(rec+0x14))
 if index==3 then assert(mem:read_u16(ed+0x36)~=0,'selection missing')end
 index=index+1;if index>#steps then print('PASS original AlphaWord file bindings');machine:exit();phase='done';return end
 ki=1;phase='press';start=frame
end
emu.register_frame_done(function()
 if phase=='done'then return end
 local ok,err=pcall(function()
 frame=frame+1;assert(frame<6000,'deadline');if events[frame]then events[frame]()end
 if phase=='boot' and frame>1100 and cpu.state.PC.value==0x426758 then capture()
 elseif phase=='press' and frame-start>=8 and cpu.state.PC.value==0x426758 then
  held=steps[index].keys[ki];for _,name in ipairs(held)do key(name):set_value(1)end;phase='release';start=frame
 elseif phase=='release' and frame-start>=4 then
  for _,name in ipairs(held)do key(name):clear_value()end;ki=ki+1;start=frame;phase=ki>#steps[index].keys and 'wait' or 'press';stable=0;last=''
 elseif phase=='wait' and frame-start>=8 and cpu.state.PC.value==0x426758 then
  local a=alpha();local ed=a+0x12;local rec=mem:read_u32(0x34d2);local s={}
  for i=0,71 do s[#s+1]=string.char(mem:read_u8(rec+i))end
  for i=0,93 do s[#s+1]=string.char(mem:read_u8(ed+i))end
  s=table.concat(s);stable=s==last and stable+1 or 1;last=s;if stable>=3 then capture()end
 end
 end)
 if not ok then print('FAIL '..tostring(err));phase='done';machine:exit()end
end)
'''.replace('OUT',json.dumps(str(out)))
(out/'run.lua').write_text(script)
with (out/'mame.log').open('w')as log:
 subprocess.run([str(mame),'asneo','-rompath',str(out/'roms'),'-nvram_directory',str(out/'nvram'),'-cfg_directory',str(out/'cfg'),'-video','none','-sound','none','-nothrottle','-seconds_to_run','100','-autoboot_delay','0','-autoboot_script',str(out/'run.lua')],stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'SDL_VIDEODRIVER':'dummy'},timeout=180,check=True)
log=(out/'mame.log').read_text();print(log);assert 'PASS original AlphaWord file bindings' in log and 'FAIL ' not in log

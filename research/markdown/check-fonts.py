#!/usr/bin/env python3
"""Query every distinct retained Neo font's four faces in disposable RAM."""
from pathlib import Path
import hashlib,json,os,struct,subprocess,sys
here=Path(__file__).resolve().parent;root=here.parents[2]
out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False)
seen=set();fonts=[]
for directory in ('Ghidra/Alphasmart Neo/NeoFonts','Ghidra/Alphasmart Neo/SmartApplets','Ghidra/Alphasmart 3000/SmartApplets'):
 for p in sorted((root/directory).iterdir()):
  if not p.is_file():continue
  b=p.read_bytes()
  if b[:4]!=bytes.fromhex('c0ffeead') or len(b)<148 or int.from_bytes(b[16:20],'big')&0x30!=0x30:continue
  h=hashlib.sha256(b).hexdigest()
  if h in seen:continue
  seen.add(h);fonts.append(dict(path=str(p),sha256=h,name=b[24:60].split(b'\0')[0].decode('latin1'),entry=int.from_bytes(b[132:136],'big'),ram=int.from_bytes(b[8:12],'big')))
fw=root/'Ghidra/Alphasmart Neo/SmartApplets';(out/'roms/asneo').mkdir(parents=True)
for n in ('os3kneorom.os3kos','smallos3kneorom.os3kos'):(out/'roms/asneo'/n).symlink_to(fw/n)
(out/'fonts.json').write_text(json.dumps(fonts,indent=2)+'\n')
items=','.join('{path='+json.dumps(f['path'])+',entry='+str(f['entry'])+',ram='+str(f['ram'])+'}' for f in fonts)
lua='local fonts={'+items+'}\nlocal destination='+json.dumps(str(out))+'''\nlocal machine=manager.machine;local cpu=machine.devices[':maincpu'];local m=cpu.spaces.program
local base,globals,code,stack,out=0x50000,0x40000,0x70000,0x7f000,0x74000
local frame,index,message,phase,deadline=0,1,0,'boot',0
local results={};local function bytes(a,n)local t={};for i=0,n-1 do t[#t+1]=string.char(m:read_u8(a+i))end;return table.concat(t)end
local function call(msg)
 m:write_u32(out,0xdeadbeef);m:write_u32(out+4,0xa5a5a5a5)
 m:write_u16(code,0x4ef9);m:write_u32(code+2,base+fonts[index].entry);m:write_u16(code+6,0x60fe)
 m:write_u32(stack,code+6);m:write_u32(stack+4,msg);m:write_u32(stack+8,out);m:write_u32(stack+12,out+4)
 cpu.state.A5.value=globals;cpu.state.SR.value=0x2700;cpu.state.SP.value=stack;cpu.state.PC.value=code;deadline=frame+120;phase='return'
end
emu.register_frame_done(function()
 frame=frame+1;if frame<150 then return end
 local ok,err=pcall(function()
 if phase=='boot'then
  local f=assert(io.open(fonts[index].path,'rb'));local b=f:read('*a');f:close();assert(#b<0x20000 and fonts[index].ram<0x10000)
  for i=0,fonts[index].ram-1 do m:write_u8(globals+i,0)end
  for i=1,#b do m:write_u8(base+i-1,b:byte(i))end
  message=0;results[index]={};call(0x18)
 elseif phase=='return'then
  local pc=cpu.state.PC.value
  if pc==code+6 or pc==code+8 then
   assert(cpu.state.SP.value==stack+4,'stack');assert(m:read_u32(out+4)==0,'reply')
   if message>0 then
    local ptr=m:read_u32(out);assert(ptr==0 or(ptr>=0x1000 and ptr<0x800000),'pointer')
    results[index][message]=ptr
    if ptr~=0 then
     local f=assert(io.open(string.format('%s/font-%02d-face-%d.bin',destination,index,message-1),'wb'));f:write(bytes(ptr,16));f:close()
    end
   end
   message=message+1
   if message<=4 then call(0x1000001+message)
   else print('PASS font '..index..' '..table.concat(results[index],','));index=index+1
    if index>#fonts then
     local f=assert(io.open(destination..'/faces.json','w'));f:write('[')
     for i,r in ipairs(results)do if i>1 then f:write(',')end;f:write('['..table.concat(r,',')..']')end
     f:write(']');f:close();print('PASS font census');machine:exit()
    else phase='boot'end
   end
  else assert(frame<deadline,string.format('timeout font %d PC=%x',index,pc))end
 end
 end)
 if not ok then print('FAIL '..tostring(err));machine:exit()end
end)
'''
(out/'probe.lua').write_text(lua)
args=[root/'mame/neodiag','asneo','-rompath',out/'roms','-nvram_directory',out/'nvram','-cfg_directory',out/'cfg','-video','none','-sound','none','-nothrottle','-seconds_to_run','40','-autoboot_delay','0','-autoboot_script',out/'probe.lua']
with(out/'mame.log').open('w')as log:subprocess.run(list(map(str,args)),cwd=out,env={**os.environ,'SDL_VIDEODRIVER':'dummy'},stdout=log,stderr=subprocess.STDOUT,check=True,timeout=100)
log=(out/'mame.log').read_text();assert 'PASS font census'in log and 'FAIL 'not in log,log[-1000:]
faces=json.loads((out/'faces.json').read_text())
for font,ptrs in zip(fonts,faces):font['faces']=ptrs;font['additional_faces']=sum(bool(x)for x in ptrs[1:])
(out/'results.json').write_text(json.dumps(fonts,indent=2)+'\n');print(json.dumps([{'name':f['name'],'additional_faces':f['additional_faces']}for f in fonts],indent=2))

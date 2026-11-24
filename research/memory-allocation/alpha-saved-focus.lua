
local machine=manager.machine;local cpu=machine.devices[':maincpu'];local mem=cpu.spaces.program
local out=OUT
io.stdout:setvbuf('no')
local function key(name)for row=0,15 do for _,f in pairs(machine.ioport.ports[':ROW'..row].fields)do if f.name:sub(1,#name+2)==name..' ['then return f end end end;error(name)end
local function dump(name,a,n)local f=assert(io.open(out..'/'..name,'wb'));for i=0,n-1 do f:write(string.char(mem:read_u8(a+i)))end;f:close()end
local function alpha()for i=1,31 do local p=mem:read_u32(0xe0a+4*i);if p>=0x400000 and p<0x800000 and mem:read_u16(p+20)==0xa000 then return mem:read_u32(0x355e+4*i)end end;error('AlphaWord missing')end
local frame,phase,index,start=0,'boot',1,0
local steps={{name='empty',keys={}},{name='typed',keys={{'A'},{'B'},{'C'}}},{name='leave',keys={{'Applets'},{'Down'},{'Enter'}}}}
local events={};local function press(t,name)events[t]=function()key(name):set_value(1)end;events[t+4]=function()key(name):clear_value()end end
press(150,'Y');press(360,'Enter')
local lost=false
local taps={}
local function install_observers()
taps[1]=mem:install_read_tap(0x470094,0x470095,'observe_aw_focus',function(offset,value,mask)
 if true then
  local sp=cpu.state.SP.value;local msg=mem:read_u32(sp)
  if msg~=0 then print(string.format('AW MSG %x pc %x',msg,cpu.state.PC.value)) end
  if msg==0x1a then
   lost=true
   dump('killfocus-entry-files.bin',0x10d2,mem:read_u32(0x34d6)-0x10d2+72)
   local ret=0x41822c
   taps[2]=mem:install_read_tap(ret,ret+1,'observe_aw_return',function(o,v,k)
    dump('killfocus-return-files.bin',0x10d2,mem:read_u32(0x34d6)-0x10d2+72)
    return v
   end)
  end
 end
 return value
end)
end
local observed=false
local held,ki,stable,last= {},1,0,''
local function capture()
 local a=alpha(); local rec=mem:read_u32(0x34d2)
 dump(steps[index].name..'-files.bin',0x10d2,mem:read_u32(0x34d6)-0x10d2+72)
 dump(steps[index].name..'-alpha.bin',a,0x200)
 print('CAPTURE '..steps[index].name..' current '..rec)
 if steps[index].name=='leave' then assert(lost,'no native KILLFOCUS observed') end
 index=index+1;if index>#steps then print('PASS native AlphaWord focus-loss observation');machine:exit();phase='done';return end
 ki=1;phase='press';start=frame
end
emu.register_frame_done(function()
 if phase=='done'then return end
 local ok,err=pcall(function()
 frame=frame+1;if not observed and mem:read_u16(0x35f8)==0x2675 then install_observers();observed=true end;assert(frame<6000,'deadline');if events[frame]then events[frame]()end
 if phase=='boot' and frame>1100 and cpu.state.PC.value==0x426758 then capture()
 elseif phase=='press' and frame-start>=8 and cpu.state.PC.value==0x426758 then
  held=steps[index].keys[ki];for _,name in ipairs(held)do key(name):set_value(1)end;phase='release';start=frame
 elseif phase=='release' and frame-start>=4 then
  for _,name in ipairs(held)do key(name):clear_value()end;ki=ki+1;start=frame;phase=ki>#steps[index].keys and 'wait' or 'press';stable=0;last=''
 elseif phase=='wait' and frame-start>=8 and cpu.state.PC.value==0x426758 then
  local s={}
  for i=0x10d2,mem:read_u32(0x34d6)+71 do s[#s+1]=string.char(mem:read_u8(i))end
  s=table.concat(s);stable=s==last and stable+1 or 1;last=s;if stable>=3 then capture()end
 end
 end)
 if not ok then print('FAIL '..tostring(err));phase='done';machine:exit()end
end)

-- Packet-level Manager test, not a USB controller/physical-device test.
-- Optional command-lane normalization is an explicit test-only NOR fixture.
local machine=manager.machine;local cpu=machine.devices[':maincpu'];local m=cpu.spaces.program;local frame=0
local stub,stack,input,output,count,request,status=0x20000,0x22000,0x24000,0x25000,0x26000,0x26100,0x26200
local function save(name,s)local f=assert(io.open(name,'wb'));f:write(s);f:close()end
local function exists(name)local f=io.open(name,'rb');if f then f:close();return true end;return false end
local function snapshot(name)local t={};for a=0,0x7ffff do t[#t+1]=string.char(m:read_u8(a))end;save(name..'.ram',table.concat(t))end
local function state()
 local rows={};for i=0,31 do local h=m:read_u32(0xe0a+i*4);if h~=0 then rows[#rows+1]=string.format('{"index":%d,"header":%d,"id":%d,"ram":%d,"base":%d}',i,h,m:read_u16(h+20),m:read_u32(h+8),m:read_u32(0x355e+i*4))end end
 return string.format('{"floor":%d,"marker":%d,"directory_marker":%d,"pc":%d,"applets":[%s]}',m:read_u32(0x35de),m:read_u16(0x35f8),m:read_u16(0x35f6),cpu.state.PC.value,table.concat(rows,','))
end
local function wait(fn,label,n)local deadline=frame+(n or 1800);repeat if fn()then return end;assert(frame<deadline,'timeout '..label..' pc='..string.format('%x',cpu.state.PC.value));coroutine.yield()until false end
local function park()cpu.state.SR.value=0x2700;cpu.state.PC.value=stub+6 end
local function call(a,args)
 m:write_u16(stub,0x4eb9);m:write_u32(stub+2,a);m:write_u16(stub+6,0x60fe)
 for i,v in ipairs(args or{})do m:write_u32(stack+(i-1)*4,v)end
 cpu.state.SR.value=0x2700;cpu.state.SP.value=stack;cpu.state.A5.value=0;cpu.state.PC.value=stub
 wait(function()return cpu.state.PC.value==stub+6 or cpu.state.PC.value==stub+8 end,'call '..string.format('%x',a))
 return cpu.state.D0.value
end
local function message(code)
 m:write_u32(request,0);m:write_u32(request+4,input);m:write_u32(request+8,1024);m:write_u32(request+12,0);m:write_u32(request+16,output);m:write_u32(status,0)
 return call(0x4100a0,{code,request,status})
end
local normalized=0
local armed,label=false,'';local clears=0;local tap;local warm_active,warm_done=false,false;local warm_tap
local function observe()
 if armed then
  local floor=m:read_u32(0x35de);local zero=true
  for a=floor,0x7d7ff do if m:read_u8(a)~=0 then zero=false;break end end
  if zero then clears=clears+1;snapshot(label..'-cleared');save(label..'-cleared.json',state());armed=false;print('OBSERVED native full clear '..label)end
 end
end
local choice,key,release_at=nil,nil,nil;local choices={};local bootstrap_tap;local trace_tap;local writes=0
local trace=assert(io.open('flash-writes.jsonl','w'))
local function named(n)for r=0,15 do for _,f in pairs(machine.ioport.ports[':ROW'..r].fields)do if f.name:sub(1,#n+2)==n..' ['then return f end end end;error(n)end
local main=coroutine.create(function()
 wait(function()return frame>=1 end,'start')
 bootstrap_tap=m:install_read_tap(0x426466,0x426467,'boot_choice',function()local a=cpu.state.A4.value;if a>0x400 and a<0x80000 then local q=m:read_u8(a);if q==0xf or q==0x69 then choice=q end end end)
 trace_tap=m:install_write_tap(0x400000,0x7fffff,'native_flash_commands',function(a,v,mask)
  writes=writes+1;if writes<8192 then trace:write(string.format('{"pc":%d,"address":%d,"value":%d,"mask":%d}\n',cpu.state.PC.value,a,v,mask));trace:flush()end
   if normalize_command_lanes and mask~=0xffff then
   local byte=mask==0xff00 and ((v>>8)&255)or(v&255)
   if (a==0x400aaa and (byte==0xaa or byte==0xa0 or byte==0x90 or byte==0x80 or byte==0xf0))or(a==0x400554 and byte==0x55)then
    -- Explicit test-only lane normalization. Native word data programming is unchanged.
    normalized=normalized+1;m:write_u16(a,byte)
   end
  end
 end)
 wait(function()return m:read_u16(0x35f8)==0x2675 and m:read_u32(0x3562)~=0 and m:read_u32(0x3566)~=0 end,'initialized real directory')
 -- The guest was genuinely cold-booted first; from here RPC occupies unused file RAM.
 park();m:write_u16(stub+6,0x60fe)
 tap=m:install_read_tap(0x4173cc,0x4173cd,'after_native_repack',observe)
 warm_tap=m:install_read_tap(0x417914,0x417915,'native_event_loop_entry',function()if warm_active then warm_done=true end end)
 save('ready',state());local sequence=1
 while true do
  wait(function()return exists('request-'..sequence)end,'host request',7200)
  local f=assert(io.open('request-'..sequence,'rb'));local blob=f:read('*a');f:close()
  local op=blob:sub(1,1);local data=blob:sub(2);local answer=''
  if op=='O'then message(0x40001)
  elseif op=='W'then
   for i=1,#data do m:write_u8(input+i-1,data:byte(i))end
   m:write_u32(count,0);call(m:read_u32(0x47a),{input,#data,output,count,1024})
   local n=m:read_u32(count);assert(n<=1024,'output overflow');local t={};for i=0,n-1 do t[#t+1]=string.char(m:read_u8(output+i))end;answer=table.concat(t)
  elseif op=='C'then
   -- Native transport close performs warm startup if applet initialization is invalid.
   if m:read_u16(0x35f8)~=0x2675 or m:read_u8(0x446)==0x52 then
    label=data;armed=m:read_u16(0x35f8)~=0x2675;warm_active=true;warm_done=false
    m:write_u32(request,0);m:write_u32(request+4,input);m:write_u32(request+8,1024);m:write_u32(request+12,0);m:write_u32(request+16,output)
    m:write_u16(stub,0x4eb9);m:write_u32(stub+2,0x4100a0);m:write_u16(stub+6,0x60fe)
    for i,v in ipairs({m:read_u8(0x446)==0x52 and 0x40006 or 0x4000c,request,status})do m:write_u32(stack+(i-1)*4,v)end
    cpu.state.SP.value=stack;cpu.state.PC.value=stub;cpu.state.SR.value=0x2700
    wait(function()return m:read_u16(0x35f8)==0x2675 and not armed and warm_done end,'native close warm restart',3600)
    snapshot(data..'-resumed');save(data..'-resumed.json',state());warm_active=false;park()
   else message(0x4000c)end
  elseif op=='L'then
   call(0x43c0ca,{0,0})
   local last=m:read_u32(0x34d6)
   assert(m:read_u32(last)+m:read_u32(last+12)<=0x5c000,'files overlap fixed RAM image')
   assert(m:read_u32(0x35de)>=0x5cc00,'installed A5 overlaps RAM image')
   for i=1,31 do local h=m:read_u32(0xe0a+i*4);if h~=0 then local base=m:read_u32(0x355e+i*4);for a=base,base+m:read_u32(h+8)-1 do m:write_u8(a,0xc3)end end end
   m:write_u32(0x35de,0x5c000)
   local f=assert(io.open('ram-probe.bin','rb'));local image=f:read('*a');f:close();assert(#image==1024)
   for i=1,#image do m:write_u8(0x5c000+i-1,image:byte(i))end
   for a=0x5c400,0x5cbff do m:write_u8(a,0)end
   warm_active=true;warm_done=false
   cpu.state.SR.value=0x2700;cpu.state.PC.value=0x44ff80
   wait(function()return warm_done and m:read_u32(0x5c400)==0x52414d49 end,'private RAM image entry',1800)
   warm_active=false;park();snapshot('ram-loaded');save('ram-loaded.json',state())
  elseif op=='H'then
   call(0x43c0ca,{0,0});local floor=m:read_u32(0x35de);m:write_u32(0x35de,floor-4096)
   for a=floor-4096,floor-1 do m:write_u8(a,0x5a)end
   for i=1,31 do local h=m:read_u32(0xe0a+i*4);if h~=0 then local base=m:read_u32(0x355e+i*4);local n=m:read_u32(h+8);for a=base,base+n-1 do m:write_u8(a,0xc3)end;m:write_u32(base,floor-4096);m:write_u32(base+4,4096)end end
   snapshot(data);save(data..'.json',state())
  elseif op=='R'then
   -- Reuse the retained 4096-byte gap as the removal fixture's heap.
   local floor=m:read_u32(0x35de)
   for a=floor,floor+4095 do m:write_u8(a,0x5a)end
   for i=1,31 do local h=m:read_u32(0xe0a+i*4);if h~=0 then local base=m:read_u32(0x355e+i*4);local n=m:read_u32(h+8);for a=base,base+n-1 do m:write_u8(a,0xc3)end;m:write_u32(base,floor);m:write_u32(base+4,4096)end end
   snapshot(data);save(data..'.json',state())
  elseif op=='S'then snapshot(data);answer=state();save(data..'.json',answer)
  elseif op=='Q'then save('response-'..sequence,'');save('guest-result.json',string.format('{"clear_observations":%d,"normalized_commands":%d}',clears,normalized));print('PASS Manager RPC completed clears='..clears);machine:exit();return
  else error('unknown op '..op)end
  save('response-'..sequence,answer);sequence=sequence+1
 end
end)
emu.register_frame_done(function()
 frame=frame+1
 if release_at and frame>=release_at then key:clear_value();key=nil;release_at=nil end
 if choice and not choices[choice] and not key then key=named(choice==0xf and 'Y'or'Enter');key:set_value(1);release_at=frame+6;choices[choice]=true end
 if coroutine.status(main)=='dead'then return end
 local ok,err=coroutine.resume(main);if not ok then save('failure.txt',tostring(err));snapshot('failure');print('FAIL '..tostring(err));machine:exit()end
end)

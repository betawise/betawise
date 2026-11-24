if _G.betawise_vector_probe_active then return end
_G.betawise_vector_probe_active=true
-- Observe native vector writes; sentinel writes below are explicitly test setup.
local machine=manager.machine;local cpu=machine.devices[':maincpu'];local m=cpu.spaces.program
local frame,phase=0,'cold';local taps={};local choice,key,release_at=nil,nil,nil;local choices={}
local trace=assert(io.open('vectors.jsonl','w'))
local function save(n,s)local f=assert(io.open(n,'wb'));f:write(s);f:close()end
local function snap(n)local t={};for a=0,0x7ffff do t[#t+1]=string.char(m:read_u8(a))end;save(n..'.ram',table.concat(t));print(string.format('STATE %s F=%08X A=%08X PC=%08X',n,m:read_u32(0x2c),m:read_u32(0x28),cpu.state.PC.value))end
local function wait(fn,label,n)local deadline=frame+(n or 2400);repeat if fn()then return end;assert(frame<deadline,'timeout '..label);coroutine.yield()until false end
local function named(n)for r=0,15 do for _,f in pairs(machine.ioport.ports[':ROW'..r].fields)do if f.name:sub(1,#n+2)==n..' ['then return f end end end;error(n)end
local loops=0
local main=coroutine.create(function()
 wait(function()return frame>=1 end,'start')
 taps[#taps+1]=m:install_write_tap(0x0,0x3ff,'vector_writes',function(a,v,mask)
  trace:write(string.format('{"phase":"%s","pc":%d,"address":%d,"value":%d,"mask":%d}\n',phase,cpu.state.PC.value,a,v,mask));trace:flush()
  if a>=0x28 and a<0x30 then print(string.format('VECTOR %s PC=%08X address=%X value=%X mask=%X',phase,cpu.state.PC.value,a,v,mask))end
 end)
 taps[#taps+1]=m:install_read_tap(0x426466,0x426467,'choice',function()local a=cpu.state.A4.value;if a>0x400 and a<0x80000 then local q=m:read_u8(a);if q==0xf or q==0x69 then choice=q end end end)
 taps[#taps+1]=m:install_read_tap(0x417914,0x417915,'loop',function()loops=loops+1 end)
 wait(function()return m:read_u16(0x35f8)==0x2675 and m:read_u32(0xe0e)==0x470000 and loops>0 end,'cold initialized')
 snap('cold')
 -- Execute a tiny real F-line handler, preserving exception frame/RTE behavior.
 -- Stub advances saved PC by two bytes, reports a marker, and returns.
 phase='test-install';m:write_u32(0x2c,0x458000)
 m:write_u16(0x30100,0xf123);m:write_u16(0x30102,0x60fe)
 cpu.state.SR.value=0x2700;cpu.state.SP.value=0x32000;cpu.state.PC.value=0x30100
 wait(function()return m:read_u32(0x30020)==0x464c494e and (cpu.state.PC.value==0x30102 or cpu.state.PC.value==0x30104) end,'F-line return')
 snap('fline-executed')
 phase='warm';local old=loops;cpu.state.PC.value=0x410082
 wait(function()return loops>old and m:read_u16(0x35f8)==0x2675 end,'warm entry')
 snap('warm');assert(m:read_u32(0x2c)==0x458000,'warm replaced F-line')
 -- Compact file capacity through the real firmware before reserving RAM image.
 phase='ram-prepare'
 m:write_u16(0x20000,0x4eb9);m:write_u32(0x20002,0x43c0ca);m:write_u16(0x20006,0x60fe)
 m:write_u32(0x22000,0);m:write_u32(0x22004,0)
 cpu.state.SR.value=0x2700;cpu.state.SP.value=0x22000;cpu.state.PC.value=0x20000
 wait(function()return cpu.state.PC.value==0x20006 or cpu.state.PC.value==0x20008 end,'file compact')
 local last=m:read_u32(0x34d6)
 assert(m:read_u32(last)+m:read_u32(last+12)<=0x5c000,'files overlap RAM image')
 assert(m:read_u32(0x35de)>=0x5cc00,'A5 overlaps RAM image')
 m:write_u32(0x35de,0x5c000)
 local f=assert(io.open('ram-probe.bin','rb'));local image=f:read('*a');f:close()
 for i=1,#image do m:write_u8(0x5c000+i-1,image:byte(i))end
 for a=0x5c400,0x5cbff do m:write_u8(a,0)end
 phase='ram-loader';old=loops;cpu.state.SR.value=0x2700;cpu.state.PC.value=0x44ff80
 wait(function()return loops>old and m:read_u32(0x5c400)==0x52414d49 end,'RAM loader')
 snap('ram-loader');assert(m:read_u32(0x2c)==0x458000,'RAM loader replaced F-line')
 -- A hardware reset re-enters the stock SmallROM, while retaining SRAM/flash.
 phase='hardware-reset';old=loops;machine:soft_reset()
 wait(function()return loops>old end,'reset return')
 snap('hardware-reset')
 print('PASS vector lifecycle');trace:close();machine:exit()
end)
emu.register_frame_done(function()
 frame=frame+1
 if release_at and frame>=release_at then key:clear_value();key=nil;release_at=nil end
 if choice and not choices[choice] and not key then key=named(choice==0xf and 'Y'or'Enter');key:set_value(1);release_at=frame+6;choices[choice]=true end
 if coroutine.status(main)=='dead'then return end
 local ok,err=coroutine.resume(main);if not ok then save('failure.txt',tostring(err));snap('failure');print('FAIL '..tostring(err));machine:exit()end
end)

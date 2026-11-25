-- Non-UI allocation qualification. All guest memory belongs to a disposable run.
local machine=manager.machine
local cpu=machine.devices[':maincpu'];local m=cpu.spaces.program
local frame=0
local function put32(a,v)m:write_u32(a,v)end
local function wait(fn,label)
 local deadline=frame+180
 repeat if fn()then return end;assert(frame<deadline,'timeout '..label);coroutine.yield()until false
end
local function call(address,args,context)
 m:write_u16(stub,0x4eb9);m:write_u32(stub+2,address);m:write_u16(stub+6,0x60fe)
 for i,v in ipairs(args or {})do put32(stack+(i-1)*4,v)end
 cpu.state.SR.value=0x2700;cpu.state.SP.value=stack;cpu.state.A5.value=context or a5;cpu.state.PC.value=stub
 wait(function()return cpu.state.PC.value==stub+6 or cpu.state.PC.value==stub+8 end,'call return')
 return cpu.state.D0.value
end
local function snapshot(label)
 local f=assert(io.open(label..'.ram','wb'))
 for addr=0,ram_size-1 do f:write(string.char(m:read_u8(addr)))end;f:close()
end
local tap
local main=coroutine.create(function()
 wait(function()return frame>=180 end,'initial execution')
 local result=call(mask_query,{0})
 local mask_base=cpu.state.A0.value
 assert(mask_base+0x100==floor_addr,'mask register relation')
 assert(result==m:read_u32(mask_base),'mask result')
 print(string.format('PASS mask query A0=%x floor_global=A0+100=%x',mask_base,floor_addr))
 -- Stop before the first firmware key/UI call, without changing stored ROM.
 -- The read tap supplies BRA.S -2 only at this test boundary.
 tap=m:install_read_tap(phase_stop,phase_stop+1,'startup_phase_stop',function(offset,value,mask)return 0x60fe end)
 local function seed()
  for j=top-0x3000,top-1 do m:write_u8(j,0x5a)end
  for i=0,31 do
   put32(descriptors+i*4,0);m:write_u16(ids+i*2,0xffff);put32(bases+i*4,0)
  end
  local private_ids={0xFF50,0xFF51}
  for i=1,2 do
   local h=data+(i-1)*256
   for j=0,255 do m:write_u8(h+j,0)end
   put32(h,0xc0ffeead);put32(h+8,2048);m:write_u16(h+20,private_ids[i])
   put32(descriptors+i*4,h);m:write_u16(ids+i*2,private_ids[i])
   put32(bases+i*4,top-i*2048)
  end
  -- Simulated heap record in applet 2's ordinary A5, and heap immediately below it.
  put32(top-4096,top-8192);put32(top-4092,4096)
  put32(floor_addr,top-8192)
  for j=0,71 do m:write_u8(first+j,0)end
  put32(first,payload);put32(first+12,512)
  put32(last_addr,first);put32(clipboard_addr,first);put32(current_addr,0)
 end
 local function phase(marker)
  m:write_u16(init_marker,marker)
  cpu.state.SR.value=0x2700;cpu.state.SP.value=stack;cpu.state.D7.value=top
  cpu.state.PC.value=phase_start
  wait(function()return cpu.state.PC.value==phase_stop or cpu.state.PC.value==phase_stop+2 end,'startup phase')
 end
 seed();phase(0x2675)
 assert(m:read_u32(floor_addr)==top-8192 and m:read_u32(top-4096)==top-8192)
 assert(m:read_u32(top-8192)==0x5a5a5a5a and m:read_u32(bases+8)==top-4096)
 snapshot('warm-valid')
 print('PASS valid marker skips clear/repack, preserves heap record, arena and lowered floor')
 seed();phase(0)
 assert(m:read_u32(floor_addr)==top-8192,'unexpected floor repair')
 for j=top-8192,top-1 do assert(m:read_u8(j)==0,'clear phase did not zero arena')end
 assert(m:read_u32(bases+4)==top-2048 and m:read_u32(bases+8)==top-4096)
 snapshot('warm-invalid')
 print('PASS invalid marker zeros A5 and heap but retains lowered floor (lost reservation record)')
 seed()
 -- Model a finalized install's RAM accounting; full Manager/flash transaction is not run.
 put32(data+256+8,3072);put32(floor_addr,top-8192-1024)
 phase(0)
 assert(m:read_u32(bases+8)==top-5120 and m:read_u32(floor_addr)==top-9216)
 assert(m:read_u32(top-4096)==0 and m:read_u32(top-8192)==0)
 snapshot('install-accounting')
 print('PASS install-accounting fixture repacks A5 from top, erases old heap, retains 4096 gap')
 seed()
 put32(descriptors+4,0);put32(floor_addr,top-8192+2048)
 phase(0)
 assert(m:read_u32(descriptors+4)==data+256 and m:read_u32(descriptors+8)==0)
 assert(m:read_u32(bases+4)==top-2048 and m:read_u32(floor_addr)==top-6144)
 assert(m:read_u32(top-4096)==0 and m:read_u32(top-8192)==0x5a5a5a5a)
 snapshot('remove-accounting')
 print('PASS removal-accounting fixture repacks surviving A5, loses record, retains gap; lower old heap bytes can remain')
 tap:remove()
 print('PASS lifecycle qualification complete '..model);machine:exit()
end)
emu.register_frame_done(function()
 frame=frame+1;if coroutine.status(main)=='dead'then return end
 local ok,err=coroutine.resume(main)
 if not ok then print('FAIL '..tostring(err));snapshot('failure');machine:exit()end
end)

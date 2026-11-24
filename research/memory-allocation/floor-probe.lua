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
local main=coroutine.create(function()
 wait(function()return frame>=180 end,'initial execution')
 local oldfloor=(model=='as3000')and 0x1c000 or 0x5c000
 local last=first+144
 local saved={256,1300,1700};local logical={200,1000,1600};local reserve={0,800,2000}
 local function pattern(i,j)return (i*53+j*17)&255 end
 for i=1,3 do
  local entry=first+(i-1)*72
  for j=0,71 do m:write_u8(entry+j,0)end
  local ptr=payload+(i-1)*8192
  put32(entry,ptr);put32(entry+4,logical[i]);put32(entry+8,saved[i])
  put32(entry+12,(i==3)and(oldfloor-ptr)or 8192)
  put32(entry+16,reserve[i]);put32(entry+20,123)
  for j=0,math.max(saved[i],reserve[i])-1 do m:write_u8(ptr+j,pattern(i,j))end
  for j=0,3 do put32(entry+36+j*4,data+(i-1)*32+j*4)end
  call(mirrors,{entry})
 end
 put32(floor_addr,oldfloor);put32(last_addr,last);put32(current_addr,last)
 local function verify(limit)
  local nextptr=payload
  for i=1,3 do
   local e=first+(i-1)*72;local ptr=m:read_u32(e);local cap=m:read_u32(e+12)
   assert(ptr==nextptr and ptr+cap<=limit,'noncontiguous or out of bounds')
   assert(cap>=math.max(saved[i],reserve[i]),'capacity below retained bytes')
   assert(m:read_u32(e+4)==logical[i]and m:read_u32(e+8)==saved[i],'length changed')
   for j=0,math.max(saved[i],reserve[i])-1 do assert(m:read_u8(ptr+j)==pattern(i,j),'payload damaged')end
   for j,off in ipairs({0,4,12,20})do assert(m:read_u32(data+(i-1)*32+(j-1)*4)==m:read_u32(e+off),'stale mirror')end
   nextptr=ptr+cap
  end
  call(check,{0xfeed}) -- Valid fixture: diagnostics/key-wait path must not be entered.
  return nextptr
 end
 verify(oldfloor);snapshot('floor-before')
 call(compact,{0,0})
 local packedend=verify(oldfloor)
 assert(packedend==payload+4096,'unexpected compacted extent')
 print(string.format('PASS compact %s payload=%x end=%x oldfloor=%x',model,payload,packedend,oldfloor))
 local newfloor=oldfloor-4096
 assert(packedend<=newfloor,'preflight capacity')
 put32(floor_addr,newfloor)
 for j=0,4095 do m:write_u8(newfloor+j,(j*29+7)&255)end
 call(compact,{last,0})
 local end_reserved=verify(newfloor)
 assert(end_reserved<=newfloor and newfloor-end_reserved<512,'last capacity not bounded by new floor')
 local function guard()
  for j=0,4095 do assert(m:read_u8(newfloor+j)==((j*29+7)&255),'reservation overwritten')end
 end
 -- Ask the original allocator for much more capacity than available.
 call(compact,{first+72,0x7fffffff});verify(newfloor);guard()
 print('PASS reservation, native growth pressure, payloads and bound-variable refresh')
 snapshot('floor-reserved')
 -- A wrapper must reject this request before modifying the floor.
 call(compact,{0,0});local before=verify(newfloor)
 local rejectedfloor=payload+4095
 assert(before>rejectedfloor,'oversize request should fail preflight')
 assert(m:read_u32(floor_addr)==newfloor);guard()
 print('PASS insufficient-space preflight leaves floor and reservation unchanged')
 -- Release in reverse order: restore floor, then let the ROM use the tail again.
 put32(floor_addr,oldfloor);call(compact,{last,0})
 local released=verify(oldfloor);assert(released<=oldfloor and oldfloor-released<512)
 snapshot('floor-released')
 print('PASS release restores native capacity')
 print('PASS floor qualification complete '..model);machine:exit()
end)
emu.register_frame_done(function()
 frame=frame+1;if coroutine.status(main)=='dead'then return end
 local ok,err=coroutine.resume(main)
 if not ok then print('FAIL '..tostring(err));snapshot('failure');machine:exit()end
end)

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
local function query(selector,out)
 put32(out,0x12345678);put32(out+4,0xa5a5a5a5)
 local ok=call(sysint,{0,selector,out})&0xff
 assert(m:read_u32(out+4)==0xa5a5a5a5,'selector overwrote canary')
 return ok,m:read_u32(out)
end
local function snapshot(label)
 local f=assert(io.open(label..'.ram','wb'))
 for addr=0,ram_size-1 do f:write(string.char(m:read_u8(addr)))end;f:close()
end
local main=coroutine.create(function()
 -- Only synchronize with CPU execution; these tests make no screen assertions.
 wait(function()return frame>=180 end,'initial execution')
 local f=assert(io.open('mathfacts.bin','rb'));local bytes=f:read('*a');f:close()
 for i=1,#bytes do m:write_u8(image+i-1,bytes:byte(i))end
 for i=0,0x1000-1 do m:write_u8(a5+i,0)end
 local ok,base=query(0x3000,data);local ok_size,size=query(0x5000,data+16)
 print(string.format('QUERY %s ptr_ok=%d ptr=%08x size_ok=%d size=%d',model,ok,base,ok_size,size))
 if model~='neo_3_21'then
  assert(ok==0 and ok_size==0 and base==0x12345678 and size==0x12345678)
 else assert(ok==1 and ok_size==1 and size==8192 and base>=0x400 and base+size<image)end
 call(image+0x961c)
 assert(m:read_u16(a5+0x492)==0)
 if model~='neo_3_21'then
  assert(m:read_u32(a5+0x494)==0 and m:read_u32(a5+0x48e)==0)
  assert(call(image+0x9680,{1})==0);snapshot('unsupported')
  print('PASS unsupported selectors and vendor allocator returns NULL')
 else
  assert(m:read_u32(a5+0x494)==base and m:read_u32(a5+0x48e)==size)
  local used=0
  for _,n in ipairs({1024,4096,3072})do
   assert(call(image+0x9680,{n})==base+used);used=used+n
   assert(m:read_u16(a5+0x492)==used)
  end
  assert(call(image+0x9680,{1})==0 and m:read_u16(a5+0x492)==8192)
  print('PASS original MathFacts allocator fills 8192 and rejects next byte')
  -- A separate applet context gets the same arena and an independent offset.
  call(image+0x961c,{},a5+0x800)
  assert(call(image+0x9680,{16},a5+0x800)==base)
  assert(m:read_u16(a5+0x492)==8192 and m:read_u16(a5+0x800+0x492)==16)
  print('PASS independent A5 contexts overlap: no global allocation/lease tracking')
  -- The helper is a byte bump allocator, not an aligned general-purpose malloc.
  call(image+0x961c)
  assert(call(image+0x9680,{1})==base)
  assert(call(image+0x9680,{3})==base+1)
  assert(call(image+0x9680,{0})==base+4 and m:read_u16(a5+0x492)==4)
  snapshot('scratch-overlap-and-alignment')
  print('PASS byte alignment and zero-size behavior characterized')
 end
 print('PASS allocation qualification complete '..model);machine:exit()
end)
emu.register_frame_done(function()
 frame=frame+1;if coroutine.status(main)=='dead'then return end
 local ok,err=coroutine.resume(main)
 if not ok then print('FAIL '..tostring(err));snapshot('failure');machine:exit()end
end)

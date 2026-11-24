-- Non-UI allocation qualification. All guest memory belongs to a disposable run.
local machine=manager.machine
local cpu=machine.devices[':maincpu'];local m=cpu.spaces.program
local frame=0
local function put32(a,v)m:write_u32(a,v)end
local function wait(fn,label)
 local deadline=frame+180
 repeat if fn()then return end;assert(frame<deadline,'timeout '..label);coroutine.yield()until false
end
local function syscall(slot,args)
 m:write_u16(stub,0x4eb9);put32(stub+2,stub+16);m:write_u16(stub+6,0x60fe)
 m:write_u16(stub+16,0xa000+slot*4)
 for i,v in ipairs(args or {})do put32(stack+(i-1)*4,v)end
 cpu.state.SR.value=0x2700;cpu.state.SP.value=stack;cpu.state.A5.value=a5;cpu.state.PC.value=stub
 wait(function()return cpu.state.PC.value==stub+6 or cpu.state.PC.value==stub+8 end,'syscall return')
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
 local saved={256,1300,1400};local logical={200,1000,1600};local reserve={0,800,2000}
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
  for j,off in ipairs({0,4,12,20})do put32(data+(i-1)*32+(j-1)*4,m:read_u32(entry+off))end
 end
 put32(floor_addr,oldfloor);put32(last_addr,last);put32(current_addr,last)
 -- Seed native folder/clipboard bookkeeping for public ID resolution.
 put32(floor_addr+0x0e,1)
 m:write_u16(first-0x240+2,0x7010)
 local folder=first-0x100+8
 put32(folder,first+72);m:write_u8(folder+4,2);m:write_u8(folder+5,0xff)
 m:write_u16(folder+6,2)
 put32(last_addr+4,first)
 m:write_u16(first+0x44,0xcb);m:write_u16(first+72+0x44,1);m:write_u16(last+0x44,2)
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
  syscall(107,{}) -- Public free-space query also invokes native invariant checking.
  return nextptr
 end
 snapshot('floor-seeded')
 syscall(107,{})
 assert(m:read_u32(last+8)==logical[3],'free-space invariant check normalizes saved below live')
 saved[3]=logical[3]
 verify(oldfloor);snapshot('floor-before')
 syscall(110,{0xfffffffc})
 verify(oldfloor)
 print('PASS cached snapshot leaves extents unchanged; free-space check normalized saved below live')
 syscall(115,{})
 -- A public create/delete pair should compact while retaining saved lengths.
 local tmpname=data+0x180
 for j,c in ipairs({66,87,84,69,77,80,0})do m:write_u8(tmpname+j-1,c)end
 local tmpid=syscall(122,{0,tmpname,0,512})
 assert(tmpid>0 and tmpid<0x8000,'temporary FileCreate failed')
 syscall(115,{})
 assert(syscall(123,{tmpid})==0,'temporary FileDelete failed')
 local preserved=verify(oldfloor)
 assert(preserved==payload+4096,'preserve-saved packed extent')
 snapshot('floor-preserved')
 assert(syscall(107,{})==oldfloor-preserved,'preserve-saved public preflight')
 -- Deliberately force the public creation fallback with no vacant tail.
 put32(floor_addr,preserved)
 snapshot('pressure-before')
 assert(syscall(107,{})==0,'pressure fixture should report no free space')
 local pressure_id=syscall(122,{0,tmpname,0,512})
 print(string.format('INFO pressure create result %x clipboard %d/%d file1 saved %d',pressure_id,m:read_u32(first+4),m:read_u32(first+8),m:read_u32(first+72+8)))
 assert(m:read_u32(first+4)==0 and m:read_u32(first+8)==0,'expected clipboard reset in allocation fallback')
 assert(m:read_u32(first+72+8)==1000,'expected snapshot in creation fallback')
 snapshot('pressure-after')
 print('PASS public pressure qualification complete '..model);machine:exit()
end)
emu.register_frame_done(function()
 frame=frame+1;if coroutine.status(main)=='dead'then return end
 local ok,err=coroutine.resume(main)
 if not ok then print('FAIL '..tostring(err));snapshot('failure');machine:exit()end
end)

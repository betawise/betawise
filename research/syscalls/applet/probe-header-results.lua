-- Real A-line calls with controlled descriptors in disposable Neo RAM.
local machine=manager.machine
local cpu=machine.devices[':maincpu'];local m=cpu.spaces.program
local frame,index,phase=0,0,0
local tablebase,code,spin,stack,output=0x0e0a,0x37f00,0x38000,0x3d000,0x38400
local saved={};local cases={};local records={}
local function put(a,s)for i=1,#s do m:write_u8(a+i-1,s:byte(i))end;m:write_u8(a+#s,0)end
local function initialize()
 for i=0,31 do saved[i]=m:read_u32(tablebase+4*i);m:write_u32(tablebase+4*i,0)end
 local names={'System fixture','Neo Font - Fixture','Plain applet',string.rep('X',36)}
 local ids={0,0xafee,0xa123,0xafef};local flags={0,0xff000030,0,0x20}
 for i=0,3 do
  local header=0x39000+256*i
  for j=0,255 do m:write_u8(header+j,0)end
  m:write_u32(header,0xc0ffeead);m:write_u32(header+16,flags[i+1]);m:write_u16(header+20,ids[i+1]);put(header+24,names[i+1])
  m:write_u32(tablebase+4*i,header)
 end
 m:write_u32(tablebase+16,0);m:write_u16(spin,0x60fe)
 for i=1,3 do
  cases[#cases+1]={op=0xa23c,args={ids[i+1]},d0=i,a0=0x39000+256*i,kind='find_id',flags=flags[i+1]}
  cases[#cases+1]={op=0xa240,args={i,output},d0=1,a0=0x39000+256*i+24+#names[i+1],kind='get_name',name=names[i+1],header=0x39000+256*i,flags=flags[i+1]}
 end
 cases[#cases+1]={op=0xa23c,args={0xffff},d0=0,kind='missing_id'}
 cases[#cases+1]={op=0xa240,args={31,output},d0=0,kind='missing_name'}
 for i,v in ipairs(SDK_BLOB) do m:write_u8(0x70400+i-1,v)end
 cases[#cases+1]={op=0,entry=SDK_ENTRY,args={},d0=0,kind='sdk_adapters'}
end
emu.register_frame_done(function()
 frame=frame+1;if frame<180 then return end
 local ok,err=pcall(function()
  if index==0 then initialize()end
  if phase==0 then
   index=index+1
   if index>#cases then
    for i=0,31 do m:write_u32(tablebase+4*i,saved[i])end
    local f=assert(io.open(RESULT_PATH,'w'));f:write('['..table.concat(records,',')..']\n');f:close()
    print('PASS header result registers '..#cases..' cases');machine:exit();return
   end
   local c=cases[index];if not c.entry then m:write_u16(code,c.op)end;m:write_u32(stack,spin)
   for i,v in ipairs(c.args)do m:write_u32(stack+4*i,v)end
   for i=0,39 do m:write_u8(output+i,0xa5)end
   cpu.state.D0.value=0x55555555;cpu.state.A0.value=0x77777770;cpu.state.A1.value=0x77777774
   cpu.state.A5.value=c.entry and SDK_GOT or 0x12345678;cpu.state.SR.value=0x2700;cpu.state.SP.value=stack;cpu.state.PC.value=c.entry or code
   phase=1
  else
   local c=cases[index];local d0=cpu.state.D0.value;local a0=cpu.state.A0.value;local a1=cpu.state.A1.value
   assert(cpu.state.PC.value==spin or cpu.state.PC.value==spin+2,'syscall did not return')
   assert(d0==c.d0,c.kind..' D0 '..string.format('%x',d0))
   if c.a0 then assert(a0==c.a0,c.kind..' A0 '..string.format('%x',a0))end
   if c.kind=='find_id' then assert(m:read_u32(a0+16)==c.flags,'returned header flags')end
   if c.name then
    for i=1,#c.name do assert(m:read_u8(output+i-1)==c.name:byte(i),'copied name mismatch')end
    assert(m:read_u8(output+#c.name)==0,'name terminator')
    assert(a0-24-#c.name==c.header,'header reconstruction')
    assert(m:read_u32(a0-24-#c.name+16)==c.flags,'reconstructed header flags')
   end
   assert(cpu.state.A5.value==(c.entry and SDK_GOT or 0x12345678),'A5 changed')
   if c.entry then assert(m:read_u32(0x73c00)==0x70617373,'SDK adapter result')end
   records[#records+1]=string.format('{"kind":"%s","opcode":%d,"D0":%d,"A0":%d,"A1":%d,"passed":true}',c.kind,c.op,d0,a0,a1)
   print('PASS',index,c.kind,string.format('D0=%x A0=%x A1=%x',d0,a0,a1));phase=0
  end
 end)
 if not ok then print('FAIL header results '..tostring(err));machine:exit()end
end)

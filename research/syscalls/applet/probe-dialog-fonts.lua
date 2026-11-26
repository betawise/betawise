-- Isolated original-ROM register audit; disposable machine state only.
local machine=manager.machine
local cpu=machine.devices[':maincpu'];local m=cpu.spaces.program
local code,spin,stack,out,text=0x37f00,0x38000,0x3d000,0x38400,0x38500
local cases={};local records={};local frame,index,phase=0,0,0
local function initialize()
 m:write_u16(spin,0x60fe);m:write_u8(text,65);m:write_u8(text+1,0)
 for _,s in ipairs({0,0x100,0x200,0x300,0x400,0x500,0x600,0x700,0x800,0x900,0xa00,0xb00,0xc00,0xd00,0xe00,0xf00,0x1000,0x2000,0x3000,0x4000,0x5000,0x8000,0x9000,0xa000})do
  -- Only pointer/query selectors: other selectors mutate or consume records.
  if s==0x700 or s==0x4000 or s==0x2000 or s==0x3000 or s==0x9000 then cases[#cases+1]={name=string.format('CallSysInt_%04x',s),op=0xa2b8,args={0,s,out}}end
 end
 cases[#cases+1]={name='width_before',op=0xa434,args={text,1}}
 cases[#cases+1]={name='initialize_dialog_subsystem_test_only',entry=0x433afc,args={}}
 cases[#cases+1]={name='width_initialized',op=0xa434,args={text,1}}
 cases[#cases+1]={name='create_invalid',op=0xa41c,args={0},zero=true}
 cases[#cases+1]={name='create_valid',op=0xa41c,args={8}}
 cases[#cases+1]={name='width_after',op=0xa434,args={text,1}}
 for i=1,20 do cases[#cases+1]={name='fill_pool_'..i,op=0xa41c,args={8},exhausted=i==20}end
end
emu.register_frame_done(function()
 frame=frame+1;if frame<180 then return end
 local ok,err=pcall(function()
  if index==0 then initialize()end
  if phase==0 then
   index=index+1
   if index>#cases then
    local f=assert(io.open(RESULT_PATH,'w'));f:write('['..table.concat(records,',')..']\n');f:close();print('PASS dialog font register probe '..#cases..' cases');machine:exit();return
   end
   local c=cases[index];if c.entry then m:write_u16(code,0x4eb9);m:write_u32(code+2,c.entry);m:write_u16(code+6,0x4e75)else m:write_u16(code,c.op)end;m:write_u32(stack,spin)
   for i,v in ipairs(c.args)do m:write_u32(stack+4*i,v)end
   m:write_u32(out,0xa5a5a5a5)
   cpu.state.D0.value=0x55555555;cpu.state.A0.value=0x77777770;cpu.state.A1.value=0x77777774
   cpu.state.SR.value=0x2700;cpu.state.SP.value=stack;cpu.state.PC.value=code;phase=1
  else
   assert(cpu.state.PC.value==spin or cpu.state.PC.value==spin+2,'call did not return')
   local c=cases[index];local d0=cpu.state.D0.value;local a0=cpu.state.A0.value;local a1=cpu.state.A1.value
   if c.zero then assert(d0==0 and a1==0,'invalid create register result')end
   if c.exhausted then assert(d0==0,'exhausted create result')end
   if c.name=='width_initialized' or c.name=='width_after'then
    assert(a1==0x7e32 and m:read_u8(a1)==9,'initialized width font')
    assert(m:read_u8(a1+16)==11 and m:read_u32(a1+28)==0x44d5a2,'adjacent dialog descriptor')
   end
   if c.name=='CallSysInt_0700'then assert(m:read_u32(out)==0x44af8e)end
   if c.name=='CallSysInt_4000'then assert(m:read_u32(out)==0x44d592)end
   if c.name:match('width')then print('WIDTH descriptor',string.format('%x height=%d',a1,m:read_u8(a1)))end
   records[#records+1]=string.format('{"case":"%s","D0":%d,"A0":%d,"A1":%d,"output":%d}',c.name,d0,a0,a1,m:read_u32(out))
   print('PASS',c.name,string.format('D0=%x A0=%x A1=%x output=%x',d0,a0,a1,m:read_u32(out)));phase=0
  end
 end)
 if not ok then print('FAIL dialog font register probe '..tostring(err));machine:exit()end
end)

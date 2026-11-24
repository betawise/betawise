local machine=manager.machine
local cpu=machine.devices[':maincpu'];local m=cpu.spaces.program
local code,data,stack=0x70000,0x72000,0x78000
local cases={};local function add(slot,args,prep,check,tick)cases[#cases+1]={slot,args,prep,check,tick}end
local function eq(a,b)assert(a==b,string.format('%x ~= %x',a,b))end
local function put(a,s)for i=1,#s do m:write_u8(a+i-1,s:byte(i))end;m:write_u8(a+#s,0)end
local dialog,region
local counts={[5]=5,[6]=3,[7]=1,[8]=1,[9]=1,[11]=3,[12]=1,[13]=1,[14]=1,[15]=1,[16]=3,[17]=3,[18]=1,[19]=3,[20]=3,[21]=3}

local lcd=dofile('/home/kirk/Projects/Alphasmart/betawise/tests/mame/asneo/NeoLCD.lua')
local savedMode
add(10000+0x433afc,{},nil,function()assert(m:read_u32(0x7e2e)~=0)end)
for _,layout in ipairs({5,6,7,8,9,11,12,13,14,15,16,17,18,19,20,21})do
 add(0,{},nil,function()end)
 add(263,{layout},nil,function()dialog=cpu.state.D0.value;assert(dialog~=0);eq(m:read_u16(dialog),counts[layout])end)
 add(265,function()return{dialog,0}end,nil,function()end)
 for r=0,counts[layout]-1 do
  local title=string.format('Layout %d / Region %d',layout,r+1)
  local body=counts[layout]==1 and 'First sample item\rSecond sample item\rThird sample item\rMore sample text' or (r==0 and 'Sample overview\rChoose an item' or 'Alpha\rBeta\rGamma')
  add(247,function()return{dialog,r,data+0x400*r,data+0x400*r+0x80,data+0x400*r+0x100,data+0x400*r+0x300,0}end,function()
   put(data+0x400*r,title);put(data+0x400*r+0x80,'Info');put(data+0x400*r+0x100,body);put(data+0x400*r+0x300,'Name:')
  end,function()end)
 end
 -- Exercise ordinary editable input using the normal key handler.
 for r=0,counts[layout]-1 do
  add(265,function()return{0,r}end,nil,function()end)
  add(256,{string.byte('A')},nil,function()end)
 end
 -- Record geometry before hiding the console cursor through the firmware API.
 add(6,{12},function()
  savedMode=m:read_u8(0x48be)
  local f=assert(io.open('/home/kirk/Projects/Alphasmart/betawise/research/syscalls/dialog/screenshots/layout-'..layout..'.geometry.txt','w'))
  f:write(string.format('layout=%d regions=%d cursor_mode=%x cursor_x=%d cursor_y=%d\n',layout,counts[layout],savedMode,m:read_u16(0x5c72),m:read_u16(0x5c74)))
  for r=0,counts[layout]-1 do
   local a=dialog+4+300*r
   f:write(string.format('region=%d flags=%x input_kind=%d\n',r,m:read_u8(a+0x10d),m:read_u8(a+0xdc)))
  end
  f:close()
 end,function()eq(m:read_u8(0x48be),12)end)
 local samples,last={},nil
 add(268,{255},nil,function()
  lcd.save('/home/kirk/Projects/Alphasmart/betawise/research/syscalls/dialog/screenshots/layout-'..layout..'.lcd.json',samples)
  machine.screens[':screen']:snapshot('/home/kirk/Projects/Alphasmart/betawise/research/syscalls/dialog/screenshots/layout-'..layout..'.mame.png')
  print('CAPTURE layout '..layout..' three identical controller samples')
 end)
 cases[#cases][9]=function()
  local raw=lcd.refresh()
  if last~=raw then samples={} end
  last=raw;samples[#samples+1]=lcd.frame()
  return #samples>=3
 end
 add(6,function()return{savedMode}end,nil,function()eq(m:read_u8(0x48be),savedMode)end)
 add(262,function()return{dialog}end,nil,function()end)
end
local index,frame,phase,failed=0,0,-1,false
emu.register_frame_done(function()
 if failed then return end;frame=frame+1;if frame<150 then return end
 local ok,err=pcall(function()
 if phase==-1 then
 index=index+1;if index>#cases then print('PASS extended probe '..#cases..' cases');machine:exit();return end
 phase=0;local p=cases[index];if p[3]then p[3]()end
 local stop=code+2;if p[1]>10000 then m:write_u16(code,0x4ef9);m:write_u32(code+2,p[1]-10000);stop=code+6 else m:write_u16(code,0xa000+4*p[1])end
 m:write_u16(stop,0x60fe);m:write_u32(stack,stop);for i,v in ipairs(type(p[2])=="function"and p[2]()or p[2])do m:write_u32(stack+4*i,v)end
 cpu.state.D0.value=0xa5a5a5a5;cpu.state.SR.value=p[8]and 0x2000 or 0x2700;cpu.state.SP.value=p[7]and stack-12 or stack;cpu.state.PC.value=code
 else
 phase=phase+1;local p=cases[index];if p[5]then p[5](phase)end
 if phase>240 then error("firmware call deadline") end
 if phase>=3 and (cpu.state.PC.value==code+(p[1]>10000 and 6 or 2) or cpu.state.PC.value==code+(p[1]>10000 and 8 or 4)) and (not p[9] or p[9]())then local stop=code+(p[1]>10000 and 6 or 2);assert(cpu.state.PC.value==stop or cpu.state.PC.value==stop+2,string.format("busy PC=%x",cpu.state.PC.value));eq(cpu.state.SP.value,stack+4);p[4]();print('PASS slot '..p[1]..' case '..index);phase=-1 end
 end
 end)
 if not ok then for i=0,80,4 do print(string.format('stack +%x %x',i,m:read_u32(cpu.state.SP.value+i)))end;print(string.format('regs PC=%x SP=%x A4=%x A5=%x',cpu.state.PC.value,cpu.state.SP.value,cpu.state.A4.value,cpu.state.A5.value));failed=true;print('FAIL extended case '..index..' '..tostring(err));machine:exit()end
end)

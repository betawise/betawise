-- Read-only save-item sampling, never reads or advances guest LCD data ports.
local controllers={}
for i=0,1 do
 local dev=assert(machine.devices[":lcd"..i])
 local state={}
 for _,name in ipairs({'m_ddram','m_start_line','m_display_on','m_adc','m_com_reverse','m_reverse','m_all_points'}) do
  local id=assert(dev.items['0/'..name], 'missing LCD save item '..name)
  state[name]=emu.item(id)
 end
 local reset=dev.items['0/m_reset'];if reset then state.m_reset=emu.item(reset) end
 controllers[i+1]=state
end
local cached={}
local function refresh_lcd()
 local signature={}
 for i,state in ipairs(controllers) do
  local c={ram=state.m_ddram:read_block(0,1188)}
  for name,item in pairs(state) do if name~='m_ddram' then c[name]=item:read(0) end end
  cached[i]=c
  signature[#signature+1]=c.ram..string.char(c.m_start_line,c.m_display_on,c.m_adc,c.m_com_reverse,c.m_reverse,c.m_all_points,c.m_reset or 0)
 end
 return table.concat(signature)
end
local function black(x,y)
 local c=cached[x//132+1];local col=x%132
 if c.m_display_on==0 or (c.m_reset or 0)~=0 then return false end
 if c.m_all_points~=0 then return true end
 if c.m_adc~=0 then col=131-col end
 local scan=c.m_com_reverse~=0 and 63-y or y
 local line=(scan+c.m_start_line)&63
 local bit=(c.ram:byte((line//8)*132+col+1)>>(line&7))&1
 return bit~=(c.m_reverse or 0)
end
local function assert_ram_matches_screen()
 for y=0,63 do for x=0,263 do
  assert(black(x,y)==((screen:pixel(x,y)&0xffffff)==0x25302a),string.format('RAM/screen mismatch at %d,%d',x,y))
 end end
 print('RAM_SCREEN_PARITY pixels=16896')
end

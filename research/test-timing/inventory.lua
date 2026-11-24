local machine=manager.machine
local done=false
emu.register_frame_done(function()
 if done then return end;done=true
 for tag,dev in pairs(machine.devices) do
  for name,item in pairs(dev.items) do
   local n=name:lower()
   if n:find('ddram',1,true) or n:find('lcd',1,true) or n:find('start_line',1,true) then print('LCD_ITEM',tag,name,item) end
  end
 end
 print('INVENTORY_DONE')
 machine:exit()
end)

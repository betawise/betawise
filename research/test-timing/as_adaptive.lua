-- Research-only action engine: expected LCD contents gate each assertion.
local machine=manager.machine
local events,actions={},{}
local function field(col,mask)
 for _,f in pairs(machine.ioport.ports[":COL."..col].fields) do if f.mask==mask then return f end end
 error('missing AS3000 key')
end
local function at(frame,fn) actions[#actions+1]={kind='check',fn=fn} end
local function text(frame,chars)
 if frame<530 then events[frame]=function() machine.natkeyboard:post(chars) end
 else actions[#actions+1]={kind='text',chars=chars} end
end
local function tap(frame,key) actions[#actions+1]={kind='tap',key=key} end
local function chord(frame,mod,key) actions[#actions+1]={kind='chord',key=key,mod=mod} end
-- LCD_READER
local function pass() machine.video:snapshot();print('PASS research-repl') end
local function run()
 local frame,index,started,previous,boot_ready=0,1,nil,nil,false
 emu.register_frame_done(function()
  frame=frame+1
  local ok,err=pcall(function()
   if events[frame] then events[frame]() end
   local screen=lcd();local stable=screen==previous;previous=screen
   if frame<530 then return end
   if not boot_ready then
    if not stable or not machine.natkeyboard.empty or not screen:find('MicroPython',1,true) or not screen:match('>>>%s*$') then return end
    boot_ready=true
   end
   local item=actions[index];if not item then return end
   if not started then
    started=frame
    if item.kind=='text' then
     if not use_native then machine.natkeyboard:post(item.chars) end
    elseif item.kind=='tap' then item.key:set_value(1)
    elseif item.kind=='chord' then item.mod:set_value(1) end
   end
   local age=frame-started
   local function next_action()
    print(string.format('ADAPT action=%d kind=%s frames=%d',index,item.kind,age))
    index=index+1;started=nil
   end
   if item.kind=='text' then
    if not use_native then
     if machine.natkeyboard.empty then next_action() end
    else
     local function press_char()
      local spec=assert(native_map[item.chars:sub(item.char,item.char)],'unmapped char')
      item.key=field(spec[1],spec[2]);item.shift=spec[3];item.keytime=frame;item.released=false
      if item.shift then field(14,1):set_value(1) end
      item.key:set_value(1)
     end
     if not item.char then item.char=1;press_char()
     elseif frame-item.keytime>=native_step then
      item.char=item.char+1
      if item.char>#item.chars then next_action() else press_char() end
     elseif not item.released and frame-item.keytime>=native_hold then
      item.key:clear_value();if item.shift then field(14,1):clear_value() end;item.released=true
     end
    end
   elseif item.kind=='tap' then
    if age==12 then item.key:clear_value() end
    if age>=14 then next_action() end
   elseif item.kind=='chord' then
    if age==2 then item.key:set_value(1) end
    if age==14 then item.key:clear_value() end
    if age==16 then item.mod:clear_value();next_action() end
   elseif item.kind=='check' and stable then
    local success,why=pcall(item.fn)
    if success then next_action() else item.why=tostring(why) end
   end
   if age>600 then error('readiness timeout: '..tostring(item.why)..'\n'..screen) end
  end)
  if not ok then print('FAIL adaptive '..tostring(err));machine:exit() end
 end)
end
text(60,'y');text(200,'\r');text(450,'\r')

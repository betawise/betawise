local actions={}
local screen=machine.screens[":screen"]
local function named(name)
 for row=0,15 do for _,f in pairs(machine.ioport.ports[":ROW"..row].fields) do
  if f.name:sub(1,#name+2)==name.." [" then return f end
 end end
 error('missing Neo key '..name)
end
local function black(x,y) return (screen:pixel(x,y) & 0xffffff)==0x25302a end
local function cell(x,y,char)
 local bits=glyphs[char];if not bits then return false end
 for dy=0,7 do for dx=0,5 do
  if black(x+dx,y+dy)~=(bits:sub(dy*6+dx+1,dy*6+dx+1)=='1') then return false end
 end end
 return true
end
local draft=''
local function logo_input_matches(text)
 local tail=text:sub(math.max(1,#text-18))
 local cursor=(2+#tail)*6
 for row=0,7 do
  local y=row*8
  local candidate=true
  for yy=y,y+7 do if not black(cursor,yy) then candidate=false;break end end
  if candidate and (cell(0,y,'?') or cell(0,y,'>')) and cell(6,y,' ') then
   for i=1,#tail do if not cell((i+1)*6,y,tail:sub(i,i)) then candidate=false;break end end
   if candidate then
    for yy=y,y+7 do for x=cursor+1,131 do if black(x,yy) then candidate=false;break end end end
   end
   if candidate then return true end
  end
 end
 return false
end
local function ready()
 if applet=='logo' then return logo_input_matches('') end
 for row=0,7 do
  local y=row*8
  if applet=='logo' then
   if (cell(0,y,'?') or cell(0,y,'>')) and cell(6,y,' ') then
    local valid=true
    for yy=y,y+7 do
     for x=12,131 do if black(x,yy)~=(x==12) then valid=false;break end end
     if not valid then break end
    end
    if valid then return true end
   end
  elseif memory:read_u8(0x48be)==0x0f and cell(0,y,'>') and cell(6,y,'>') and cell(12,y,'>') then
   local valid=true
   for yy=y,y+7 do for x=18,263 do
    if x~=23 and x~=24 and black(x,yy) then valid=false;break end
   end;if not valid then break end end
   if valid then return true end
  end
 end
 return false
end
local function matches(spec)
 if spec.graphics then
  local bits=graphics[spec.graphics]
  for y=0,63 do for x=0,131 do
   local index=y*132+x+1
   if black(132+x,y)~=(bits:sub(index,index)=='1') then return false end
  end end
 end
 return ready()
end
local function key(name,modifier,hold)
 actions[#actions+1]={kind='key',name=name,modifier=modifier,hold=hold or key_hold,step=math.max(key_step,(hold or key_hold)+key_gap)}
end
local punctuation={[' ']='Space',['=']='Equals',['-']='Minus',['.']='Period',[',']='Comma',[';']='Semicolon',["'"]='Quote',['[']='Left bracket',[']']='Right bracket',['/']='Slash',['\\']='Backslash',['`']='Grave',['\r']='Enter',['\t']='Tab'}
local shifted={['"']='Quote',[':']='Semicolon',['(']='9',[')']='0',['+']='Equals',['_']='Minus',['*']='8',['<']='Comma',['>']='Period',['!']='1',['@']='2',['%']='5',['{']='Left bracket',['}']='Right bracket'}
local function type_text(text)
 for i=1,#text do
  local ch=text:sub(i,i)
  key(shifted[ch] or punctuation[ch] or ch:upper(),(ch:match('%u') or shifted[ch]) and 'Left Shift' or nil)
  actions[#actions].char=ch
  if ch=='\r' then actions[#actions+1]={kind='ready'} end
 end
end
local function wait(frames) end -- Expected display state replaces completion sleeps.
local function checkpoint() actions[#actions+1]={kind='capture'} end
local events={}
local function press(frame,name)
 events[frame]=function() named(name):set_value(1) end
 events[frame+6]=function() named(name):clear_value() end
end
local function boot(name)
 applet=name
 press(150,'Y');press(360,'Enter');press(740,'Applets');press(850,'Down')
 if name=='micropython' then press(910,'Down') end
 press(980,'Enter')
end
local function finish() actions[#actions+1]={kind='finish'} end
local function run()
 local frame,index,started,previous=0,1,nil,nil
 emu.register_frame_done(function()
  local ok,err=pcall(function()
   -- CAPTURE_TICKS
   frame=frame+1
   if events[frame] then events[frame]() end
   if frame<1100 then return end
   local sig=screen:pixels();local stable=sig==previous;previous=sig
   local item=actions[index];if not item then return end
   if not started then
    started=frame
    if item.kind=='key' then
     item.key=named(item.name);item.mod=item.modifier and named(item.modifier)
     if item.mod then item.mod:set_value(1) end;item.key:set_value(1)
    end
   end
   local age=frame-started
   local function next_action()
    print(string.format('ADAPT action=%d kind=%s frames=%d',index,item.kind,age))
    index=index+1;started=nil
   end
   if item.kind=='key' then
    if age==item.hold then item.key:clear_value();if item.mod then item.mod:clear_value() end end
    if age>=item.step then
     if applet~='logo' or not item.char or item.char=='\r' or (stable and logo_input_matches(draft..item.char)) then
      if applet=='logo' and item.char then draft=item.char=='\r' and '' or draft..item.char end
      next_action()
     end
    end
   elseif item.kind=='ready' then if stable and ready() then next_action() end
   elseif item.kind=='capture' then
    if stable and matches(expectations[capture_count+1]) then next_action();capture() end
   elseif item.kind=='finish' then print('PASS Neo scenario completed');machine:exit() end
   if age>900 then error('readiness timeout at '..index..' kind='..item.kind) end
  end)
  if not ok then print('FAIL adaptive '..tostring(err));machine:exit() end
 end)
end

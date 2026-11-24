local bench_frames=0
local function bench_exit()
 print(string.format("BENCH time=%.9f frames=%d hz=%.6f",manager.machine.time:as_double(),bench_frames,manager.machine.screens[":screen"].refresh))
 manager.machine:exit()
end
local function experiment()
local variant="extra"
local test_case="research-repl"
local use_native=true
local native_map={["]"]={0,1,false},["}"]={0,1,true},["k"]={0,4,false},["K"]={0,4,true},["i"]={0,8,false},["I"]={0,8,true},["="]={0,16,false},["+"]={0,16,true},["8"]={0,32,false},["*"]={0,32,true},[","]={0,64,false},["<"]={0,64,true},["l"]={2,4,false},["L"]={2,4,true},["o"]={2,8,false},["O"]={2,8,true},["9"]={2,32,false},["("]={2,32,true},["."]={2,64,false},[">"]={2,64,true},["["]={3,1,false},["{"]={3,1,true},["'"]={3,2,false},["\""]={3,2,true},[";"]={3,4,false},[":"]={3,4,true},["p"]={3,8,false},["P"]={3,8,true},["-"]={3,16,false},["_"]={3,16,true},["0"]={3,32,false},[")"]={3,32,true},["/"]={3,128,false},["?"]={3,128,true},["\\"]={9,4,false},["|"]={9,4,true},[" "]={9,128,false},["d"]={10,4,false},["D"]={10,4,true},["e"]={10,8,false},["E"]={10,8,true},["3"]={10,32,false},["#"]={10,32,true},["c"]={10,64,false},["C"]={10,64,true},["s"]={11,4,false},["S"]={11,4,true},["w"]={11,8,false},["W"]={11,8,true},["2"]={11,32,false},["@"]={11,32,true},["x"]={11,64,false},["X"]={11,64,true},["\t"]={12,1,false},["a"]={12,4,false},["A"]={12,4,true},["q"]={12,8,false},["Q"]={12,8,true},["`"]={12,16,false},["~"]={12,16,true},["1"]={12,32,false},["!"]={12,32,true},["z"]={12,64,false},["Z"]={12,64,true},["t"]={13,1,false},["T"]={13,1,true},["g"]={13,2,false},["G"]={13,2,true},["f"]={13,4,false},["F"]={13,4,true},["r"]={13,8,false},["R"]={13,8,true},["5"]={13,16,false},["%"]={13,16,true},["4"]={13,32,false},["$"]={13,32,true},["v"]={13,64,false},["V"]={13,64,true},["b"]={13,128,false},["B"]={13,128,true},["y"]={15,1,false},["Y"]={15,1,true},["h"]={15,2,false},["H"]={15,2,true},["j"]={15,4,false},["J"]={15,4,true},["u"]={15,8,false},["U"]={15,8,true},["6"]={15,16,false},["^"]={15,16,true},["7"]={15,32,false},["&"]={15,32,true},["m"]={15,64,false},["M"]={15,64,true},["n"]={15,128,false},["N"]={15,128,true},["\r"]={9,64,false}}
local native_step=4;local native_hold=2
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
local function lcd()
    local rows = {}
    for _, tag in ipairs({":ks0066_0", ":ks0066_1"}) do
        local index = assert(machine.devices[tag].items["0/m_ddram"], "missing LCD DDRAM")
        local ddram = emu.item(index)
        -- AS3000 3.01 translates text through its ROM table at 0x4ea62c.
        -- These ASCII glyphs do not use their ASCII byte in controller DDRAM.
        local ascii = {[0]="g", [1]="y", [2]="p", [3]="q", [0xda]="\\", [0xd5]="~"}
        local function decode(bytes)
            return (bytes:gsub(".", function(c) return ascii[c:byte()] or c end))
        end
        rows[#rows + 1] = decode(ddram:read_block(0, 40))
        rows[#rows + 1] = decode(ddram:read_block(0x40, 40))
    end
    return table.concat(rows, "\n")
end

local function expect_text(expected)
    local screen = lcd()
    if expected=="KeyboardInterrupt" then assert(screen:match(">>>%s*$"),"interrupt still running") end
    assert(screen:find(expected, 1, true), "missing LCD text " .. expected .. "\n" .. screen)
end


local function pass() machine.video:snapshot();print('PASS research-repl') end
local function run()
 local frame,index,started,previous=0,1,nil,nil
 emu.register_frame_done(function() bench_frames=bench_frames+1
  frame=frame+1
  local ok,err=pcall(function()
   if events[frame] then events[frame]() end
   local screen=lcd();local stable=screen==previous;previous=screen
   if frame<530 then return end
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
  if not ok then print('FAIL adaptive '..tostring(err));bench_exit() end
 end)
end
text(60,'y');text(200,'\r');text(450,'\r')
-- Focused readline integration checks, shared by every ROM profile.
local frame = 530
local function check(expected)
    local ok, err = pcall(expect_text, expected)
    if not ok then error(err) end
end
local function enter(command, expected)
    text(frame, command .. "\r")
    frame = frame + #command * 12 + 180
    if expected then at(frame, function() check(expected) end) end
    frame = frame + 20
end
local function key(input)
    tap(frame, input)
    frame = frame + 40
end
local function expect(expected)
    at(frame, function() check(expected) end)
    frame = frame + 20
end
if variant == "extra" then
    enter('import micropython; events=[]; micropython.schedule(events.append,7); micropython.schedule(events.append,8)')
    enter('assert events==[7,8]; print("SCHEDULER",1)', 'SCHEDULER 1')
end

text(frame, 'print("BACKSPACE",123)X')
frame = frame + 360
key(field(9, 0x01)) -- Backspace: remove the stray X.
enter('', 'BACKSPACE 123')
text(frame, 'x')
frame = frame + 80
key(field(9, 0x01))
key(field(9, 0x01))
at(frame, function()
    local screen = lcd()
    assert(not screen:find('>>> >>>', 1, true), 'Backspace reprinted the prompt')
end)
frame = frame + 20
text(frame, 'x')
frame = frame + 80
key(field(4, 0x08)) -- Home, then Ctrl+D deletes the last remaining character.
chord(frame, field(12, 0x80), field(10, 0x04))
frame = frame + 100
at(frame, function() assert(not lcd():find('>>> >>>', 1, true), 'delete-to-empty reprinted the prompt') end)
frame = frame + 20
enter('print("DELETE",1)', 'DELETE 1')
text(frame, 'discard this draft')
frame = frame + 300
chord(frame, field(12, 0x80), field(15, 0x08)) -- Ctrl+U clears to beginning.
frame = frame + 100
enter('print("CTRLU",1)', 'CTRLU 1')
text(frame, 'pint("CTRLF",1)')
frame = frame + 250
key(field(4, 0x08)) -- Home, then Ctrl+F moves past the p.
chord(frame, field(12, 0x80), field(13, 0x04))
frame = frame + 100
enter('r', 'CTRLF 1')
text(frame, 'print("CTRLK",1)junk')
frame = frame + 320
for i=1,4 do key(field(5, 0x80)) end
chord(frame, field(12, 0x80), field(0, 0x04)) -- Ctrl+K removes the tail.
frame = frame + 100
enter('', 'CTRLK 1')
enter('history=0')
enter('history+=1; print("HISTORY",history)', 'HISTORY 1')
key(field(7, 0x80)) -- Up: recall and execute previous command.
enter('', 'HISTORY 2')
chord(frame, field(12, 0x80), field(3, 0x08)) -- Ctrl+P recalls history.
frame = frame + 80
chord(frame, field(12, 0x80), field(15, 0x80)) -- Ctrl+N returns to new input.
frame = frame + 80
chord(frame, field(12, 0x80), field(3, 0x08))
frame = frame + 80
enter('', 'HISTORY 3')
enter('completionvalue=37')
text(frame, 'print("COMPLETE",completi')
frame = frame + 320
key(field(12, 1)) -- Complete a user-defined name.
enter(')', 'COMPLETE 37')
enter('word="abc"')
text(frame, 'print("METHOD",word.upp')
frame = frame + 320
key(field(12, 1)) -- Complete an attribute.
enter('())', 'METHOD ABC')
text(frame, 'print("EDIT",12)')
frame = frame + 240
key(field(5, 0x80)) -- Left twice, insert in the middle.
key(field(5, 0x80))
enter('0', 'EDIT 102')
text(frame, 'if True:\r')
frame = frame + 200
key(field(12, 1)) -- Four-space indent after newline.
enter('print("TAB",1)\r', 'TAB 1')
-- Exercise collection and recall after many temporary allocations.
enter('exec(\"for i in range(900):\\\\n t=list(range(12))\");print(\"ALLOC\",1)', 'ALLOC 1')
frame = frame + 200
enter('assert completionvalue==37; print("ALIVE",1)', 'ALIVE 1')
text(frame, 'while True:\r pass\r\r')
frame = frame + 450
chord(frame, field(12, 0x80), field(10, 0x40))
frame = frame + 150
expect('KeyboardInterrupt') -- Check full decoded LCD text, not a substitute marker.
enter('assert completionvalue==37; print("INTERRUPT",1)', 'INTERRUPT 1')
if variant == "extra" then
    enter('f=getattr(micropython,"kbd"+chr(95)+"intr"); print("HOOK",1)', 'HOOK 1')
    text(frame, 'while True:\r f(24)\r\r')
    frame = frame + 450
    chord(frame, field(12, 0x80), field(11, 0x40)) -- Assigned Ctrl+X.
    frame = frame + 150
    expect('KeyboardInterrupt')
    text(frame, 'while True:\r f(120)\r\r')
    frame = frame + 450
    key(field(11, 0x40)) -- Assigned plain x.
    frame = frame + 150
    expect('KeyboardInterrupt')
end

chord(frame, field(12, 0x80), field(10, 0x04))
frame = frame + 120
expect('MicroPython')
enter('try:\r completionvalue\rexcept NameError:\r print("RESET",1)\r', 'RESET 1')
-- The adapter must preserve upstream raw and paste modes.
chord(frame, field(12, 0x80), field(12, 0x04)) -- Ctrl+A: raw REPL.
frame = frame + 100
expect('raw REPL')
text(frame, 'print("RAW",1)')
frame = frame + 250
chord(frame, field(12, 0x80), field(10, 0x04)) -- Ctrl+D executes raw source.
frame = frame + 150
expect('RAW 1')
chord(frame, field(12, 0x80), field(13, 0x80)) -- Ctrl+B: friendly REPL.
frame = frame + 100
expect('MicroPython')
chord(frame, field(12, 0x80), field(10, 0x08)) -- Ctrl+E: paste mode.
frame = frame + 100
expect('paste mode')
text(frame, 'print("PASTE",1)\r')
frame = frame + 300
chord(frame, field(12, 0x80), field(10, 0x04))
frame = frame + 150
expect('PASTE 1')
chord(frame, field(12, 0x80), field(10, 0x08))
frame = frame + 100
text(frame, 'unfinished paste')
frame = frame + 260
chord(frame, field(12, 0x80), field(10, 0x40)) -- Cancel paste.
frame = frame + 100
enter('print("FRIENDLY",1)', 'FRIENDLY 1')
-- Terminal controls must pass through Python output, not appear as text.
enter('print(chr(27),"[2J",chr(27),"[HVT100",sep="")')
at(frame, function() assert(lcd():sub(1,5)=='VT100', 'clear/home escape was not interpreted') end)
frame = frame + 20
enter('print(chr(27),"[2;5HAT",sep="")')
at(frame, function()
    local row2 = lcd():match("^[^\n]*\n([^\n]*)")
    assert(row2:sub(5,6)=='AT', 'absolute cursor position failed')
end)
frame = frame + 20
enter('print(chr(27),"[2;5H",chr(27),"[K",sep="")')
at(frame, function()
    local row2 = lcd():match("^[^\n]*\n([^\n]*)")
    assert(row2:sub(5,6)=='  ', 'erase line failed')
    pass(); bench_exit()
end)
run()

print("SCHEDULE final="..frame)

end
local ok,err=pcall(experiment);if not ok then print("FAIL setup: "..tostring(err));bench_exit() end

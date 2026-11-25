local machine=manager.machine;local cpu=machine.devices[':maincpu'];local memory=cpu.spaces.program
io.stdout:setvbuf('no')
local lcd=dofile(lcd_module)
local function eq(a,b,why)assert(a==b,(why or '')..string.format(' %x ~= %x',a,b))end
local function dump(name,a,n)local f=assert(io.open(capture_directory..'/'..name,'wb'));local t={};for i=0,n-1 do t[#t+1]=string.char(memory:read_u8(a+i))end;f:write(table.concat(t));f:close()end
local function bytes(a,n)local t={};for i=0,n-1 do t[#t+1]=string.char(memory:read_u8(a+i))end;return table.concat(t)end
local function key(name)for row=0,15 do for _,f in pairs(machine.ioport.ports[':ROW'..row].fields)do if f.name:sub(1,#name+2)==name..' ['then return f end end end;error('key '..name)end
local frame,phase,index,probe,editor,last,stable,start=0,'boot',1,nil,nil,nil,0,0
local events={};local function press(t,names)if type(names)=='string'then names={names}end;events[t]=function()for _,n in ipairs(names)do key(n):set_value(1)end end;events[t+4]=function()for _,n in ipairs(names)do key(n):clear_value()end end end
press(150,'Y');press(360,'Enter');press(700,{'Left Ctrl','Left Alt','Command','F'});press(850,'Home');press(920,'End');press(990,'Enter')
local function app(id)for i=1,31 do local p=memory:read_u32(0xe0a+4*i);if p>=0x400000 and p<0x800000 and memory:read_u16(p+20)==id then return i,p,memory:read_u32(0x355e+4*i)end end end
local function source()return bytes(probe+92,memory:read_u32(probe+68))end
local held,mods,keyindex,sequence,baseline,hold_for
local perf,timing_tap;local timings={}
local function begin_keys()
 local check=checks[index];if check.seed then memory:write_u32(seed,check.seed)end;if check.command~=nil then memory:write_u32(probe+8,check.command)end
 sequence=check.keys;keyindex=1;phase='press';start=frame;baseline=memory:read_u32(probe+28)
end
local saved,ram,original_mode,samples,sample_sig
local scratch,code,stack=0x3f000,0x3ff00,0x3fe00
local regs={'D0','D1','D2','D3','D4','D5','D6','D7','A0','A1','A2','A3','A4','A5','A6','SP','PC','SR'}
local function callmode(n)memory:write_u16(code,0xa018);memory:write_u16(code+2,0x60fe);memory:write_u32(stack,code+2);memory:write_u32(stack+4,n);cpu.state.SR.value=0x2700;cpu.state.SP.value=stack;cpu.state.PC.value=code end
local function returned()return cpu.state.PC.value==code+2 or cpu.state.PC.value==code+4 end
local function capture()
 local check=checks[index]
 local x,y=memory:read_u16(editor+60),memory:read_u16(editor+62)
 if check.preview==1 then eq(memory:read_u8(0x48be),12,'preview cursor hidden');assert(memory:read_u16(0x5c72)<264 and memory:read_u16(0x5c74)<64,'hidden overlay cursor bounds')else eq(memory:read_u16(0x5c72),x,'cursor x');eq(memory:read_u16(0x5c74),y,'cursor y')end;assert(x<264 and y<64,'cursor bounds')
 if check.x then eq(x,check.x,'expected cursor x')end
 if check.y then eq(y,check.y,'expected cursor y')end
 if check.selection then assert(memory:read_u16(editor+54)~=0,'selection absent')end
 local record=memory:read_u32(0x34d2)
 assert(record>=0x1000 and record<0x80000,'current record')
 local n=memory:read_u32(record+4);assert(n<4096,'file bound');dump(string.format('file-%02d.bin',index),memory:read_u32(record),n)
 if perf_offset and perf_offset~=0 then dump(string.format('perf-%02d.bin',index),perf,32)end
 dump(string.format('editor-%02d.bin',index),editor,94);dump(string.format('probe-%02d.bin',index),probe,484)
 local f=assert(io.open(string.format('%s/state-%02d.json',capture_directory,index),'w'))
 f:write(string.format('{"x":%d,"y":%d,"length":%d,"caret":%d,"gap_start":%d,"gap_end":%d,"flags":%d,"selection":%d,"hotkeys":%d,"preview":%d}',x,y,n,memory:read_u32(editor+36),memory:read_u32(editor+40),memory:read_u32(editor+44),memory:read_u16(editor+28),memory:read_u16(editor+54),memory:read_u32(probe+28),memory:read_u32(probe+32)));f:close()
 if check.empty_file then
  eq(memory:read_u16(editor+54),0,'selection cleared');eq(memory:read_u16(editor+28),0,'caret styles cleared')
  local raw=bytes(memory:read_u32(record),n);local first=memory:read_u32(editor+40);local lastgap=memory:read_u32(editor+44)
  assert(raw:sub(1,first)..raw:sub(lastgap+1)=='','encoded source not empty')
 end
 if check.same_size then eq(memory:read_u32(probe+44),memory:read_u32(probe+72),'same size');eq(memory:read_u32(probe+48),memory:read_u32(probe+76),'same caret');eq(memory:read_u32(probe+52),memory:read_u32(probe+80),'same gap start');eq(memory:read_u32(probe+56),memory:read_u32(probe+84),'same gap end')end
 if check.clip then local len=memory:read_u32(probe+348);assert(bytes(probe+352,len)==check.clip,'clipboard text mismatch')end
 if check.raw_keyboard then
  local raw=bytes(memory:read_u32(record),n):gsub(string.char(0xa7),'')
  assert(raw:find(string.char(0xb0,0xb1,0xb0),1,true),'keyboard B1 not escaped')
  assert(raw:find(string.char(0xb0,0xb2,0xb0),1,true),'keyboard B2 not escaped')
 end
 saved={};ram={};for _,r in ipairs(regs)do saved[r]=cpu.state[r].value end;for i=0,4095 do ram[i]=memory:read_u8(scratch+i)end
 original_mode=memory:read_u8(0x48be);callmode(12);phase='hide'
end
local failed=false
emu.register_frame_done(function()
 if failed then return end;frame=frame+1
 local ok,err=pcall(function()
 if events[frame]then events[frame]()end
 assert(frame<18000,'overall deadline')
 local sig=lcd.refresh();stable=sig==last and stable+1 or 1;last=sig
 if phase=='boot'and frame>1100 then
  local i,p,a=app(shortcut_mode and 0xa006 or private_probe_id)
  if i and a>0 and memory:read_u32(a+probe_offset)==0x4d445052 then
   probe=a+probe_offset;perf=a+(perf_offset or 0);seed=a+(seed_offset or 0)
   if perf_offset and perf_offset~=0 then timing_tap=memory:install_write_tap(perf+28,perf+29,'markdown_timing',function(offset,data,mask)
    if mask~=0 then timings[#timings+1]={check=index,key=keyindex,phase=data,time=machine.time:as_double(),message=memory:read_u32(perf+20),param=memory:read_u32(perf+24)}end
   end)end
   local ai,ap,aa=app(0xa000);editor=aa+0x12
   eq(memory:read_u32(p+16)&1,1,'hidden companion');eq(memory:read_u32(aa+0x16a),shortcut_mode and 0 or i,'AlphaWord companion lookup')
   assert(memory:read_u16(editor)~=0,'editor missing');eq(memory:read_u8(memory:read_u32(editor+78)),font_height,'font selection')
   local seen={};for j=0,3 do local face=memory:read_u32(editor+78+4*j);assert(face~=0 and not seen[face],'distinct font faces');seen[face]=true end
   print('PASS hidden companion discovery, live editor and four installed faces');begin_keys()
  end
 elseif phase=='press'and frame-start>=8 and stable>=2 and cpu.state.PC.value==0x426758 then
  local names=sequence[keyindex];hold_for=4;if type(names)=='table'and names.names then hold_for=names.frames or 4;names=names.names end;if type(names)=='string'then names={names}end
  held={};for _,n in ipairs(names)do local f=key(n);f:set_value(1);held[#held+1]=f end
  phase='release';start=frame
 elseif phase=='release'and frame-start>=hold_for then
  for _,f in ipairs(held)do f:clear_value()end
  keyindex=keyindex+1;start=frame;stable=0;last=nil
  phase=keyindex<=#sequence and 'press'or 'wait'
 elseif phase=='wait'then
  if frame%120==0 then print('WAIT',index,string.format('%x',cpu.state.PC.value),memory:read_u32(probe+12),memory:read_u32(probe+28))end
  assert(frame-start<600,string.format('checkpoint %d PC=%x SP=%x stage=%d',index,cpu.state.PC.value,cpu.state.SP.value,memory:read_u32(probe+12)))
  if frame-start>8 and stable>=3 and cpu.state.PC.value==0x426758 and (checks[index].automatic or memory:read_u32(probe+28)>baseline) then
   local check=checks[index];eq(memory:read_u32(probe+16),0,'probe operation')
   if check.text then assert(source()==check.text,'source mismatch '..source())end
   if check.reply_message then eq(memory:read_u32(probe+12),check.reply_message,'shortcut callback message')end
   if check.preview~=nil then eq(memory:read_u32(probe+32),check.preview,'preview state')end
   capture()
  end
 elseif phase=='hide'and returned()then eq(memory:read_u8(0x48be),12,'hide return');samples={};sample_sig=nil;phase='sample'
 elseif phase=='sample'then
  if sample_sig and sig~=sample_sig then samples={}end
  sample_sig=sig;samples[#samples+1]=lcd.frame()
  if #samples==3 then lcd.save(string.format('%s/checkpoint-%02d.lcd.json',capture_directory,index),samples);callmode(original_mode);phase='restore'end
 elseif phase=='restore'and returned()then
  eq(memory:read_u8(0x48be),original_mode,'restore return');for i=0,4095 do memory:write_u8(scratch+i,ram[i])end;for _,r in ipairs(regs)do cpu.state[r].value=saved[r]end
  print('PASS checkpoint '..index..' '..checks[index].name);index=index+1
  if index>#checks then local f=assert(io.open(capture_directory..'/timings.json','w'));f:write('{\"events\":[');for j,t in ipairs(timings)do if j>1 then f:write(',')end;f:write(string.format('{\"check\":%d,\"key\":%d,\"phase\":%d,\"time\":%.9f,\"message\":%d,\"param\":%d}',t.check,t.key or 0,t.phase,t.time,t.message,t.param))end;f:write(']}');f:close();print('PASS AlphaWord companion editor suite');machine:exit()else begin_keys()end
 end
 end)
 if not ok then failed=true;print('FAIL '..phase..' '..tostring(err));if probe then local r=memory:read_u32(0x34d2);if r>=0x1000 and r<0x80000 then local n=memory:read_u32(r+4);if n<32768 then dump('failure-file.bin',memory:read_u32(r),n)end end;if perf_offset and perf_offset~=0 then dump('failure-perf.bin',perf,32)end;dump('failure-probe.bin',probe,484);dump('failure-editor.bin',editor,94);dump('failure-stack.bin',cpu.state.SP.value,math.min(512,0x80000-cpu.state.SP.value))end;machine:exit()end
end)

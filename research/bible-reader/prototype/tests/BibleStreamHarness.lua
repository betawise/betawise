local machine=manager.machine
io.stdout:setvbuf('no')
local cpu=machine.devices[':maincpu'];local memory=cpu.spaces.program
local lcd=dofile(lcd_module)
local frame,index,phase=0,1,'boot'
local ram,bench
local last,stable,samples=nil,0,{}
local minimum_serial=1
local timing_tap;local timings={};local writes,start_writes=0,0;local case_writes={}
local lcd_taps={}
for _,a in ipairs({0x1000000,0x1008000})do lcd_taps[#lcd_taps+1]=memory:install_write_tap(a,a+1,'viewer_lcd_writes',function(off,data,mask)if(mask&255)~=0 then writes=writes+1 end end)end
local function work_values()local a={};if work_enabled then for i=0,3 do a[#a+1]=memory:read_u32(ram+work_offset+4*i)end end;return a end
local function save_timings()
 local f=assert(io.open(capture_directory..'/timings.json','w'));f:write('[')
 for i,t in ipairs(timings)do if i>1 then f:write(',')end;f:write(string.format('{"check":%d,"phase":%d,"time":%.12f,"work":[%s]}',t.check,t.phase,t.time,table.concat(t.work or {},",")))end
 f:write(']');f:close()
end
local menu_before,handoff,checking_font_menu,action_wait,key_serial,routing_menu
local events={};local held,mods,key_index,key_sequence,start_frame
local saved_cpu,saved_ram,original_mode
local scratch,code,stack=0x3f000,0x3ff00,0x3fe00
local regs={'D0','D1','D2','D3','D4','D5','D6','D7','A0','A1','A2','A3','A4','A5','A6','SP','PC','SR'}
local function key(name)
 for row=0,15 do for _,f in pairs(machine.ioport.ports[':ROW'..row].fields)do if f.name:sub(1,#name+2)==name..' [' then return f end end end
 error('missing key '..name)
end
local function press(t,name)events[t]=function()key(name):set_value(1)end;events[t+6]=function()key(name):clear_value()end end
press(150,'Y');press(360,'Enter');press(740,'Applets');press(850,'Down');press(980,'Enter')
local function returned()return cpu.state.PC.value==code+2 or cpu.state.PC.value==code+4 end
local function mode(n)
 memory:write_u16(code,0xa018);memory:write_u16(code+2,0x60fe);memory:write_u32(stack,code+2);memory:write_u32(stack+4,n)
 cpu.state.SR.value=0x2700;cpu.state.SP.value=stack;cpu.state.PC.value=code
end
local function dump(path,a,n)
 local f=assert(io.open(capture_directory..'/'..path,'wb'));local t={};for i=0,n-1 do t[#t+1]=string.char(memory:read_u8(a+i))end;f:write(table.concat(t));f:close()
end
local function dump_font(prefix,face)
local h,w,stride=memory:read_u8(face),memory:read_u8(face+1),memory:read_u8(face+2)
 local widths,offsets,pixels=memory:read_u32(face+4),memory:read_u32(face+8),memory:read_u32(face+12)
 local needed=0
 for c=32,126 do local width=widths~=0 and memory:read_u8(widths+c)or w;local offset=offsets~=0 and memory:read_u16(offsets+2*c)or c*stride;needed=math.max(needed,offset+((h+7)//8)*width)end
 assert(h>0 and h<=64 and w>0 and w<=64 and needed>0 and needed<=65536,'font descriptor bounds')
 dump(string.format(prefix..'-%02d.bin',index),face,16)
 if widths~=0 then dump(string.format(prefix..'-widths-%02d.bin',index),widths,256)end
 if offsets~=0 then dump(string.format(prefix..'-offsets-%02d.bin',index),offsets,512)end
 dump(string.format(prefix..'-pixels-%02d.bin',index),pixels,needed)
end
local function park()
 -- Pin a ROM instruction entry: frame-end PC can otherwise point at an
 -- extension word, which cannot safely be restored as a new opcode.
 assert(cpu.state.PC.value==0x426758 and memory:read_u16(0x426758)==0x40c0,'safe idle instruction entry')
 assert((cpu.state.SR.value&0x2000)~=0,'supervisor capture required')
 assert(memory:read_u16(0x5c72)==memory:read_u32(bench+104),'native pixel cursor x')
 assert(memory:read_u16(0x5c74)==((memory:read_u32(bench+108)+memory:read_u32(bench+112))&63),'native pixel cursor y/roll')
 assert(memory:read_u8(memory:read_u32(0x5c68))==memory:read_u32(bench+136),'native pixel cursor height')
 saved_cpu,saved_ram={},{};for _,r in ipairs(regs)do saved_cpu[r]=cpu.state[r].value end
 for i=0,4095 do saved_ram[i]=memory:read_u8(scratch+i)end
 original_mode=memory:read_u8(0x48be)
 print('PARK',index,saved_cpu.PC,saved_cpu.SP,saved_cpu.SR)
 dump(string.format('stack-%02d.bin',index),saved_cpu.SP,128)
 dump_font('font',memory:read_u32(ram+font_offset));dump_font('uifont',memory:read_u32(ram+uifont_offset))
 dump(string.format('stream-%02d.bin',index),bench,140)
 local wf=assert(io.open(string.format('%s/display-%02d.json',capture_directory,index),'w'));wf:write(string.format('{"writes":%d}',case_writes[index]or 0));wf:close()
 if checks[index].clipboard then local r=memory:read_u32(0x34da);local n=memory:read_u32(r+4);assert(n<32768);dump(string.format('clipboard-%02d.bin',index),memory:read_u32(r),n)end
 local f=assert(io.open(string.format('%s/cursor-%02d.json',capture_directory,index),'w'))
 f:write(string.format('{"x":%d,"y":%d,"mode":%d}',memory:read_u16(0x5c72),memory:read_u16(0x5c74),original_mode));f:close()
 mode(0x0c)
end
local function restored()
 local before=assert(io.open(string.format('%s/stack-%02d.bin',capture_directory,index),'rb')):read('*a')
 for i=0,127 do assert(memory:read_u8(saved_cpu.SP+i)==before:byte(i+1),'original guest stack changed by cursor calls')end
 for i=0,4095 do memory:write_u8(scratch+i,saved_ram[i])end
 for _,r in ipairs(regs)do cpu.state[r].value=saved_cpu[r]end
end
local function begin_key()
 local entry=key_sequence[key_index];if type(entry)=='string'then entry={entry}end
 mods={};for i=1,#entry-1 do local k=key(entry[i]);k:set_value(1);mods[#mods+1]=k end
 handoff=checks[index].resume and key_index==3
 menu_before=(entry[#entry]=='Applets'or handoff)and lcd.refresh()or nil
 if entry[#entry]=='F'and #entry==4 then checking_font_menu=true end
 if entry[#entry]=='Applets'then routing_menu=true end
 key_serial=memory:read_u32(bench+4);local n=entry[#entry];action_wait=not routing_menu and not checking_font_menu and memory:read_u32(bench+28)==0 and(n=='Up'or n=='Down'or n=='Left'or n=='Right'or n=='Home'or n=='End'or n=='N'or n=='P'or n=='Space')
 held=key(entry[#entry]);held:set_value(1);phase='release';start_frame=frame
end
local failed=false
emu.register_frame_done(function()
 if failed then return end;assert(#lcd_taps==2,'LCD taps retained');frame=frame+1
 local ok,err=pcall(function()
  if events[frame]then events[frame]()end
  if not bench and frame>980 then
   local candidate=cpu.state.A5.value
   if candidate>=0x1000 and candidate+reader_offset+48<0x80000 and memory:read_u32(candidate+reader_offset)==0x42535452 then ram=candidate;bench=ram+reader_offset;print('READER',ram)
    timing_tap=memory:install_write_tap(bench+8,bench+11,'reader_phase',function(offset,data,mask)
     if offset==bench+10 and(mask&65535)~=0 then if data==1 then start_writes=writes elseif data==4 then case_writes[index]=writes-start_writes end;timings[#timings+1]={check=index,phase=data,time=machine.time:as_double(),work=work_values()}end
    end)end
  end
  if not bench then assert(frame<2400,'startup deadline');return end
  assert(memory:read_u32(bench+12)==0,'reader error '..memory:read_u32(bench+12))
  local sig=lcd.refresh();if checking_font_menu then for _,c in ipairs(lcd.cache)do assert(c.m_start_line==0,'font dialog must have zero hardware roll')end end;stable=sig==last and stable+1 or 1;last=sig
  if phase=='boot'then phase='wait';start_frame=frame end
  if phase=='wait'and frame%600==0 then print('REG',cpu.state.D1.value,cpu.state.A0.value,cpu.state.A1.value,cpu.state.SP.value,memory:read_u32(cpu.state.SP.value));print('WAIT',cpu.state.PC.value,index,memory:read_u32(bench+4),memory:read_u32(bench+8),memory:read_u32(bench+28),memory:read_u32(bench+32))end
  assert(frame-start_frame<7200,'bounded stage '..index..' '..phase)
  if phase=='wait'then
   local check=checks[index]
   if memory:read_u32(bench+8)==4 and memory:read_u32(bench+4)>=minimum_serial and memory:read_u32(bench+28)==(check.mode or 0) and memory:read_u32(bench+32)==0 and stable>=3 and cpu.state.PC.value==0x426758 then
    if check.chapter then assert(memory:read_u32(bench+16)==check.chapter,'wrong chapter')end
    if check.page then assert(memory:read_u32(bench+48)==check.page,'wrong page')end
    if check.verse then assert(memory:read_u32(bench+20)==check.verse,'wrong verse '..memory:read_u32(bench+20))end
    if check.numbered~=nil then assert(memory:read_u32(bench+44)==check.numbered,'number toggle')end
    checking_font_menu=false;routing_menu=false;park();phase='hide';start_frame=frame
   end
  elseif phase=='hide'and returned()then
   assert(memory:read_u8(0x48be)==0x0c,'hide return/mode');phase='samples';samples={};last=nil
  elseif phase=='samples'then
   if #samples>0 and sig~=sample_signature then samples={}end
   sample_signature=sig;samples[#samples+1]=lcd.frame()
   if #samples==3 then lcd.save(string.format('%s/checkpoint-%02d.lcd.json',capture_directory,index),samples);mode(original_mode);phase='restore'end
  elseif phase=='restore'and returned()then
   assert(memory:read_u8(0x48be)==original_mode,'restore mode');restored();print('PASS checkpoint '..index..' '..checks[index].name)
   if index==#checks then print('PASS BibleReader suite');save_timings();machine:exit();return end
   minimum_serial=memory:read_u32(bench+4)+1;index=index+1;key_sequence=checks[index].keys;key_index=1;begin_key()
  elseif phase=='release'and frame-start_frame>=3 then
   held:clear_value();for _,k in ipairs(mods)do k:clear_value()end
   phase=key_index<#key_sequence and 'gap' or 'wait';start_frame=frame;stable=0;last=nil
  elseif phase=='gap'and frame-start_frame>=8 and (not menu_before or(sig~=menu_before and stable>=3 )) and(not handoff or memory:read_u8(0x48be)==15)and(not action_wait or(memory:read_u32(bench+8)==4 and memory:read_u32(bench+4)>key_serial and cpu.state.PC.value==0x426758))then key_index=key_index+1;begin_key()end
 end)
 if not ok then failed=true;save_timings();print('FAIL BibleReader '..tostring(err));if bench then dump('failure-metrics.bin',bench,48);dump('failure-stream.bin',bench,140)end;lcd.refresh();lcd.save(capture_directory..'/failure.lcd.json',{lcd.frame()});machine:exit()end
end)

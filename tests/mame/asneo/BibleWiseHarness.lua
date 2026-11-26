local machine=manager.machine
io.stdout:setvbuf('no')
local cpu=machine.devices[':maincpu'];local memory=cpu.spaces.program
local lcd=dofile(lcd_module)
local frame,index,phase=0,1,'boot'
local ram,bench,editor
local last,stable,samples=nil,0,{}
local minimum_serial=1
local busy_samples,busy_signature,busy_saved={},nil,{}
local loading_samples,loading_signature,loading_saved={},nil,false
local stack_tap;local stack_lows={};local timing_tap;local timings={};local lcd_writes=0;local lcd_taps={}

local function save_timings()
 local f=assert(io.open(capture_directory..'/timings.json','w'));f:write('[')
 for i,t in ipairs(timings)do
  if i>1 then f:write(',')end
  f:write(string.format('{"check":%d,"phase":%d,"time":%.12f,"lcd_writes":%d,"file_bytes":%d,"caret":%d,"viewport":%d,"caret_y":%d}',t.check,t.phase,t.time,t.lcd_writes,t.file_bytes,t.caret,t.viewport,t.caret_y))
 end
 f:write(']');f:close()
 if profile_stack then
  local out=assert(io.open(capture_directory..'/stack-lows.json','w'));out:write('[')
  for i=1,#checks do if i>1 then out:write(',') end;out:write(string.format('{"check":%d,"min_sp":%d}',i,stack_lows[i] or 0)) end
  out:write(']');out:close()
 end
end
local menu_before,handoff
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
if startup_system_font then
 -- A test-only entry hook opens the original system picker before reader init.
 press(1200,'End');press(1320,'Enter')
end
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
 for c=0,255 do local width=widths~=0 and memory:read_u8(widths+c)or w;local offset=offsets~=0 and memory:read_u16(offsets+2*c)or c*stride;needed=math.max(needed,offset+((h+7)//8)*width)end
 assert(h>0 and h<=64 and w>0 and w<=64 and needed>0 and needed<=65536,'font descriptor bounds')
 dump(string.format(prefix..'-%02d.bin',index),face,16)
 if widths~=0 then dump(string.format(prefix..'-widths-%02d.bin',index),widths,256)end
 if offsets~=0 then dump(string.format(prefix..'-offsets-%02d.bin',index),offsets,512)end
 dump(string.format(prefix..'-pixels-%02d.bin',index),pixels,needed)
end
-- Test oracle for the pinned Neo 3.21 fixture only. The applet itself obtains
-- names/indices through syscalls and never reads this RAM table.
local function applet_header_id(index)
 if index==0 then return 0 end
 if index==32 then return 0x10000 end
 assert(index>0 and index<32,'font applet index')
 return memory:read_u16(memory:read_u32(0x0e0a+4*index)+0x14)
end
local function park()
 -- Pin a ROM instruction entry: frame-end PC can otherwise point at an
 -- extension word, which cannot safely be restored as a new opcode.
 assert(cpu.state.PC.value==0x426758 and memory:read_u16(0x426758)==0x40c0,'safe idle instruction entry')
 assert((cpu.state.SR.value&0x2000)~=0,'supervisor capture required')
 -- Cursor geometry remains independent of pixel assertions. Full-screen
 -- forms reset the console cursor, while status/copy preserve native geometry.
 local check=checks[index]
 if check.family_picker then
  assert(memory:read_u16(0x5c72)==0 and memory:read_u16(0x5c74)==0,'font-dialog preserved console cursor geometry '..memory:read_u16(0x5c72)..','..memory:read_u16(0x5c74))
 elseif check.font_menu then
  assert(memory:read_u16(0x5c72)==12,'font menu cursor column '..memory:read_u16(0x5c72)..' row '..memory:read_u16(0x5c74)..' choice '..memory:read_u8(0x3ebf)..' top '..memory:read_u8(0x3eba))
  local top=memory:read_u8(0x3eba);local choice=memory:read_u8(0x3ebf)
  assert(memory:read_u16(0x5c74)==(1+choice-top)*16,'font menu cursor row')
 elseif check.mode==2 then
  assert(memory:read_u16(0x5c72)==54+#check.find_form.text*6 and memory:read_u16(0x5c74)==0,'native TextBox cursor geometry '..memory:read_u16(0x5c72)..','..memory:read_u16(0x5c74)..' origin '..memory:read_u16(0x5c70)..' bytes '..memory:read_u8(ram+input_offset)..','..memory:read_u8(ram+input_offset+1)..' font '..string.format('%x',memory:read_u32(0x5c68)))
  assert(memory:read_u32(0x5c68)==0x44af8e,'native TextBox system font')
 elseif check.mode==3 and not check.clipboard then
  assert(memory:read_u16(0x5c72)==0 and memory:read_u16(0x5c74)==0,'dialog cursor reset')
 else
  assert(memory:read_u16(0x5c72)==memory:read_u16(editor+0x3c),'cursor x/editor mismatch')
  assert(memory:read_u16(0x5c74)==memory:read_u16(editor+0x3e),'cursor y/editor mismatch')
 end
 assert(memory:read_u16(0x5c72)<264 and memory:read_u16(0x5c74)<64,'cursor out of viewport')
 saved_cpu,saved_ram={},{};for _,r in ipairs(regs)do saved_cpu[r]=cpu.state[r].value end
 for i=0,4095 do saved_ram[i]=memory:read_u8(scratch+i)end
 original_mode=memory:read_u8(0x48be)
 if checks[index].profile_offsets then
  assert(memory:read_u32(bench+68)==1,'reconstructed verse tables differ from decoder tables')
  dump(string.format('offset-rebuild-%02d.bin',index),bench+64,8)
 end
 dump(string.format('file-lifecycle-%02d.bin',index),bench+64,8)
 dump(string.format('editor-%02d.bin',index),editor,94)
 dump_font('font',memory:read_u32(editor+0x4e))
 if checks[index].rich then
  dump(string.format('options-%02d.bin',index),ram+settings_offset,3)
  if checks[index].family_picker then
   dump(string.format('picker-%02d.bin',index),ram+picker_offset,6)
  end
  if checks[index].font_menu then
   local f=assert(io.open(string.format('%s/font-menu-%02d.json',capture_directory,index),'w'))
   f:write(string.format('{"top":%d,"choice":%d,"count":%d}',memory:read_u8(0x3eba),memory:read_u8(0x3ebf),memory:read_u8(0x3eb8)));f:close()
  end
  local counters=assert(io.open(string.format('%s/counters-%02d.json',capture_directory,index),'w'))
  counters:write(string.format('{"sidebar_draws":%d,"chapter_decodes":%d}',memory:read_u32(bench+56),memory:read_u32(bench+60)));counters:close()
  if checks[index].local_ui then
   local f=assert(io.open(string.format('%s/font-preference-%02d.json',capture_directory,index),'w'))
   f:write(string.format('{"system":%d,"reader":%d}',memory:read_u16(0x5c8a),applet_header_id(memory:read_u16(ram+settings_offset+4))));f:close()
  end
  dump_font('boldfont',memory:read_u32(editor+0x52))
  dump_font('italicfont',memory:read_u32(editor+0x56))
  dump_font('privatefont',memory:read_u32(editor+0x5a))
  local record=memory:read_u32(0x34d2)
  assert(memory:read_u16(record+0x44)==1,'reader file record')
  local ptr,n=memory:read_u32(record),memory:read_u32(record+4)
  assert(ptr>=0x1000 and n<66048 and ptr+n<=0x80000,'native chapter buffer bounds')
  dump(string.format('chapter-%02d.bin',index),ptr,n)
 end
 dump_font('sidebarfont',sidebar_font_address)
 if checks[index].find_form then
  dump(string.format('find-%02d.bin',index),ram+input_offset,33)
 end
 dump(string.format('metrics-%02d.bin',index),bench,48)
 local notice=memory:read_u8(ram+search_notice_offset)
 if notice~=0 then
  local f=assert(io.open(string.format('%s/search-notice-%02d.json',capture_directory,index),'w'))
  f:write(string.format('{"notice":%d,"dots":%d}',notice,memory:read_u32(ram+busy_dots_offset)));f:close()
 end
 local f=assert(io.open(string.format('%s/cursor-%02d.json',capture_directory,index),'w'))
 f:write(string.format('{"x":%d,"y":%d,"mode":%d}',memory:read_u16(0x5c72),memory:read_u16(0x5c74),original_mode));f:close()
 if checks[index].resume then
  dump(string.format('saved-%02d.bin',index),ram+saved_offset,20)
 end
 if checks[index].clipboard then
  if copy_probe_offset and copy_probe_offset>0 then
   dump(string.format('copy-relocation-%02d.bin',index),ram+copy_probe_offset,32)
  end
  local record=memory:read_u32(0x34da);local n=memory:read_u32(record+4);local ptr=memory:read_u32(record)
  assert(record>=0x1000 and record<0x80000 and n<32768 and ptr>=0x1000 and ptr+n<0x80000,'clipboard geometry')
  dump(string.format('clipboard-%02d.bin',index),ptr,n)
 end
 mode(0x0c)
end
local function restored()
 for i=0,4095 do memory:write_u8(scratch+i,saved_ram[i])end
 for _,r in ipairs(regs)do cpu.state[r].value=saved_cpu[r]end
end
local function begin_key()
 if not key_sequence[key_index]then phase='wait';start_frame=frame;return end
 local entry=key_sequence[key_index]
 if type(entry)=='table'and entry.key then
  if entry.wait_status and(memory:read_u8(ram+status_offset)~=1 or memory:read_u32(bench+8)~=4 or stable<3)then phase='key-wait';return end
  entry={entry.key}
 end
 if type(entry)=='string'then entry={entry}end
 mods={};for i=1,#entry-1 do local k=key(entry[i]);k:set_value(1);mods[#mods+1]=k end
 handoff=checks[index].resume and key_index==(checks[index].handoff_key_index or 3)
 menu_before=(entry[#entry]=='Applets'or handoff)and lcd.refresh()or nil
 if checks[index].family_picker then
  timings[#timings+1]={check=index,phase=600,time=machine.time:as_double(),lcd_writes=lcd_writes,file_bytes=0,caret=0,viewport=0,caret_y=0}
 end
 held=key(entry[#entry]);held:set_value(1);phase='release';start_frame=frame
end
local cancel_started,cancel_sent={},{}
local failed=false
emu.register_frame_done(function()
 if failed then return end;frame=frame+1
 local ok,err=pcall(function()
  if events[frame]then events[frame]()end
  if not bench and frame>980 then
   local candidate=cpu.state.A5.value
   if candidate>=0x1000 and candidate+reader_offset+48<0x80000 and memory:read_u32(candidate+reader_offset)==0x42524452 then ram=candidate;bench=ram+reader_offset;editor=ram+editor_offset;print('READER',ram)
    -- Install after firmware startup remapping, like the phase tap.
    if profile_stack then
     stack_tap=memory:install_write_tap(0x70000,0x7ffff,'reader_stack_low',function(off,data,mask)
      local sp=cpu.state.SP.value
      if sp>=0x70000 and off>=sp-16 and off<sp+32 then
       stack_lows[index]=math.min(stack_lows[index] or sp,sp)
      end
     end)
    end
    for _,a in ipairs({0x1000000,0x1008000})do lcd_taps[#lcd_taps+1]=memory:install_write_tap(a,a+1,'native_reader_lcd_writes',function(off,data,mask)if(mask&255)~=0 then lcd_writes=lcd_writes+1 end end)end
    timing_tap=memory:install_write_tap(bench+8,bench+11,'reader_phase',function(offset,data,mask)
     if offset==bench+10 and(mask&65535)~=0 then
      timings[#timings+1]={check=index,phase=data,time=machine.time:as_double(),lcd_writes=lcd_writes,file_bytes=memory:read_u32(bench+24),caret=memory:read_u32(editor+36),viewport=memory:read_u32(editor+24),caret_y=memory:read_u16(editor+62)}
     end
    end)end
  end
  if not bench then assert(frame<2400,'startup deadline');return end
  assert(memory:read_u32(bench+12)==0,'reader error '..memory:read_u32(bench+12))
  local sig=lcd.refresh();stable=sig==last and stable+1 or 1;last=sig
  if bench and memory:read_u8(ram+busy_offset)==1 and memory:read_u8(0x48be)==12 then
   local serial=memory:read_u32(ram+busy_dots_offset)
   if serial>0 and not busy_saved[serial]then
   local signature=sig..':'..serial
   if signature~=busy_signature then busy_samples={}end
   busy_signature=signature;busy_samples[#busy_samples+1]=lcd.frame()
   if #busy_samples==3 then
    lcd.save(capture_directory..'/busy-'..serial..'.lcd.json',busy_samples);busy_saved[serial]=true
    dump_font('sidebarfont',sidebar_font_address)
    local f=assert(io.open(capture_directory..'/busy-meta-'..serial..'.json','w'));f:write(string.format('{"index":%d,"dots":%d}',index,serial));f:close()
   end
  end
  end
  if bench and index>1 and not loading_saved and memory:read_u32(bench+8)==3 and
   memory:read_u8(ram+busy_offset)==1 and memory:read_u32(ram+busy_dots_offset)==0 then
   local chapter=memory:read_u16(ram+chapter_offset)
   local signature=sig..':'..chapter
   if loading_signature~=signature then loading_samples={}end
   loading_signature=signature;loading_samples[#loading_samples+1]=lcd.frame()
   if #loading_samples==3 then
    lcd.save(capture_directory..'/loading.lcd.json',loading_samples);loading_saved=true
    local f=assert(io.open(capture_directory..'/loading-meta.json','w'))
    f:write(string.format('{"index":%d,"chapter":%d}',index,chapter));f:close()
   end
  end
  if phase=='boot'then phase='wait';start_frame=frame end
  assert(frame-start_frame<7200,'bounded stage '..index..' '..phase)
  if phase=='wait'then
   local check=checks[index]
   if check.cancel_after_frames and memory:read_u32(bench+32)==1 then
    if not cancel_started[index]then cancel_started[index]=frame end
    if not cancel_sent[index]and frame-cancel_started[index]>=check.cancel_after_frames then
     cancel_sent[index]=machine.time:as_double();key('Escape'):set_value(1);events[frame+6]=function()key('Escape'):clear_value()end
     print('CANCEL_SENT',index,cancel_sent[index])
    end
   end
   if cancel_sent[index]and frame%60==0 then print('CANCEL_TRACE',frame,cpu.state.PC.value,cpu.state.SR.value,cpu.state.SP.value,memory:read_u32(bench+8),memory:read_u32(bench+28),memory:read_u32(bench+32))end
   local field_ready=true
   if check.font_menu then field_ready=memory:read_u8(0x3ebf)==check.font_menu end
   if check.family_picker then
    local a=ram+picker_offset;local id=memory:read_u16(a)
    field_ready=applet_header_id(id)==check.family_picker.id and memory:read_u8(a+4)==check.family_picker.target
    assert(memory:read_u16(a+2)<=32 and memory:read_u8(a+5)<6,'uncached viewport state')
   end
   if check.search_notice then field_ready=field_ready and memory:read_u8(ram+search_notice_offset)==check.search_notice end
   if check.find_form then
    local text='';for i=0,32 do local c=memory:read_u8(ram+input_offset+i);if c==0 then break end;text=text..string.char(c)end
    field_ready=text==check.find_form.text
   end
   if field_ready and frame-start_frame>=(check.wait_frames or 0)and memory:read_u32(bench+8)==4 and (check.find_form or check.font_menu or check.family_picker or memory:read_u32(bench+4)>=minimum_serial) and memory:read_u32(bench+28)==(check.mode or 0) and memory:read_u32(bench+32)==0 and memory:read_u8(ram+status_offset)==(check.status and 1 or 0) and stable>=3 and cpu.state.PC.value==0x426758 then
    if check.chapter then assert(memory:read_u32(bench+16)==check.chapter,'wrong chapter '..memory:read_u32(bench+16)..' expected '..check.chapter..' verse '..memory:read_u32(bench+20))end
    if check.verse then assert(memory:read_u32(bench+20)==check.verse,'wrong verse '..memory:read_u32(bench+20))end
    if check.numbered~=nil then assert(memory:read_u32(bench+44)==check.numbered,'number toggle')end
    if check.cancel_after_frames then assert(cancel_sent[index],'cancel key was never injected');print('CANCEL_DONE',index,machine.time:as_double()-cancel_sent[index])end
    park();phase='hide';start_frame=frame
   end
  elseif phase=='hide'and returned()then
   assert(memory:read_u8(0x48be)==0x0c,'hide return/mode');phase='samples';samples={};last=nil
  elseif phase=='samples'then
   if #samples>0 and sig~=sample_signature then samples={}end
   sample_signature=sig;samples[#samples+1]=lcd.frame()
   if #samples==3 then lcd.save(string.format('%s/checkpoint-%02d.lcd.json',capture_directory,index),samples);mode(original_mode);phase='restore'end
  elseif phase=='restore'and returned()then
   assert(memory:read_u8(0x48be)==original_mode,'restore mode');restored();print('PASS checkpoint '..index..' '..checks[index].name)
   if index==#checks then print('PASS BibleWise suite');save_timings();machine:exit();return end
   minimum_serial=memory:read_u32(bench+4)+1;index=index+1;key_sequence=checks[index].keys;
   if not key_sequence or #key_sequence==0 then minimum_serial=minimum_serial-1 end
   phase='case-gap';start_frame=frame
  elseif phase=='key-wait'then begin_key()
  elseif phase=='case-gap'and frame-start_frame>=8 then key_index=1;begin_key()
  elseif phase=='release'and frame-start_frame>=3 then
   held:clear_value();for _,k in ipairs(mods)do k:clear_value()end
   phase=key_index<#key_sequence and 'gap' or 'wait';start_frame=frame;stable=0;last=nil
  elseif phase=='gap'and frame-start_frame>=8 and (not menu_before or(sig~=menu_before and stable>=3 and memory:read_u32(bench+8)~=15)) and(not handoff or memory:read_u8(0x48be)==15)then key_index=key_index+1;begin_key()end
 end)
 if not ok then failed=true;print('FAIL BibleWise '..tostring(err));if bench then print('STATE',index,memory:read_u32(bench+8),memory:read_u32(bench+28),memory:read_u32(bench+32),memory:read_u32(bench+4),minimum_serial,cpu.state.PC.value)end;save_timings();machine:exit()end
end)

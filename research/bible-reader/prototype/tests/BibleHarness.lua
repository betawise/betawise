-- Bootstrap supplies exact expected text/font and applet-relative symbol offsets.
local machine=manager.machine
io.stdout:setvbuf('no')
local cpu=machine.devices[":maincpu"]
local memory=cpu.spaces.program
local lcd=dofile(lcd_module)
local frame,index,phase=0,1,'boot'
local bench,ram,tap
local samples,last,stable={},nil,0
local events,timings={},{}
local start_frame,held,modifier
local key_sequence,key_index
local parked,original_mode,saved_cpu,saved_ram
local scratch,code,stack=0x3f000,0x3ff00,0x3fe00
local regs={'D0','D1','D2','D3','D4','D5','D6','D7','A0','A1','A2','A3','A4','A5','A6','SP','PC','SR'}
local function now() return machine.time:as_double() end
local function cpu_clock()
    -- Same read-only PLL equation as the emulated VZ core; no clock writes.
    local control=memory:read_u16(0xfffff200)
    local frequency=memory:read_u16(0xfffff202)
    local hz=2*(14*((frequency&255)+1)+((frequency>>8)&15)+1)*32768
    if(control&0x80)~=0 then hz=hz//2 end
    if(control&0x20)~=0 then hz=hz//2 end
    local n=(control>>8)&7
    if n<4 then hz=hz//(2<<n) end
    return hz
end
local function key(name)
    for row=0,15 do for _,f in pairs(machine.ioport.ports[":ROW"..row].fields) do
        if f.name:sub(1,#name+2)==name..' [' then return f end
    end end
    error('missing Neo key '..name)
end
local function press(t,name)
    events[t]=function() key(name):set_value(1) end
    events[t+6]=function() key(name):clear_value() end
end
press(150,'Y');press(360,'Enter');press(740,'Applets');press(850,'Down');press(980,'Enter')
local function mode(n)
    memory:write_u16(code,0xa018);memory:write_u16(code+2,0x60fe)
    memory:write_u32(stack,code+2);memory:write_u32(stack+4,n)
    cpu.state.SR.value=0x2700;cpu.state.SP.value=stack;cpu.state.PC.value=code
end
local function returned() return cpu.state.PC.value==code+2 or cpu.state.PC.value==code+4 end
local function park()
    assert((cpu.state.SR.value&0x2000)~=0,'capture must be supervisor context')
    saved_cpu,saved_ram={},{}
    for _,r in ipairs(regs) do saved_cpu[r]=cpu.state[r].value end
    for n=0,4095 do saved_ram[n]=memory:read_u8(scratch+n) end
    original_mode=memory:read_u8(0x48be)
    -- Independent physical cursor geometry before any capture-time hide call.
    assert(memory:read_u16(0x5c72)==0 and memory:read_u16(0x5c74)==56,'cursor geometry mismatch')
    mode(0x0c);parked=true
end
local function restore()
    for n=0,4095 do memory:write_u8(scratch+n,saved_ram[n]) end
    for _,r in ipairs(regs) do cpu.state[r].value=saved_cpu[r] end
    parked=false
end
local function decode()
    local lines={}
    for y=0,56,8 do
        local chars={}
        for x=0,258,6 do
            local bits=0
            for dy=0,7 do for dx=0,5 do bits=(bits<<1)|(lcd.black(x+dx,y+dy) and 1 or 0) end end
            assert(font[bits],'unknown/ambiguous glyph at '..x..','..y)
            chars[#chars+1]=font[bits]
        end
        lines[#lines+1]=table.concat(chars):gsub(' +$','')
    end
    return table.concat(lines,'\n'):gsub('\n+$','')
end
local function save_timings()
    local f=assert(io.open(capture_directory..'/timings.json','w'))
    f:write('[')
    for i,t in ipairs(timings) do
        if i>1 then f:write(',') end
        f:write(string.format('{"serial":%d,"phase":%d,"emulated_seconds":%.12f,"cpu_clock":%d}',t.serial,t.phase,t.time,t.clock))
    end
    f:write(']\n');f:close()
end
local function discover()
    local candidate=cpu.state.A5.value
    if frame==1150 then
        for address=0x1000,0x7ffbc,2 do
            if memory:read_u32(address)==0x4249424c then print(string.format('FOUND BIBLE magic=%x',address));candidate=address-bench_offset;break end
        end
        print(string.format('PROBE a5=%x magic=%x',cpu.state.A5.value,memory:read_u32(cpu.state.A5.value+bench_offset)))
    end
    if candidate<0x1000 or candidate+bench_offset+64>=0x80000 then return end
    if memory:read_u32(candidate+bench_offset)~=0x4249424c then return end
    ram=candidate;bench=ram+bench_offset
    print(string.format('BIBLE_RAM base=%x bench=%x workspace=%d',ram,bench,memory:read_u32(bench+52)))
    tap=memory:install_write_tap(bench+8,bench+11,'bible_phase',function(offset,data,mask)
        if offset==bench+10 and (mask&0xffff)~=0 and data>=1 and data<=5 then
            local clock=cpu_clock()
            timings[#timings+1]={serial=memory:read_u32(bench+4),phase=data,time=now(),clock=clock}
        end
    end)
end
local function metrics()
    local values={}
    for n=0,15 do values[#values+1]=memory:read_u32(bench+4*n) end
    local f=assert(io.open(string.format('%s/metrics-%02d.json',capture_directory,index),'w'))
    f:write('['..table.concat(values,',')..']\n');f:close()
end
local failed=false
emu.register_frame_done(function()
    if failed then return end
    frame=frame+1
    local ok,err=pcall(function()
        if events[frame] then events[frame]() end
        if not bench and frame%300==0 then print(string.format('BOOT frame=%d PC=%x A5=%x mode=%x',frame,cpu.state.PC.value,cpu.state.A5.value,memory:read_u8(0x48be))) end
        if not bench and frame>980 then discover() end
        local signature=lcd.refresh()
        stable=signature==last and stable+1 or 1;last=signature
        if not bench then assert(frame<2400,'applet startup timeout');return end
        assert(memory:read_u32(bench+48)==0,'native decoder error '..memory:read_u32(bench+48))
        if phase=='boot' then phase='wait';start_frame=frame end
        assert(frame-start_frame<7200,'bounded stage timeout '..phase)
        if phase=='wait' then
            if memory:read_u32(bench+8)==4 and stable>=3 and
               memory:read_u32(bench+4)>=checks[index].serial then
                assert(decode()==checks[index].equals,'screen text mismatch: '..decode())
                park();phase='hide';start_frame=frame
            end
        elseif phase=='hide' then
            if returned() then
                assert(memory:read_u8(0x48be)==0x0c,'firmware cursor hide failed')
                phase='samples';samples={};last=nil;start_frame=frame
            end
        elseif phase=='samples' then
            if #samples>0 and signature~=sample_signature then samples={} end
            sample_signature=signature;samples[#samples+1]=lcd.frame()
            if #samples==3 then
                assert(decode()==checks[index].equals,'captured screen mismatch')
                lcd.save(string.format('%s/checkpoint-%02d.lcd.json',capture_directory,index),samples)
                if checks[index].full then
                    local bytes={}
                    for i=0,checks[index].byte_count-1 do bytes[#bytes+1]=string.char(memory:read_u8(ram+cache_offset+i)) end
                    local f=assert(io.open(string.format('%s/cache-%02d.bin',capture_directory,index),'wb'))
                    f:write(table.concat(bytes));f:close()
                end
                metrics();save_timings();mode(original_mode);phase='restore';start_frame=frame
            end
        elseif phase=='restore' then
            if returned() then
                assert(memory:read_u8(0x48be)==original_mode,'cursor restore failed');restore()
                print('PASS Bible checkpoint '..index..' '..checks[index].name)
                if index==#checks then print('PASS Bible benchmark completed');save_timings();machine:exit();return end
                index=index+1
                key_sequence=checks[index].keys or {checks[index].key};key_index=1
                held=key(key_sequence[key_index]);held:set_value(1)
                start_frame=frame;phase='release'
            end
        elseif phase=='release' then
            if frame-start_frame>=3 then
                held:clear_value()
                if key_index<#key_sequence then phase='gap' else phase='wait';start_frame=frame end
            end
        elseif phase=='gap' then
            if frame-start_frame>=8 then
                key_index=key_index+1;held=key(key_sequence[key_index]);held:set_value(1)
                phase='release';start_frame=frame
            end
        end
    end)
    if not ok then
        failed=true;print('FAIL Bible: '..tostring(err));save_timings()
        lcd.save(capture_directory..'/failure.lcd.json',{lcd.frame()});machine:exit()
    end
end)

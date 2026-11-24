-- Capture a NEW disposable AS3000 input after normal firmware initialization.
-- No saved user state or historical .research-work capture is an input.
local out = assert(os.getenv('AS3K_FIXTURE_OUT'), 'Set AS3K_FIXTURE_OUT')
local machine = manager.machine
local cpu = machine.devices[':maincpu']
local memory = cpu.spaces.program
local state = cpu.state
local frames = 0
local done = false
local function exists(name)
    local file = io.open(out .. '/' .. name, 'rb')
    if file then file:close(); return true end
    return false
end
local function dump(name, first, length)
    local file = assert(io.open(out .. '/' .. name, 'wb'))
    for address = first, first + length - 1 do
        file:write(string.char(memory:read_u8(address)))
    end
    file:close()
end
emu.register_frame_done(function()
    if done then return end
    local ok, failure = pcall(function()
    frames = frames + 1
    assert(frames < 60 * 1800, 'Disposable fixture preparation deadline')
    if not exists('capture-request') then return end
    local pc = state.PC.value
    assert(pc >= 0x4c0000 and pc < 0x500000, 'Expected System 3.01 execution')
    assert(state.SP.value >= 0x1000 and state.SP.value < 0x40000, 'Invalid native stack')
    dump('native.ram', 0, 0x40000)
    dump('flash.bin', 0x400000, 0x100000)
    done = true
    print('Captured disposable native-file fixture; validate through prepare.py')
    machine:exit()
    end)
    if not ok then
        done = true
        print('FAIL fixture capture: ' .. tostring(failure))
        machine:exit()
    end
end)

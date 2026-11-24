#!/usr/bin/env python3
"""Capture original AlphaWord dialogs with disposable state and cursor-safe RAM."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = ROOT / 'betawise/tests/mame/asneo'
sys.path.insert(0, str(HERE))
from check import prepare_session


# Explicit text from the pinned vendor image/manual; glyph 0x0a is the
# vendor selection arrow, verified against that image's font bytes.
EXPECTED = {
    'find': ['  Find: [                ]', '  Press enter to search in "File 1",',
        '  Option-enter to search in all files,', '  Cmd-G to find again, esc to exit.'],
    'replace': ['          Find:[                         ]',
        '  Replace with:[                         ]',
        '  (*)whole word( )match case( )replace all',
        '   (tab=next field, cmd-H=help, esc=exit)'],
    'thesaurus': ['  Enter a word for the Thesaurus to', '  look up:',
        '  [                             ]', '                  (Press esc key to exit)'],
    'spelling': ['  Select word and enter OR       I=ignore',
        '  runn                           E=edit',
        '  - run   - ruin  - rune         C=context',
        '  \x0a runt  - rung  - runny        A=add'],
}


def verify(out):
    from PIL import Image, ImageChops
    from bible_layout import captured_font
    from screen_bitmap import compare
    results = {}
    for index, (name, lines) in enumerate(EXPECTED.items(), 1):
        profile = captured_font(out, index)
        assert profile['height'] == 16 and set(profile['widths'][32:127]) == {6}
        expected = Image.new('1', (264, 65))
        for row, line in enumerate(lines):
            assert len(line) <= 44
            for column, character in enumerate(line.ljust(44)):
                glyph = profile['glyphs'][ord(character)]
                for y in range(16):
                    for x in range(6):
                        expected.putpixel((column * 6 + x, row * 16 + y),
                            (glyph[y // 8 * 6 + x] >> (y % 8)) & 1)
        reference = out / (name + '-reference.png')
        ImageChops.invert(expected.convert('L')).save(reference)
        results[name] = compare([out / (name + '.lcd.json')], reference,
            out / (name + '-comparison'), screen_size=(264, 65))
    (out / 'results.json').write_text(json.dumps({'status': 'passed', 'screens': results}, indent=2))
    evidence = sorted(out.glob('*.lcd.json')) + sorted(out.glob('*.bin'))
    evidence += sorted((out / 'artifacts').glob('*'))
    evidence += [Path(__file__).resolve()]
    (out / 'evidence-manifest.json').write_text(json.dumps([
        {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        for path in evidence], indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    firmware = ROOT / 'Ghidra/Alphasmart Neo/SmartApplets'
    emulator = ROOT / 'mame/neodiag'
    prepare_session(out, firmware, 'extra', emulator)
    flash = bytearray((out / 'nvram/asneo/flashnv').read_bytes())
    flash[0x70000:] = b'\xff' * (len(flash) - 0x70000)
    offset = 0x70000
    (out / 'artifacts').mkdir()
    for name in ['alphawordplus.os3kapp', 'spellcheck_small_usa.os3kapp', 'thesaurus_small_usa.os3kapp']:
        path = firmware / name
        data = path.read_bytes()
        flash[offset:offset + len(data)] = data
        offset += len(data)
        shutil.copyfile(path, out / 'artifacts' / name)
    (out / 'nvram/asneo/flashnv').write_bytes(flash)
    cases = [
        ('find', ['Find']),
        ('replace', ['Escape', ['Left Ctrl', 'Find']]),
        ('thesaurus', ['Escape', ['Left Ctrl', 'T']]),
        ('spelling', ['Escape', 'R', 'U', 'N', 'N', 'Space', 'Spell Check']),
    ]
    harness = (HERE / 'BibleReaderHarness.lua').read_text()
    helpers = harness[harness.index('local function dump(path'):harness.index('local function park()')]
    # Serialize only strings and arrays, without shell interpolation.
    def lua(value):
        if isinstance(value, str):
            return json.dumps(value)
        return '{' + ','.join(lua(item) for item in value) + '}'
    script = 'local capture_directory=' + lua(str(out)) + '\n'
    script += 'local cases=' + lua(cases) + '\n'
    script += 'local lcd_module=' + lua(str(HERE / 'NeoLCD.lua')) + '\n'
    script += '''local machine=manager.machine
local cpu=machine.devices[':maincpu'];local memory=cpu.spaces.program
local lcd=dofile(lcd_module);local index=1
io.stdout:setvbuf('no')
''' + helpers + '''
local function key(name)
 for row=0,15 do for _,field in pairs(machine.ioport.ports[':ROW'..row].fields)do
  if field.name:sub(1,#name+2)==name..' ['then return field end
 end end;error('missing key '..name)
end
local frame,start,phase,ki=0,0,'boot',1
local held={};local events={};local stable,last=0,nil
local function press(names)
 if type(names)=='string'then names={names}end
 held=names;for _,name in ipairs(held)do key(name):set_value(1)end
 start=frame;phase='release'
end
local regs={'D0','D1','D2','D3','D4','D5','D6','D7','A0','A1','A2','A3','A4','A5','A6','SP','PC','SR'}
local saved,ram,original,samples
local scratch,code,stack=0x3f000,0x3ff00,0x3fe00
local function mode(n)
 memory:write_u16(code,0xa018);memory:write_u16(code+2,0x60fe)
 memory:write_u32(stack,code+2);memory:write_u32(stack+4,n)
 cpu.state.SR.value=0x2700;cpu.state.SP.value=stack;cpu.state.PC.value=code
end
local function returned()return cpu.state.PC.value==code+2 or cpu.state.PC.value==code+4 end
emu.register_frame_done(function()
 frame=frame+1
 local ok,err=pcall(function()
  assert(frame<15000,'bounded dialog capture')
  if frame%600==0 then print('STATE',frame,index,phase,string.format('%x',cpu.state.PC.value))end
  local sig=lcd.refresh();stable=sig==last and stable+1 or 1;last=sig
  if frame==150 then key('Y'):set_value(1)end
  if frame==156 then key('Y'):clear_value()end
  if frame==360 then key('Enter'):set_value(1)end
  if frame==366 then key('Enter'):clear_value()end
  if phase=='boot'and frame>700 then ki=1;press(cases[index][2][ki])
  elseif phase=='release'and frame-start>=6 then
   for _,name in ipairs(held)do key(name):clear_value()end
   phase='gap';start=frame
  elseif phase=='gap'and frame-start>=20 and stable>=3 then
   ki=ki+1;if cases[index][2][ki]then press(cases[index][2][ki])else phase='ready';start=frame end
  elseif phase=='ready'and frame-start>=20 and stable>=3 and(cpu.state.PC.value==0x426758 or cpu.state.PC.value==0x437438)then
   assert(memory:read_u16(cpu.state.PC.value)==(cpu.state.PC.value==0x437438 and 0x4e75 or 0x40c0),'verified instruction boundary')
   local x,y=memory:read_u16(0x5c72),memory:read_u16(0x5c74)
   assert(x<264 and y<66,'cursor geometry')
   local f=assert(io.open(capture_directory..'/cursor-'..index..'.json','w'))
   f:write(string.format('{"x":%d,"y":%d,"mode":%d}',x,y,memory:read_u8(0x48be)));f:close()
   dump_font('font',memory:read_u32(0x5c68))
   saved={};ram={};for _,r in ipairs(regs)do saved[r]=cpu.state[r].value end
   for i=0,4095 do ram[i]=memory:read_u8(scratch+i)end
   original=memory:read_u8(0x48be);mode(12);phase='hide'
  elseif phase=='hide'and returned()then
   assert(memory:read_u8(0x48be)==12,'hide return');phase='samples';samples={}
  elseif phase=='samples'then
   samples[#samples+1]=lcd.frame()
   if #samples==3 then lcd.save(capture_directory..'/'..cases[index][1]..'.lcd.json',samples);mode(original);phase='restore'end
  elseif phase=='restore'and returned()then
   assert(memory:read_u8(0x48be)==original,'restore return')
   for i=0,4095 do memory:write_u8(scratch+i,ram[i])end
   for _,r in ipairs(regs)do cpu.state[r].value=saved[r]end
   print('CAPTURE '..cases[index][1]);index=index+1
   if not cases[index]then machine:exit();return end
   ki=1;press(cases[index][2][ki])
  end
 end)
 if not ok then print('FAIL '..tostring(err));machine:exit()end
end)
'''
    (out / 'run.lua').write_text(script)
    (out / 'cases.json').write_text(json.dumps(cases, indent=2))
    with (out / 'mame.log').open('w') as log:
        subprocess.run([str(emulator), 'asneo', '-rompath', str(out / 'roms'),
            '-nvram_directory', str(out / 'nvram'), '-cfg_directory', str(out / 'cfg'),
            '-video', 'none', '-sound', 'none', '-nothrottle', '-autoboot_delay', '0',
            '-autoboot_script', str(out / 'run.lua'), '-seconds_to_run', '260'],
            stdout=log, stderr=subprocess.STDOUT,
            env=dict(os.environ, SDL_VIDEODRIVER='dummy'), timeout=180, check=True)
    log = (out / 'mame.log').read_text()
    assert 'FAIL' not in log and all('CAPTURE ' + name in log for name, _ in cases), log
    # Three samples must be identical, including controller flags.
    from neo_reader import lcd_frames
    for name, _ in cases:
        lcd_frames(out / (name + '.lcd.json'), height=65)
    verify(out)
    print(log)


if __name__ == '__main__':
    main()

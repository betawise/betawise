#!/usr/bin/env python3
"""Characterize original AlphaWord Small-font rows by exact source glyphs."""
import argparse,hashlib,importlib.util,json,os,shutil,struct,subprocess,sys
from pathlib import Path
from PIL import Image,ImageChops
from check import ROOT,HERE,prepare_session
from bible_layout import captured_font
from neo_reader import lcd_frames
from screen_bitmap import compare
spec=importlib.util.spec_from_file_location('repl',HERE/'check-repl.py');repl=importlib.util.module_from_spec(spec);spec.loader.exec_module(repl)
ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);fw=ROOT/'Ghidra/Alphasmart Neo/SmartApplets';mame=ROOT/'mame/neodiag';prepare_session(out,fw,'extra',mame);flash=bytearray((out/'nvram/asneo/flashnv').read_bytes());flash[0x70000:]=b'\xff'*(len(flash)-0x70000);offset=0x70000;(out/'artifacts').mkdir()
for p in [fw/'alphawordplus.os3kapp',fw/'neofontsmall.os3kapp']:
 b=p.read_bytes();flash[offset:offset+len(b)]=b;offset+=len(b);shutil.copyfile(p,out/'artifacts'/p.name)
(out/'nvram/asneo/flashnv').write_bytes(flash);lines=[f'agypq0{i}'for i in range(1,7)];keys=[]
for i,line in enumerate(lines):
 if i:keys.append('Enter')
 keys.extend(c.upper()for c in line)
source=(HERE/'BibleWiseHarness.lua').read_text();fontdump=source[source.index('local function dump(path'):source.index('-- Test oracle for the pinned Neo 3.21 fixture')]
script='local lcd_module='+repl.lua(str(HERE/'NeoLCD.lua'))+'\nlocal capture_directory='+repl.lua(str(out))+'\nlocal typed='+repl.lua(keys)+'''\nlocal machine=manager.machine;local cpu=machine.devices[':maincpu'];local memory=cpu.spaces.program;local lcd=dofile(lcd_module);local index=1
local function key(name)for row=0,15 do for _,f in pairs(machine.ioport.ports[':ROW'..row].fields)do if f.name:sub(1,#name+2)==name..' ['then return f end end end;error(name)end
'''+fontdump+'''
local frame=0;local events={};local function press(at,names)if type(names)=='string'then names={names}end;events[at]=function()for _,n in ipairs(names)do key(n):set_value(1)end end;events[at+6]=function()for _,n in ipairs(names)do key(n):clear_value()end end end
press(150,'Y');press(360,'Enter');press(700,{'Left Ctrl','Left Alt','Command','F'});press(850,'Home');press(920,'End');press(990,'Enter')
local phase='font';local start,ki,stable,last=0,1,0,nil;local saved,ram,mode,samples;local scratch,code,stack=0x3f000,0x3ff00,0x3fe00;local regs={'D0','D1','D2','D3','D4','D5','D6','D7','A0','A1','A2','A3','A4','A5','A6','SP','PC','SR'}
local function callmode(n)memory:write_u16(code,0xa018);memory:write_u16(code+2,0x60fe);memory:write_u32(stack,code+2);memory:write_u32(stack+4,n);cpu.state.SR.value=0x2700;cpu.state.SP.value=stack;cpu.state.PC.value=code end
local function returned()return cpu.state.PC.value==code+2 or cpu.state.PC.value==code+4 end
emu.register_frame_done(function()frame=frame+1;local ok,err=pcall(function()
 if events[frame]then events[frame]()end;local sig=lcd.refresh();stable=sig==last and stable+1 or 1;last=sig
 assert(frame<6000,'bounded AlphaWord probe')
 if phase=='font'and frame>1100 then local face=memory:read_u32(0x5c68);assert(face>=0x1000,'font pointer');assert(memory:read_u8(face)==11,'Small font not selected');phase='type';start=frame end
 if phase=='type'and frame-start>=12 then if ki<=#typed then press(frame+1,typed[ki]);ki=ki+1;start=frame else phase='ready';start=frame end end
 if phase=='ready'and frame-start>12 and stable>=3 and cpu.state.PC.value==0x426758 then
  assert(memory:read_u16(0x5c72)<264 and memory:read_u16(0x5c74)<66,'cursor geometry');mode=memory:read_u8(0x48be);dump_font('font',memory:read_u32(0x5c68));local f=assert(io.open(capture_directory..'/cursor.json','w'));f:write(string.format('{"x":%d,"y":%d,"mode":%d}',memory:read_u16(0x5c72),memory:read_u16(0x5c74),mode));f:close();saved={};ram={};for _,r in ipairs(regs)do saved[r]=cpu.state[r].value end;for i=0,4095 do ram[i]=memory:read_u8(scratch+i)end;callmode(12);phase='hide'
 elseif phase=='hide'and returned()then assert(memory:read_u8(0x48be)==12);phase='samples';samples={};last=nil
 elseif phase=='samples'then samples[#samples+1]=lcd.frame();if #samples==3 then assert(machine.screens[':screen'].height==65,'physical panel geometry');local on=machine.screens[':screen']:pixel(1,3);local off=machine.screens[':screen']:pixel(263,0);assert(on~=off,'known source glyph black/white pixels');for x=0,263 do assert(machine.screens[':screen']:pixel(x,64)==(lcd.black(x,64)and on or off),'physical bottom row output')end;lcd.save(capture_directory..'/checkpoint-01.lcd.json',samples);callmode(mode);phase='restore'end
 elseif phase=='restore'and returned()then assert(memory:read_u8(0x48be)==mode);for i=0,4095 do memory:write_u8(scratch+i,ram[i])end;for _,r in ipairs(regs)do cpu.state[r].value=saved[r]end;print('PASS AlphaWord row capture');machine:exit()end
 end);if not ok then print('FAIL '..tostring(err));machine:exit()end end)
''';(out/'run.lua').write_text(script)
with(out/'mame.log').open('w')as log:subprocess.run([str(mame),'asneo','-rompath',str(out/'roms'),'-nvram_directory',str(out/'nvram'),'-cfg_directory',str(out/'cfg'),'-video','none','-sound','none','-nothrottle','-autoboot_delay','0','-autoboot_script',str(out/'run.lua'),'-seconds_to_run','130'],stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,SDL_VIDEODRIVER='dummy'),timeout=150,check=True)
log=(out/'mame.log').read_text();assert 'PASS AlphaWord row capture'in log,log[-1000:];profile=captured_font(out,1);actual=lcd_frames(out/'checkpoint-01.lcd.json')[0];matches=[]
for pitch in [10,11]:
 for first in [0,1]:
  expected=Image.new('1',(264,64));px=expected.load()
  for row,text in enumerate(lines[first:]):
   x=0
   for c in text:
    w=profile['widths'][ord(c)];g=profile['glyphs'][ord(c)]
    for y in range(11):
     for dx in range(w):
      yy=row*pitch+y
      if yy<64 and g[(y//8)*w+dx]>>(y%8)&1:px[x+dx,yy]=1
    x+=w
  if list(map(int,expected.getdata()))==actual:matches.append((pitch,first,expected))
assert len(matches)==1,('unknown/ambiguous original AlphaWord layout',[(a,b)for a,b,_ in matches]);pitch,first,expected=matches[0];ref=out/'expected.png';ImageChops.invert(expected.convert('L')).save(ref);cmp=compare([out/'checkpoint-01.lcd.json'],ref,out/'comparison');panel=Image.new('1',(264,65));panel.paste(expected,(0,0));px=panel.load();x=0
# Independently spell the sixth input line's row 9 at physical y=64.
for c in lines[-1]:
 w=profile['widths'][ord(c)];g=profile['glyphs'][ord(c)]
 for dx in range(w):px[x+dx,64]=(g[w+dx]>>1)&1
 x+=w
panelref=out/'expected-panel.png';ImageChops.invert(panel.convert('L')).save(panelref);panelcmp=compare([out/'checkpoint-01.lcd.json'],panelref,out/'comparison-panel',screen_size=(264,65))
result=dict(status='passed',physical_panel_rows=65,physical_row64_descender_pixels=sum(panel.crop((0,64,264,65)).getdata()),full_panel=panelcmp,line_pitch=pitch,first_visible_input_line=first+1,cursor=json.loads((out/'cursor.json').read_text()),font_height=11,pixels=cmp);(out/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

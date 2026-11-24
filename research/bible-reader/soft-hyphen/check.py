#!/usr/bin/env python3
"""Original Neo editor soft-hyphen experiment; exact glyph and RAM assertions."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = ROOT / 'betawise/tests/mame/asneo'
sys.path.insert(0,str(HERE))
from check import prepare_session
from bible_layout import system_font
from screen_bitmap import compare

out=ROOT/'.research-work/bible-compression/native-soft-hyphen-v4'
out.mkdir(parents=True,exist_ok=False)
firmware=ROOT/'Ghidra/Alphasmart Neo/SmartApplets'
app=Path(__file__).resolve().parent
subprocess.run(['make','-C',str(app)],check=True,stdout=(out/'build.log').open('w'))
emulator=ROOT/'mame/neodiag'
prepare_session(out,firmware,'extra',emulator)
flash=bytearray((out/'nvram/asneo/flashnv').read_bytes());flash[0x70000:]=b'\xff'*(len(flash)-0x70000)
images=[firmware/'alphawordplus.os3kapp',app/'SoftHyphen.OS3KApp']
(out/'artifacts').mkdir()
import shutil
pos=0x70000
for path in images:
 data=path.read_bytes();flash[pos:pos+len(data)]=data;pos+=len(data);shutil.copyfile(path,out/'artifacts'/path.name)
(out/'nvram/asneo/flashnv').write_bytes(flash)
shutil.copyfile(app/'SoftHyphen.c',out/'artifacts/SoftHyphen.c')
nm=subprocess.check_output(['m68k-linux-gnu-nm','-n',str(app/'SoftHyphen.elf')],text=True)
symbols={f[2]:int(f[0],16)-0x80000000 for line in nm.splitlines() if len(f:=line.split())==3}
checks=[dict(name=name,chapter=i,verse=1,numbered=0,keys=[] if i==0 else ['Down']) for i,name in enumerate([
 'Cached hyphen wide','Cached hyphen narrow','Literal hyphen wide','Literal hyphen narrow','No hyphen wide','No hyphen narrow'])]
config=dict(lcd_module=str(HERE/'NeoLCD.lua'),capture_directory=str(out),reader_offset=symbols['g_reader'],
 editor_offset=symbols['g_editor'],status_offset=symbols['g_reader']+55,small_font_offset=symbols['g_editor']+78,
 busy_offset=symbols['g_reader']+55,status_text_offset=0,busy_dots_offset=0,saved_offset=0,input_offset=0,checks=checks)
# Same bounded cursor-hide/restore and three stable controller samples as production acceptance.
lua=(HERE/'BibleWiseHarness.lua').read_text().replace(" dump(string.format('metrics-",f" dump(string.format('file-%02d.bin',index),ram+{symbols['g_file_bytes']},64)\n dump(string.format('metrics-")
head=''.join('local '+k+'='+json.dumps(v)+'\n' for k,v in config.items() if k!='checks')
head+='local checks={'+','.join('{name='+json.dumps(c['name'])+',chapter='+str(c['chapter'])+',verse=1,numbered=0,keys={'+('"Down"' if c['keys'] else '')+'}}' for c in checks)+'}\n'
(out/'run.lua').write_text(head+lua)
(out/'manifest.json').write_text(json.dumps([dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in images+[app/'SoftHyphen.c',HERE/'BibleWiseHarness.lua',emulator]],indent=2))
with (out/'mame.log').open('w') as log:
 result=subprocess.run([str(emulator),'asneo','-rompath',str(out/'roms'),'-cfg_directory',str(out/'cfg'),
 '-nvram_directory',str(out/'nvram'),'-video','none','-sound','none','-nothrottle','-autoboot_delay','0',
 '-autoboot_script',str(out/'run.lua'),'-seconds_to_run','240'],env=dict(os.environ,SDL_VIDEODRIVER='dummy'),stdout=log,stderr=subprocess.STDOUT,timeout=180)
assert result.returncode==0 and 'PASS BibleWise suite' in (out/'mame.log').read_text(),(out/'mame.log').read_text()[-1500:]
from PIL import Image,ImageChops
pixels=system_font()
expected_lines=[['abcdefghij-klmnop'],['abcdefghij-','klmnop'],['abcdefghij-klmnop'],['abcdefghij-','klmnop'],['abcdefghijklmnop'],['abcdefghijkl','mnop']]
reports=[]
for i,lines in enumerate(expected_lines,1):
 raw=(out/f'file-{i:02}.bin').read_bytes()
 assert raw.split(b'\0',1)[0].replace(b'\xad',b'-').replace(b'\x8f',b'') == (b'abcdefghij-klmnop' if i<=4 else b'abcdefghijklmnop'), raw.hex()
 expected=Image.new('1',(264,65),0)
 for row,text in enumerate(lines):
  for col,ch in enumerate(text):
   for dy in range(16):
    for dx in range(6):
     if pixels[ord(ch)*12+(dy//8)*6+dx]>>(dy%8)&1:expected.putpixel((col*6+dx,row*16+dy),1)
 reference=out/f'expected-{i:02}.png';ImageChops.invert(expected.convert('L')).save(reference)
 reports.append(dict(case=checks[i-1]['name'],expected_lines=lines,raw_file=(out/f'file-{i:02}.bin').read_bytes().hex(),
   comparison=compare([out/f'checkpoint-{i:02}.lcd.json'],reference,out/f'comparison-{i:02}',screen_size=(264,65))))
(out/'results.json').write_text(json.dumps(dict(status='passed',results=reports),indent=2))
print(json.dumps(dict(status='passed',cases=len(reports))))

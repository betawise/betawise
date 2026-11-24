#!/usr/bin/env python3
"""Original-ROM vector lifecycle observation, disposable flash/RAM; no UI oracle."""
from pathlib import Path
import hashlib,json,os,shutil,struct,subprocess,sys
HERE=Path(__file__).resolve().parent
WS=HERE.parents[3]
out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False)
fw=WS/'Ghidra/Alphasmart Neo/SmartApplets'
small=(fw/'smallos3kneorom.os3kos').read_bytes();system=(fw/'os3kneorom.os3kos').read_bytes()
assert hashlib.sha256(system).hexdigest()=='32fe55bb50c1b58326bd303f14973b8402ddf8bf6662b210e4d5e9f931c7e6c0'
flash=bytearray(b'\xff'*0x400000);flash[:len(small)]=small;source=0
for pos in range(0x50,0x70,8):
 addr,n=struct.unpack_from('>II',system,pos)
 if not addr and not n:break
 n=(n+1023)&~1023;flash[addr-0x400000:addr-0x400000+n]=system[source:source+n];source+=n
# Prepatched disposable image: executable F-line service in the main-ROM FF tail.
handler=bytes.fromhex('54af000223fc464c494e000300204e73')
assert flash[0x58000:0x58000+len(handler)]==b'\xff'*len(handler)
flash[0x58000:0x58000+len(handler)]=handler
app=(fw/'alphawordplus.os3kapp').read_bytes();flash[0x70000:0x70000+len(app)]=app
(out/'nvram/asneo').mkdir(parents=True);(out/'nvram/asneo/flashnv').write_bytes(flash)
(out/'roms/asneo').mkdir(parents=True)
for n in ['smallos3kneorom.os3kos','os3kneorom.os3kos']:shutil.copyfile(fw/n,out/'roms/asneo'/n)
(out/'cfg').mkdir();(out/'cfg/asneo.cfg').write_text('<mameconfig version="10"><system name="asneo"><input><port tag=":NOR_PROFILE" type="CONFIG" mask="1" defvalue="0" value="1" /></input></system></mameconfig>')
assembly=WS/'betawise/research/memory-allocation/manager/ram-evidence/ram-entry.S'
subprocess.run(['m68k-linux-gnu-as','-m68000',str(assembly),'-o',str(out/'ram-entry.o')],check=True)
subprocess.run(['m68k-linux-gnu-objcopy','-O','binary','-j','.text',str(out/'ram-entry.o'),str(out/'ram-entry.bin')],check=True)
blob=bytearray(1024);struct.pack_into('>IIII',blob,0,0xc0ffeead,1024,2048,0)
struct.pack_into('>IHBB',blob,16,0xff000000,0x7010,1,0);blob[24:32]=b'RAMProbe'
struct.pack_into('>IIII',blob,132,148,0,1,2);code=(out/'ram-entry.bin').read_bytes();blob[148:148+len(code)]=code
struct.pack_into('>I',blob,1020,0xcafefeed);(out/'ram-probe.bin').write_bytes(blob)
shutil.copyfile(HERE/'vector-probe.lua',out/'probe.lua')
(out/'manifest.json').write_text(json.dumps({'system_sha256':hashlib.sha256(system).hexdigest(),'small_sha256':hashlib.sha256(small).hexdigest(),'seed_sha256':hashlib.sha256(flash).hexdigest(),'emulator_sha256':hashlib.sha256((WS/'mame/neodiag').read_bytes()).hexdigest()},indent=2))
with (out/'mame.log').open('w') as log:
 r=subprocess.run([str(WS/'mame/neodiag'),'asneo','-rompath',str(out/'roms'),'-nvram_directory',str(out/'nvram'),'-cfg_directory',str(out/'cfg'),'-video','none','-sound','none','-nothrottle','-skip_gameinfo','-autoboot_delay','0','-autoboot_script',str(out/'probe.lua'),'-seconds_to_run','100'],cwd=out,env={**os.environ,'SDL_VIDEODRIVER':'dummy'},stdout=log,stderr=subprocess.STDOUT,timeout=120)
assert r.returncode==0
s=(out/'mame.log').read_text();print('\n'.join(l for l in s.splitlines() if l.startswith(('VECTOR','STATE','PASS','FAIL'))))
assert 'PASS vector lifecycle' in s and 'FAIL ' not in s

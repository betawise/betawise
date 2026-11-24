#!/usr/bin/env python3
"""Prepare a disposable AS3000 filesystem-export run; no emulator/network use."""
import argparse,hashlib,json,sys
from pathlib import Path
from catalog import read_ram,catalogue
HERE=Path(__file__).resolve().parent;BASE=HERE.parent;ROOT=HERE.parents[2]
ap=argparse.ArgumentParser();ap.add_argument('out',type=Path);ap.add_argument('--ram',required=True,type=Path,help='disposable historical 256 KiB AS3000 capture, optionally gzip');ap.add_argument('--flash',type=Path,help='optional matching 1 MiB raw guest-byte-order flash capture');ap.add_argument('--port',type=int,default=13300);ap.add_argument('--timeout',type=int,default=900);args=ap.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
full=(ROOT/'betawise/tests/mame/asma3k/OS3KROM.OS3KOS').read_bytes();assert hashlib.sha256(full).hexdigest()=='732dca63399d883071ce41cc07ad352fa19c506b7b8c307ace16d5c53e6f8708'
rompath=ROOT/'mame/roms';flash=bytearray(b'\xff'*0x100000);small=(rompath/'asma3k/smallos3krom.os3kos').read_bytes();flash[:len(small)]=small;flash[0xc0000:0x100000]=full[:0x40000];flash[0x4000:0x7bf0]=full[0x40000:]
ram=read_ram(args.ram)
# The default fixture is the reviewed historical AlphaWord + KeyWords image.
# For another disposable capture, require its matching raw flash rather than
# guessing which installed image belongs to each native descriptor.
if args.flash:
 flash=bytearray(args.flash.read_bytes());assert len(flash)==0x100000
 assert flash[0xc0000:]==full[:0x40000]and flash[0x4000:0x7bf0]==full[0x40000:]
else:
 headers=[int.from_bytes(ram[0xd82+4*a:0xd86+4*a],'big')for a in range(32)]
 alpha=(rompath/'asma3k/alphawordplus.os3kapp').read_bytes();keywords=(rompath/'asma3k/keywords.os3kapp').read_bytes()
 assert headers[1:3]==[0x408000,0x408000+len(alpha)]and all(h in(0,0xffffffff)for h in headers[3:]),'Provide --flash for a different installed-applet set'
 flash[0x8000:0x8000+len(alpha)]=alpha;off=headers[2]-0x400000;flash[off:off+len(keywords)]=keywords
expected=catalogue(ram,flash)
symbols=json.loads((BASE/'build/symbols.json').read_text());binary=BASE/'build/msc.bin';end=symbols['end']
regions=[(0x30000,end),(0x3c000,0x3e200)]
# Only logical file bytes are exported. Unused capacity may be borrowed by this
# disposable RAM bootstrap while all native allocation/writes are stopped.
for file in expected['files']:
 for lo,hi in regions:
  assert not(file['length']and file['address']<hi and file['address']+file['length']>lo),('live file overlaps bootstrap',file['path'])
  assert not(file['record']<hi and file['record']+72>lo),('file record overlaps bootstrap',file['path'])
(out/'native-before.ram').write_bytes(ram);(out/'flash-memory.bin').write_bytes(flash);(out/'expected.json').write_text(json.dumps(expected,indent=2)+'\n')
native=bytearray(flash)
if sys.byteorder=='little':native[0::2],native[1::2]=native[1::2],native[0::2]
nvram=out/'nvram/asma3k';nvram.mkdir(parents=True);(nvram/'flash').write_bytes(native)
lua=(HERE/'load.lua.in').read_text()
values={'OUT':json.dumps(str(out)),'BINARY':json.dumps(str(binary)),'RAM':json.dumps(str(out/'native-before.ram')),'ENTRY':str(symbols['msc_main']),'BSS':str(0x30000+binary.stat().st_size),'END':str(end),'DEADLINE':str(60*(args.timeout+60))}
for k,v in values.items():lua=lua.replace('@'+k+'@',v)
assert '@'not in lua;(out/'load.lua').write_text(lua)
cmd=[str(ROOT/'mame-usb/asma3k'),'asma3k','-rompath',str(rompath),'-nvram_directory',str(out/'nvram'),'-cfg_directory',str(out/'cfg'),'-video','none','-sound','none','-autoboot_delay','0','-autoboot_script',str(out/'load.lua'),'-usb',f'socket.127.0.0.1:{args.port}','-seconds_to_run',str(args.timeout+60)]
(out/'prepared.json').write_text(json.dumps({'command':cmd,'packet_port':args.port,'timeout':args.timeout,'sectors':4096,'files':len(expected['files']),'build_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'ram_sha256':hashlib.sha256(ram).hexdigest()},indent=2)+'\n')
print('Prepared only; no emulator started:',out)

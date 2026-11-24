#!/usr/bin/env python3
"""Probe original CoWriter handler and Neo face selector in disposable RAM."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
here=Path(__file__).resolve().parent
workspace=here.parents[2]
out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=True)
romdir=out/'roms/asneo';romdir.mkdir(parents=True,exist_ok=True)
source=workspace/'Ghidra/Alphasmart Neo/SmartApplets'
for name in ('os3kneorom.os3kos','smallos3kneorom.os3kos'):
    p=romdir/name
    if not p.exists():p.symlink_to(source/name)
cow=source/'CoWriter.os3kapp'
manifest={name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in ('CoWriter.os3kapp','alphawordplus.os3kapp','alphawordplus.os3kapp.bin','os3kneorom.os3kos')}
assert manifest==json.loads((here/'images.json').read_text()),'Original image hashes differ'
assert (source/'alphawordplus.os3kapp').read_bytes()[0x94:0x94+len((source/'alphawordplus.os3kapp.bin').read_bytes())]==(source/'alphawordplus.os3kapp.bin').read_bytes()
(out/'hashes.json').write_text(json.dumps(manifest,indent=2)+'\n')
lua=out/'probe.lua';lua.write_text((here/'probe.lua.in').read_text().replace('@COWRITER@',str(cow)))
args=[workspace/'mame/neodiag','asneo','-rompath',out/'roms','-nvram_directory',out/'nvram','-cfg_directory',out/'cfg','-video','none','-sound','none','-nothrottle','-seconds_to_run','40','-autoboot_delay','0','-autoboot_script',lua]
with (out/'mame.log').open('w') as log:
    subprocess.run(list(map(str,args)),cwd=out,env={**os.environ,'SDL_VIDEODRIVER':'dummy'},stdout=log,stderr=subprocess.STDOUT,check=True)
text=(out/'mame.log').read_text()
assert 'PASS cowriter/face probe 278 cases' in text and 'FAIL ' not in text and 'LUA ERROR' not in text,text[-2000:]
(out/'results.json').write_text(json.dumps({'passed':278,'face_selector':256,'scanner_bits':16,'cowriter_handler':6,'screen_assertions':False},indent=2)+'\n')
print('PASS 278 original-code cases; evidence:',out)

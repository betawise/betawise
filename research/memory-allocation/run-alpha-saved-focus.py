from pathlib import Path
import sys,json,subprocess,os,hashlib
root=Path('/home/kirk/Projects/Alphasmart');sys.path.insert(0,str(root/'betawise/tests/mame/asneo'))
from check import prepare_session
out=Path(sys.argv[1]).resolve();out.mkdir(exist_ok=False)
fw=root/'Ghidra/Alphasmart Neo/SmartApplets';mame=root/'mame/neodiag'
prepare_session(out,fw,'extra',mame)
flash=bytearray((out/'nvram/asneo/flashnv').read_bytes());flash[0x70000:]=b'\xff'*(len(flash)-0x70000)
aw=(fw/'alphawordplus.os3kapp').read_bytes();flash[0x70000:0x70000+len(aw)]=aw
hello=(root/'betawise/applets/HelloWorld/build/HelloWorld.OS3KApp').read_bytes();addr=(0x70000+len(aw)+1023)&~1023;flash[addr:addr+len(hello)]=hello
(out/'nvram/asneo/flashnv').write_bytes(flash)
lua=(Path(__file__).resolve().parent/'alpha-saved-focus.lua').read_text()
(out/'run.lua').write_text(lua.replace('OUT',json.dumps(str(out))))
with (out/'mame.log').open('w') as log:
 subprocess.run([str(mame),'asneo','-rompath',str(out/'roms'),'-nvram_directory',str(out/'nvram'),'-cfg_directory',str(out/'cfg'),'-video','none','-sound','none','-nothrottle','-seconds_to_run','100','-autoboot_delay','0','-autoboot_script',str(out/'run.lua')],stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'SDL_VIDEODRIVER':'dummy'},timeout=180,check=True)
log=(out/'mame.log').read_text();print(log);assert 'PASS native AlphaWord focus-loss observation' in log and 'FAIL ' not in log

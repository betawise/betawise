from pathlib import Path
import hashlib, json, shutil, subprocess, sys
ROOT=Path('/home/kirk/Projects/Alphasmart')
BASE=Path(__file__).resolve().parent
SOURCES=BASE/'sources'
SOURCES.mkdir(exist_ok=True)
for name in ['asneo','asma3k']:
 shutil.copytree(ROOT/'betawise/tests/mame'/name,SOURCES/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
sys.path.insert(0,str(ROOT/'betawise/tests/mame/asneo'))
from check import build_images
build_images('extra',BASE/'build.log')
subprocess.run([sys.executable,str(ROOT/'betawise/tests/mame/asneo/check.py'),'--prepare-only','--no-build','--output',str(BASE/'neo-seed')],check=True)
metadata={'sources':{},'inputs':{},'git':{}}
for p in SOURCES.rglob('*'):
 if p.is_file():metadata['sources'][str(p.relative_to(SOURCES))]=hashlib.sha256(p.read_bytes()).hexdigest()
for p in [ROOT/'mame/mame',ROOT/'mame/neodiag',ROOT/'betawise/applets/MicroPython/build/MicroPython-extra.OS3KApp',ROOT/'betawise/applets/MicroPython/build/extra/MicroPython.OS3KApp']:
 metadata['inputs'][str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
for repo in ['betawise','mame']:
 metadata['git'][repo]={'head':subprocess.check_output(['git','-C',str(ROOT/repo),'rev-parse','HEAD'],text=True).strip(),'status':subprocess.check_output(['git','-C',str(ROOT/repo),'status','--short'],text=True)}
metadata['host']={p:Path(p).read_text() for p in ['/proc/cpuinfo','/proc/loadavg']}
(BASE/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
print(BASE)

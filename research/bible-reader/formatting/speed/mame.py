#!/usr/bin/env python3
"""Run the verified C benchmark on a disposable Neo; numeric RAM oracle only."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import os

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
sys.path.insert(0,str(ROOT/'betawise/tests/mame/asneo'))
from check import prepare_session


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('prepared',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    prepared=args.prepared.resolve()
    out=args.output.resolve()
    out.mkdir(parents=True,exist_ok=False)
    app=ROOT/'betawise/applets/BibleWise'
    makefile='''TARGET = FormatBench.OS3KApp
OBJ = BenchGuest.o FormatBench.o Decoder.o BenchData.o BenchDataAsm.o
VPATH = '''+str(HERE)+':'+str(app)+'''
CPPFLAGS = -I'''+str(HERE)+' -I'+str(app)+' -I'+str(prepared)+'''
include '''+str(ROOT/'betawise/Makefile.common')+'''
BenchDataAsm.o: BenchData.S
	$(CC) $(CFLAGS) -c $< -o $@
'''
    (prepared/'Makefile').write_text(makefile)
    with(out/'build.log').open('w')as log:
        subprocess.run(['make','-C',str(prepared)],check=True,stdout=log,stderr=subprocess.STDOUT)
    firmware=ROOT/'Ghidra/Alphasmart Neo/SmartApplets'
    emulator=ROOT/'mame/neodiag'
    prepare_session(out,firmware,'extra',emulator)
    flash=bytearray((out/'nvram/asneo/flashnv').read_bytes())
    flash[0x70000:]=b'\xff'*(len(flash)-0x70000)
    start=0x70000
    hashes={}
    for path in [firmware/'alphawordplus.os3kapp',prepared/'FormatBench.OS3KApp']:
        raw=path.read_bytes();assert start+len(raw)<=len(flash)
        flash[start:start+len(raw)]=raw;start+=len(raw)
        hashes[str(path)]=hashlib.sha256(raw).hexdigest()
    (out/'nvram/asneo/flashnv').write_bytes(flash)
    symbols=subprocess.check_output(['m68k-linux-gnu-nm','-n',str(prepared/'FormatBench.elf')],text=True)
    offset=next(int(parts[0],16)-0x80000000 for line in symbols.splitlines()if len(parts:=line.split())==3 and parts[2]=='g_bench')
    script='''local machine=manager.machine
local cpu=machine.devices[':maincpu'];local memory=cpu.spaces.program
local frame,base,stable,last=0,nil,0,nil
local events={}
local function key(name)
 for r=0,15 do for _,f in pairs(machine.ioport.ports[':ROW'..r].fields)do if f.name:sub(1,#name+2)==name..' ['then return f end end end
 error('missing key '..name)
end
local function press(t,name)events[t]=function()key(name):set_value(1)end;events[t+6]=function()key(name):clear_value()end end
press(150,'Y');press(360,'Enter');press(740,'Applets');press(850,'Down');press(980,'Enter')
local samples={}
emu.register_frame_done(function()
 frame=frame+1
 if events[frame]then events[frame]()end
 if not base and frame>980 then
  local a=cpu.state.A5.value
  if a>=0x1000 and a+OFFSET+988<0x80000 and memory:read_u32(a+OFFSET)==0x464d5442 then base=a+OFFSET end
 end
 if base and memory:read_u32(base+8)==1 then
  assert(memory:read_u32(base+12)==0,'guest decoder failed at line '..memory:read_u32(base+12))
  local s='';for i=0,987 do s=s..string.char(memory:read_u8(base+i))end
  if s~=last then stable=0;samples={}end
  last=s;stable=stable+1;samples[#samples+1]=s
  if stable==3 then
   for i=1,3 do local f=assert(io.open(OUT..'/probe-'..i..'.bin','wb'));f:write(samples[i]);f:close()end
   print('PASS FormatBench numeric results');machine:exit()
  end
 end
 assert(frame<36000,'FormatBench guest timeout')
end)
'''.replace('OFFSET',str(offset)).replace('OUT',json.dumps(str(out)))
    (out/'run.lua').write_text(script)
    with(out/'mame.log').open('w')as log:
        completed=subprocess.run([str(emulator),'asneo','-rompath',str(out/'roms'),'-cfg_directory',str(out/'cfg'),'-nvram_directory',str(out/'nvram'),'-video','none','-sound','none','-nothrottle','-skip_gameinfo','-autoboot_delay','0','-autoboot_script',str(out/'run.lua'),'-seconds_to_run','600'],stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,SDL_VIDEODRIVER='dummy'),timeout=600)
    assert completed.returncode==0 and 'PASS FormatBench numeric results'in(out/'mame.log').read_text()
    raw=(out/'probe-1.bin').read_bytes();assert all((out/f'probe-{i}.bin').read_bytes()==raw for i in [2,3])
    magic,started,done,error,c,v,repetitions=struct.unpack_from('>7I',raw)
    assert magic==0x464d5442 and started==done==1 and error==0
    fixtures=json.loads((prepared/'fixtures.json').read_text())
    results=[]
    for ci,case in enumerate(fixtures['cases']):
        for vi,variant in enumerate(fixtures['variants']):
            ms,h,n,atoms,heads,error=struct.unpack_from('>6I',raw,28+24*(ci*10+vi))
            expected=case['expected']['raw'if variant[2]==0 else str(variant[3])]
            actual=dict(hash=h,bytes=n,atoms=atoms,headings=heads)
            assert actual==expected and not error,(case['name'],variant,actual,expected)
            results.append(dict(case=case['name'],variant=variant[0],milliseconds=ms/repetitions,**actual))
    (out/'results.json').write_text(json.dumps(dict(status='passed',scope='CPU decode/merge only; no native editor, file I/O or LCD rendering',repetitions=repetitions,results=results,assets=hashes,probe_sha256=hashlib.sha256(raw).hexdigest()),indent=2))
    print(json.dumps(results,indent=2))


if __name__=='__main__':main()

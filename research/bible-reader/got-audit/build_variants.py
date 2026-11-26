#!/usr/bin/env python3
"""Host-only code-generation probes. Never modifies the production sources or SDK."""
import argparse
from pathlib import Path
import re
import subprocess
import json

ROOT=Path(__file__).resolve().parents[3]
APP=ROOT/'applets/BibleWise'
SDK=ROOT/'os3k'
HERE=Path(__file__).resolve().parent
SOURCES=('BibleWise.c','Decoder.c','Search.c','Formatting.c')


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--variant',choices=['baseline','relax','unity','state','relative-calls','state-relative','no-console'],required=True);args=p.parse_args()
 out=HERE/'build'/args.variant;out.mkdir(parents=True,exist_ok=True)
 cpp=['-I'+str(APP),'-I'+str(APP/'build/data/nkjv'),'-I'+str(APP/'build/generated'),'-I'+str(SDK),'-I'+str(SDK/'build'),'-DBIBLEWISE_TEST=0','-DBIBLE_APP_NAME="BibleWise-NKJV"','-DBIBLE_VERSION="NKJV"']
 flags=['-m68000','-msoft-float','-msep-data','-fomit-frame-pointer','-fshort-enums','-fno-store-merging','-Os','-ffunction-sections','-fdata-sections']
 sources=[APP/n for n in SOURCES]
 if args.variant=='unity':
  source=out/'unity.c';source.write_text(''.join('#include "'+str(f)+'"\n'for f in sources));sources=[source]
 if args.variant in ('state','state-relative'):
  text=sources[0].read_text();start=text.index('static struct {');stop=text.index('static unsigned DisplayOptions',start)
  block=text[start:stop]
  # Keep the initialized six-byte settings object separate; group all zero-initialized reader fields.
  settings=re.search(r'^static BibleSettings g_settings.*\n',block,re.M).group()
  block=block.replace(settings,'')
  fields=re.findall(r'\b(g_\w+)\s*(?:\[|;)',block)
  block=re.sub(r'\bstatic\s+','',block)
  replacement='typedef struct {\n'+block+'} ReaderState;\nstatic ReaderState reader;\n'+settings+'\n'+''.join('#define '+name+' reader.'+name+'\n'for name in fields)
  source=out/'BibleWise.c';source.write_text(text[:start]+replacement+'\n'+text[stop:]);sources[0]=source
 if args.variant=='no-console':
  stub=out/'console-unused.c';stub.write_text('void _ConsoleReset(void) {}\n');sources.append(stub)
 objects=[];rewrites=0
 for source in sources:
  obj=out/(source.stem+'.o')
  if args.variant in ('relative-calls','state-relative'):
   asm=out/(source.stem+'.s')
   subprocess.run(['m68k-linux-gnu-gcc',*cpp,*flags,'-S',str(source),'-o',str(asm)],check=True)
   text=asm.read_text()
   # Only an adjacent address load and call through a call-clobbered A0/A1.
   # No cached-register or callback-pointer rewriting. Final linker checks PC16 reach.
   pattern=r'\tmove\.l ([\w.$]+)@GOT\(%a5\),(%a[01])\n\tjsr \(\2\)'
   text,n=re.subn(pattern,lambda m:'\tbsr.w '+m[1],text);rewrites+=n;asm.write_text(text)
   subprocess.run(['m68k-linux-gnu-gcc','-m68000','-c',str(asm),'-o',str(obj)],check=True)
  else:subprocess.run(['m68k-linux-gnu-gcc',*cpp,*flags,'-c',str(source),'-o',str(obj)],check=True)
  objects.append(obj)
 elf=out/'BibleWise-NKJV.elf'
 base=['m68k-linux-gnu-ld',*(str(o)for o in objects),str(APP/'build/NKJV/Resources.o'),'-static','-T',str(SDK/'os3k.lds'),str(SDK/'build/libos3k.a'),'--gc-sections','--emit-relocs']
 if args.variant=='relax':base+=['--relax']
 reloc=out/'fixups.bin'
 subprocess.run([*base,'--defsym','__os3k_reloc_size=0','-o',str(elf)],check=True)
 count=subprocess.check_output(['python3',str(SDK/'fixups.py'),'m68k-linux-gnu-readelf',str(elf),str(reloc)],text=True).strip()
 subprocess.run([*base,'--defsym','__os3k_reloc_size='+count,'-o',str(elf)],check=True)
 final=subprocess.check_output(['python3',str(SDK/'fixups.py'),'m68k-linux-gnu-readelf',str(elf),str(reloc)],text=True).strip();assert count==final
 subprocess.run(['m68k-linux-gnu-objcopy','--update-section','.data.reloc='+str(reloc),str(elf)],check=True)
 subprocess.run(['m68k-linux-gnu-objcopy','-O','binary',str(elf),str(elf.with_suffix('.OS3KApp'))],check=True)
 symbols={f[2]:int(f[0],16)for line in subprocess.check_output(['m68k-linux-gnu-nm',str(elf)],text=True).splitlines()if len(f:=line.split())==3}
 report=dict(variant=args.variant,a5=symbols['__os3k_ram_size'],got=symbols['__os3k_got_size'],rom=symbols['__os3k_rom_size'],adjacent_calls_rewritten=rewrites,validation='Host build only; not a production change or MAME acceptance')
 (out/'sizes.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))


if __name__=='__main__':main()

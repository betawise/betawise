#!/usr/bin/env python3
"""Build comparable production KJV search options; separate code and index ROM."""
from prototype_support import prototype_app, prototype_test
from pathlib import Path
import argparse,json,subprocess,shutil,struct,re,hashlib
ROOT=Path(__file__).resolve().parents[3];APP=prototype_app()
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--version',default='KJV',choices=['KJV','NKJV']);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);data=ROOT/'.research-work/bible-compression/reader-viewer'/a.version.lower();rows=[]
for option in ['full','compact','scan','none']:
 out=a.output/option;out.mkdir();flags=dict(READER='BibleReader',SEARCH_INDEX=option,VERSION=a.version,PRUNE=1,PROFILE=0,TEST_FONT=0,WORK_PROFILE=0,NATIVE_STREAM=0,FAST_BITS=8,FAST_NATIVE=0,VERSE_BOOST=0,SEARCH_CLEAR_COMPLETE=0,BENCH_QUERY=-1,NATIVE_OPEN_TEST=1,NATIVE_PAGE_TEST=1,LINK_MAP=str(out.resolve()/'link.map'))
 with(out/'build.log').open('w')as f:subprocess.run(['make','-C',str(APP),*[f'{k}={v}'for k,v in flags.items()]],stdout=f,stderr=subprocess.STDOUT,check=True)
 stem='BibleReader'+(''if a.version=='KJV'else'-'+a.version)+(''if option=='full'else'-'+option);b=(APP/(stem+'.OS3KApp')).read_bytes();search=(APP/'search.bin').read_bytes();other=sum((data/f).stat().st_size for f in ['container.bin','verses.bin'])+(APP/'pruning.bin').stat().st_size+1848
 for suffix in ['OS3KApp','elf']:shutil.copyfile(APP/(stem+'.'+suffix),out/(stem+'.'+suffix))
 for f in ['BibleReader.c','Search.c','Search.h','HuffmanDecoder.c','Makefile','search_options.py','NoIndex.h','SearchBench.h','SearchMatch.h','SearchModesBench.h']:shutil.copyfile(APP/f,out/f)
 for f in APP.glob('*.su'):shutil.copyfile(f,out/f.name)
 executable=0;section='';mapped=False
 for line in (out/'link.map').read_text().splitlines():
  if 'Linker script and memory map'in line:mapped=True
  if not mapped:continue
  m=re.match(r'^ (\.\S+)(?:\s+(.*))?$',line)
  if m:section=m[1];tail=m[2]or''
  else:tail=line.strip()
  m=re.match(r'0x[0-9a-f]+\s+0x([0-9a-f]+)\s+.+',tail)
  if m and(section=='.text'or section.startswith('.text.')):executable+=int(m[1],16);section=''
 rows.append(dict(index=option,rom_bytes=len(b),index_bytes=len(search),common_text_navigation_bytes=other,app_code_assets_bytes=len(b)-other-len(search),executable_bytes=executable,a5_bytes=struct.unpack_from('>I',b,8)[0],sha256=hashlib.sha256(b).hexdigest(),flags=flags,binary=str(out.resolve()/(stem+'.OS3KApp'))))
(a.output/'results.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows,indent=2))

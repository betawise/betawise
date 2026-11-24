#!/usr/bin/env python3
from prototype_support import prototype_app, prototype_test
from pathlib import Path
import subprocess,json,struct,shutil
root=Path(__file__).resolve().parents[3];app=prototype_app();out=root/'.research-work/bible-compression/god-production';out.mkdir(exist_ok=True);rows=[]
for name,bits,native,clear,boost in [('baseline',8,0,0,0),('clear',8,0,1,0),('fast10',10,1,0,0),('fast12',12,1,0,0),('verse',8,0,0,1),('verse-fast12',12,1,0,1)]:
 d=out/name;d.mkdir(exist_ok=True)
 flags=dict(READER='BibleReader',SEARCH_INDEX='full',VERSION='KJV',PRUNE=1,PROFILE=0,TEST_FONT=0,WORK_PROFILE=0,NATIVE_STREAM=0,NATIVE_OPEN_TEST=1,NATIVE_PAGE_TEST=1,FAST_BITS=bits,FAST_NATIVE=native,SEARCH_CLEAR_COMPLETE=clear,VERSE_BOOST=boost,BENCH_QUERY=-1)
 with(d/'build.log').open('w')as f:subprocess.run(['make','-C',str(app),*[f'{k}={v}' for k,v in flags.items()]],stdout=f,stderr=subprocess.STDOUT,check=True)
 b=(app/'BibleReader.OS3KApp').read_bytes();shutil.copyfile(app/'BibleReader.OS3KApp',d/'BibleReader.OS3KApp');shutil.copyfile(app/'BibleReader.elf',d/'BibleReader.elf')
 rows.append(dict(name=name,rom_bytes=len(b),a5_bytes=struct.unpack_from('>I',b,8)[0],wide_bytes=(app/'wide.bin').stat().st_size,verse_bytes=(app/'verse-boost.bin').stat().st_size,flags=flags))
(out/'results.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows))

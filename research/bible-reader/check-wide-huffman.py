#!/usr/bin/env python3
from prototype_support import prototype_app, prototype_test
from pathlib import Path
import subprocess,json,hashlib
r=Path(__file__).resolve().parents[3];a=prototype_app();o=r/'.research-work/bible-compression/god-wide-host';o.mkdir(exist_ok=True);data=r/'.research-work/bible-compression/reader-viewer/kjv';rows=[]
for bits in [8,10,12]:
 table=o/f'table{bits}.bin';subprocess.run(['python3',str(a/'wide_huffman.py'),str(data/'container.bin'),str(bits),str(table)],check=True)
 src=(a/'native_check.c').read_text();src+='\nconst unsigned char BibleFastHuffmanTable[]={'+','.join(map(str,table.read_bytes() or b'\0'))+'};\n'
 c=o/f'check{bits}.c';c.write_text(src);exe=o/f'check{bits}';subprocess.run(['cc','-O2','-DBIBLE_HUFFMAN=1','-DBIBLE_RAW_ONLY=1',f'-DBIBLE_FAST_BITS={bits}','-I'+str(a),str(c),str(a/'HuffmanDecoder.c'),'-o',str(exe)],check=True)
 dest=o/f'decode{bits}.bin';subprocess.run([str(exe),str(data/'container.bin'),str(dest)],check=True);rows.append(dict(bits=bits,bytes=dest.stat().st_size,sha256=hashlib.sha256(dest.read_bytes()).hexdigest()))
assert len({x['sha256'] for x in rows})==1
(o/'results.json').write_text(json.dumps(dict(status='passed',chapters=1189,results=rows),indent=2)+'\n')

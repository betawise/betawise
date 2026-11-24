#!/usr/bin/env python3
"""Cross-check the fixed-workspace C decoder against every source verse."""
import argparse
import hashlib
import json
from prototype_support import prototype_app, prototype_test
from pathlib import Path
import struct
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
APP=prototype_app()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path)
    ap.add_argument('--container',type=Path,default=APP/'bible.bin')
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    is_huffman=args.container.read_bytes()[:8]in [b'KJVHUF01',b'KJVHUF02',b'KJVDNS01']
    if args.source is None:args.source=ROOT/('.research-work/bible-compression/ascii-huffman/kjv-ascii.json'if is_huffman else'.research-work/bible-compression/kjv.json')
    chapters=[('\n'.join(c)+'\n').encode()for b in json.loads(args.source.read_text(encoding='utf-8-sig'))for c in b['chapters']]
    with(out/'native.log').open('w')as log:
        for driver in (['native_check']if is_huffman else['native_check','seek_prepare']):
            subprocess.run(['cc',f'-DBIBLE_HUFFMAN={int(is_huffman)}',f'-DBIBLE_DENSE={int(args.container.read_bytes()[:8]==b"KJVDNS01")}','-O2','-Wall','-Wextra',str(APP/('HuffmanDecoder.c'if is_huffman else'Decoder.c')),str(APP/(driver+'.c')),'-o',str(out/driver)],check=True,stdout=log,stderr=subprocess.STDOUT)
        decoded=out/'chapters.bin'
        subprocess.run([str(out/'native_check'),str(args.container),str(decoded)],check=True,stdout=log,stderr=subprocess.STDOUT)
        if not is_huffman:subprocess.run([str(out/'seek_prepare'),str(args.container),str(out/'seek.bin')],check=True,stdout=log,stderr=subprocess.STDOUT)
    data=decoded.read_bytes();count=struct.unpack_from('>I',data)[0];p=4
    assert count==len(chapters)==1189
    seen=set()
    for _ in range(count):
        chapter,n=struct.unpack_from('>II',data,p);p+=8
        assert chapter not in seen and data[p:p+n]==chapters[chapter],chapter
        seen.add(chapter);p+=n
    assert p==len(data)
    result=dict(status='passed',codec='huffman'if is_huffman else'arithmetic',source_sha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),chapters=count,text_bytes=sum(map(len,chapters)),reverse_chapter_decode_exact=True,decoder_sha256=hashlib.sha256((APP/('HuffmanDecoder.c'if is_huffman else'Decoder.c')).read_bytes()).hexdigest())
    if not is_huffman:
        seek=(out/'seek.bin').read_bytes();assert seek[:8]==b'KJVSEEK1'
        points=struct.unpack_from('>I',seek,12)[0]
        result.update(checkpoint_suffix_replays_exact=points,checkpoint_bytes=len(seek),checkpoint_sha256=hashlib.sha256(seek).hexdigest())
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()

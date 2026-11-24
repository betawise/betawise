#!/usr/bin/env python3
"""Build/validate a portable C benchmark using the actual NKJV format resources."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from measure import APP, ROOT, read_formatting, uvarint, heading_chunks, bundle
from compact import compact
from small_huffman import heading_pool


def checksum(raw):
    value=0x12345678
    for byte in raw:
        value=(((value<<5)|(value>>27))^byte)&0xffffffff
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--small-headings',action='store_true')
    parser.add_argument('--inline-headings-path',type=Path)
    parser.add_argument('--repetitions',type=int,default=100)
    args=parser.parse_args()
    out=args.output.resolve()
    out.mkdir(parents=True,exist_ok=False)
    artifacts=ROOT/'.research-work/bible-compression'
    data=read_formatting('nkjv')
    inputs={
        'base':APP/'build/data/nkjv/container.bin',
        'inline':artifacts/'nkjv-format-all-inline-book/container.bin',
        'learned':artifacts/'nkjv-format-all-inline-learned/container.bin',
        'font':artifacts/'nkjv-format-learned/book-32-runs_huffman.bin',
        'layout':artifacts/'nkjv-format-sidecars-final/layout-translation-huffman_small.bin',
        'heads':artifacts/'nkjv-format-sidecars-final/headings.bin',
        'heads_raw':out/'raw-headings.bin',
        'prediction':artifacts/'nkjv-format-all-inline-book/prediction-header.bin',
        'prediction_learned':artifacts/'nkjv-format-all-inline-learned/prediction-header.bin',
        'layout_defaults':artifacts/'nkjv-format-all-inline-book/layout-defaults.bin',
    }
    header,heads=heading_chunks(data['headings'],'front_pool')
    raw,_=bundle(data,b'',[b'']*len(heads),header,heads,layout_override=[b'']*len(heads))
    raw,_=compact(raw)
    inputs['heads_raw'].write_bytes(raw)
    heading_sizes={16:inputs['heads'].stat().st_size,'raw16':inputs['heads_raw'].stat().st_size}
    if args.small_headings:
        strings=sorted({text for ch in data['headings']for _,_,text in ch})
        for block_size in [4,1]:
            offsets=bytearray();text=bytearray();previous=''
            for i,word in enumerate(strings):
                if not i%block_size:
                    offsets.extend(struct.pack('>I',len(text)));previous=''
                prefix=0
                while prefix<min(len(previous),len(word))and previous[prefix]==word[prefix]:prefix+=1
                assert prefix<256
                text.append(prefix);text.extend(word[prefix:].encode()+b'\0');previous=word
            header=uvarint(len(strings))+bytes(offsets)+bytes(text)
            header,_=heading_pool(header,block_size)
            raw,_=bundle(data,b'',[b'']*len(heads),header,heads,layout_override=[b'']*len(heads))
            raw,_=compact(raw)
            path=out/f'headings-{block_size}.bin';path.write_bytes(raw)
            inputs[f'heads{block_size}']=path
            heading_sizes[block_size]=len(raw)
        for name in ['learned','prediction_learned']:
            inputs.pop(name)
    if args.inline_headings_path:
        assert args.small_headings
        inputs['inline']=args.inline_headings_path.resolve()/'container.bin'
    for name,index in [('base',APP/'build/data/nkjv/search.bin'),('inline',artifacts/'nkjv-format-all-inline-book/search.bin'),('learned',artifacts/'nkjv-format-all-inline-learned/search.bin')]:
        if args.small_headings and name=='learned':continue
        if args.inline_headings_path and name=='inline': index=args.inline_headings_path/'search.bin'
        raw=index.read_bytes();vocabulary,words=struct.unpack_from('>HH',raw,8)
        start=20+4*(vocabulary+1)
        path=out/(name+'-normalization.bin')
        path.write_bytes(raw[start:start+(14*words+7)//8]+b'\0\0')
        inputs[name+'_norm']=path
    assembly=['.section .rodata']
    for name,path in inputs.items():
        assembly += ['.balign 2',f'.global asset_{name}',f'asset_{name}:',f'.incbin {json.dumps(str(path))}']
    (out/'BenchData.S').write_text('\n'.join(assembly)+'\n')
    source=['#include "FormatBench.h"','#include "BenchData.h"']
    for name in inputs:
        source.append(f'extern const uint8_t asset_{name}[];')
    def blob(name):
        return '{asset_'+name+','+str(inputs[name].stat().st_size)+'}'if name else '{0,0}'
    resources=[]
    resource_specs=[('base','heads',False,4),('inline','heads',True,4),('learned','heads',True,4),('base','heads_raw',False,4)]
    if args.small_headings:
        resource_specs=[('base','heads',False,4),('inline','heads',True,4),('base','heads_raw',False,4),('base','heads4',False,2),('base','heads1',False,0)]
    for body,head,inline,shift in resource_specs:
        resources.append('{'+','.join([blob(body),blob(body+'_norm'),blob('font'),blob('layout'),blob(head),blob('prediction_learned'if body=='learned'else'prediction'),blob('layout_defaults'),'13056',str(int(inline)),str(int(head!='heads_raw')),str(shift),str(int(bool(args.inline_headings_path)and body=='inline'))])+'}')
    source.append('const BenchAssets BenchResources[] = {'+','.join(resources)+'};')
    cases=[]
    expectations=[]
    firsts=[]
    book=0
    book_starts=[]
    for item in json.loads((APP/'build/data/nkjv/source.json').read_text()):
        book_starts.append(len(firsts))
        firsts.extend([book]*len(item['chapters']));book+=1
    labels=[('Genesis 1',0),('John 3',book_starts[42]+2),('1 Cor 13',book_starts[45]+12),('Psalm 119',book_starts[18]+118)]
    for ci,(label,chapter)in enumerate(labels):
        ch=data['atoms'][chapter]
        styles=bytes(a['style']&7 for a in ch);layouts=bytes(a['layout']for a in ch)
        rawheads=bytearray(uvarint(len(data['headings'][chapter])))
        previous=0
        for atom,level,text in data['headings'][chapter]:
            encoded=text.encode('ascii');rawheads+=uvarint(atom-previous)+bytes([level])+uvarint(len(encoded))+encoded;previous=atom
        for name,raw in [('styles',styles),('layouts',layouts),('heads',bytes(rawheads))]:
            source.append(f'static const uint8_t case_{ci}_{name}[]={{'+','.join(map(str,raw))+'};')
        cases.append('{'+f'{chapter},{firsts[chapter]},{len(ch)},'+','.join('{case_'+str(ci)+'_'+n+','+str(len(v))+'}'for n,v in [('styles',styles),('layouts',layouts),('heads',rawheads)])+'}')
        expected={}
        for heads in [0,1]:
            wire=bytearray();atom=0
            heading_groups={}
            for at,level,text in data['headings'][chapter]:heading_groups.setdefault(at,[]).append((level,text))
            for match in re.finditer(rb'\S+|\s',data['blocks'][chapter]):
                text=match.group()
                if text in (b' ',b'\n'):
                    wire+=b'W'+text
                else:
                    if heads:
                        for level,title in heading_groups.get(atom,[]):
                            title=title.encode('ascii');wire+=b'H'+bytes([2,level])+len(title).to_bytes(2,'big')+title
                    wire+=b'A'+bytes([styles[atom],layouts[atom]])+len(text).to_bytes(2,'big')+text
                    atom+=1
            expected[str(heads)]=dict(hash=checksum(wire),bytes=len(wire),atoms=len(ch),headings=len(data['headings'][chapter])if heads else 0)
        expected['raw']=dict(hash=checksum(data['blocks'][chapter]),bytes=len(data['blocks'][chapter]),atoms=0,headings=0)
        expectations.append(dict(name=label,chapter=chapter,expected=expected))
    source.append('const BenchCase BenchCases[] = {'+','.join(cases)+'};')
    variants=[('raw_text',0,0,0),('prepared_no_heads',0,1,0),('sidecar_no_heads',0,2,0),('inline_no_heads',1,3,0),('inline_learned_no_heads',2,3,0),('prepared_heads',0,1,1),('sidecar_heads',0,2,1),('sidecar_raw_heads',3,2,1),('inline_heads',1,3,1),('inline_learned_heads',2,3,1)]
    if args.small_headings:
        variants=[('raw_text',0,0,0),('prepared_no_heads',0,1,0),('sidecar_no_heads',0,2,0),('inline_no_heads',1,3,0),('prepared_heads',0,1,1),('sidecar_heads',0,2,1),('sidecar_raw_heads',2,2,1),('inline_heads',1,3,1),('sidecar_heads4',3,2,1),('sidecar_heads1',4,2,1)]
    if args.inline_headings_path:
        variants=[(n.replace('inline_', 'inline_headings_'),a,2 if a==1 else m,h)for n,a,m,h in variants]
    source.append('const BenchVariant BenchVariants[] = {'+','.join('{'+f'{a},{m},{h}'+'}'for n,a,m,h in variants)+'};')
    (out/'BenchData.c').write_text('\n'.join(source)+'\n')
    (out/'BenchData.h').write_text('#include "FormatBench.h"\ntypedef struct { unsigned asset,mode,headings; } BenchVariant;\n#define BENCH_CASE_COUNT 4\n#define BENCH_VARIANT_COUNT 10\nextern const BenchAssets BenchResources[];\nextern const BenchCase BenchCases[];\nextern const BenchVariant BenchVariants[];\n')
    manifest={name:dict(path=str(path),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())for name,path in inputs.items()}
    (out/'fixtures.json').write_text(json.dumps(dict(cases=expectations,variants=variants,assets=manifest,heading_bytes=heading_sizes),indent=2))
    compiler=['cc','-Wl,-z,noexecstack','-DHOST_BENCH','-O2','-Wall','-Wextra','-I'+str(APP),'-I'+str(HERE),'-I'+str(out),str(HERE/'FormatBench.c'),str(APP/'Decoder.c'),str(out/'BenchData.c'),str(out/'BenchData.S'),str(HERE/'HostBench.c'),'-o',str(out/'bench')]
    subprocess.run(compiler,check=True)
    raw=subprocess.check_output([str(out/'bench'),str(args.repetitions)],text=True)
    (out/'host-raw.txt').write_text(raw)
    results=[]
    for line in raw.splitlines():
        c,v,seconds,h,n,atoms,heads=line.split()
        c,v=int(c),int(v);mode=variants[v][2];show=variants[v][3]
        want=expectations[c]['expected']['raw'if mode==0 else str(show)]
        actual=dict(hash=int(h),bytes=int(n),atoms=int(atoms),headings=int(heads))
        assert actual==want,(expectations[c]['name'],variants[v],actual,want)
        results.append(dict(case=expectations[c]['name'],variant=variants[v][0],seconds=float(seconds),**actual))
    (out/'host-results.json').write_text(json.dumps(dict(status='passed',repetitions=args.repetitions,results=results),indent=2))
    print(json.dumps(results,indent=2))


if __name__=='__main__':main()

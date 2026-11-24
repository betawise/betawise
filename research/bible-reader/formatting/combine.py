#!/usr/bin/env python3
"""Combine independently verified styles, best layout defaults and heading pools."""
import argparse
import json
from pathlib import Path
from measure import read_formatting, singleton_runs, style_events, sparse_styles, byte_huffman, heading_chunks, bundle, uvarint
from compact import compact


def layout_parts(blob, component=2):
    count=int.from_bytes(blob[4:6],'big')
    width=blob[6]
    codec_size=int.from_bytes(blob[8:10],'big')
    heading_size=int.from_bytes(blob[10:12],'big')
    header_size=13+codec_size+heading_size
    bitmap_size=(count+7)//8
    bitmap=blob[header_size:header_size+bitmap_size]
    present=sum(x.bit_count()for x in bitmap)
    table=header_size+bitmap_size
    payload=table+(present+1)*width
    assert blob[header_size-1]==component or present==0
    chunks=[]
    rank=0
    for ci in range(count):
        if bitmap[ci//8]>>(ci%8)&1:
            start=int.from_bytes(blob[table+rank*width:table+(rank+1)*width],'big')
            end=int.from_bytes(blob[table+(rank+1)*width:table+(rank+2)*width],'big')
            chunks.append(blob[payload+start:payload+end])
            rank+=1
        else:
            chunks.append(b'')
    return blob[12:12+codec_size],chunks


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--styles',type=Path,required=True)
    parser.add_argument('--layouts',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    style_options=json.loads((args.styles/'results.json').read_text())['versions']
    layout_options=json.loads((args.layouts/'results.json').read_text())['versions']
    results={}
    for version in style_options:
        data=read_formatting(version)
        layout_name=layout_options[version]['best'].replace('/','-')
        layout_header,layouts=layout_parts((args.layouts/f'{version}-{layout_name}.bin').read_bytes())
        if not any(layouts):
            layout_header=b''
        head_header,heads=heading_chunks(data['headings'],'front_pool')
        variants={}
        for projection_name,projection in [('typography',7),('all_styles',15)]:
            choices=style_options[version]['variants']
            name=min((n for n in choices if n.startswith(projection_name+'/')),key=lambda n:choices[n]['bytes'])
            if 'singleton_runs'in name:
                header,styles=singleton_runs(data['atoms'],projection)
                if name.endswith('_huffman'):
                    model,styles=byte_huffman(styles)
                    header+=model
            else:
                _,coordinate,codec=name.split('/')
                header,styles=sparse_styles(data['atoms'],style_events(data['atoms'],projection),codec,coordinate)
            full_header=uvarint(len(header))+header+layout_header
            raw,_=bundle(data,full_header,styles,head_header,heads,layout_override=layouts)
            blob,record=compact(raw)
            record.update(style_codec=name,layout_codec=layout_name,
                style_payload_bytes=sum(map(len,styles)),layout_payload_bytes=sum(map(len,layouts)),
                heading_record_bytes=sum(map(len,heads)),heading_dictionary_bytes=len(head_header))
            variants[projection_name]=record
            (args.output/f'{version}-{projection_name}.bin').write_bytes(blob)
        results[version]=variants
        print(version,variants,flush=True)
    (args.output/'results.json').write_text(json.dumps(dict(status='passed',versions=results),indent=2))


if __name__=='__main__':
    main()

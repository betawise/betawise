#!/usr/bin/env python3
"""Compare NKJV sidecar encodings with common heading/layout resources."""
import argparse
import hashlib
import json
from pathlib import Path
from measure import APP, read_formatting, sparse_styles, style_events, singleton_runs, byte_huffman, heading_chunks, bundle, uvarint
from layout import profiles
from word_defaults import book_predictions
from small_huffman import compress, heading_pool
from compact import compact


def make_file(data, header, styles=None, layouts=None, heading_header=b'', headings=None):
    count=len(data['atoms'])
    styles=styles if styles is not None else [b'']*count
    layouts=layouts if layouts is not None else [b'']*count
    raw,_=bundle(data,header,styles,heading_header,headings,layout_override=layouts)
    return compact(raw)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    data=read_formatting('nkjv')
    head_header,heads=heading_chunks(data['headings'],'front_pool')
    head_header,head_stats=heading_pool(head_header)
    head_file,head_sizes=make_file(data,b'',heading_header=head_header,headings=heads)
    (args.output/'headings.bin').write_bytes(head_file)
    candidates={}
    payloads={}
    for profile in ['translation','book','chapter']:
        table,events=profiles(data,profile)
        for codec in ['packed_varint','gamma','rice','huffman_fast','huffman_small']:
            header,chunks=sparse_styles(data['atoms'],events,codec if codec in ['gamma','rice']else 'packed_varint','atoms')
            if codec=='huffman_fast':
                model,chunks=byte_huffman(chunks)
                header+=model
            elif codec=='huffman_small':
                model,chunks=compress(chunks)
                header+=model
            header=bytes([['translation','book','chapter'].index(profile)])+uvarint(len(table))+table+header
            blob,record=make_file(data,header,layouts=chunks)
            name=profile+'/'+codec
            candidates[name]=dict(**record,exceptions=sum(map(len,events)))
            payloads[name]=(header,chunks)
            (args.output/('layout-'+name.replace('/','-')+'.bin')).write_bytes(blob)
    best=min(candidates,key=lambda n:candidates[n]['bytes'])
    layout_header,layouts=payloads[best]
    prediction,residual=book_predictions(data)
    styles_results={}
    for default,atoms,default_header in [('none',data['atoms'],b''),('book',residual,prediction)]:
        for codec in ['varint_state','packed_varint','gamma','rice','runs','runs_huffman_fast','runs_huffman_small']:
            if codec.startswith('runs'):
                header,chunks=singleton_runs(atoms,7)
                if codec=='runs_huffman_fast':
                    model,chunks=byte_huffman(chunks)
                    header+=model
                elif codec=='runs_huffman_small':
                    model,chunks=compress(chunks)
                    header+=model
            else:
                header,chunks=sparse_styles(atoms,style_events(atoms,7),codec,'atoms')
            header=default_header+header
            font_blob,font_sizes=make_file(data,header,styles=chunks)
            combined,record=make_file(data,uvarint(len(header))+header+layout_header,styles=chunks,layouts=layouts,heading_header=head_header,headings=heads)
            name=default+'/'+codec
            format_only,_=make_file(data,uvarint(len(header))+header+layout_header,styles=chunks,layouts=layouts)
            record.update(format_only_bytes=len(format_only),style_bytes=len(font_blob),separate_total=len(font_blob)+len(head_file)+candidates[best]['bytes'],style_huffman_default_bytes=len(default_header))
            styles_results[name]=record
            (args.output/('all-'+name.replace('/','-')+'.bin')).write_bytes(combined)
            (args.output/('style-'+name.replace('/','-')+'.bin')).write_bytes(font_blob)
    hashes={name:hashlib.sha256((APP/'build/data/nkjv'/name).read_bytes()).hexdigest()for name in ['container.bin','search.bin','pruning.bin','verses.bin']}
    expected=json.loads((APP/'build/data/nkjv/results.json').read_text())['resource_sha256']
    assert all(value==expected[name]for name,value in hashes.items())
    report=dict(status='passed',version='nkjv',source_sha256=data['source_sha256'],source_flags=data['flags'],
        layout_default=data['default_layout'],layout_best=best,layout_candidates=candidates,
        heading=head_sizes,heading_huffman=head_stats,styles=styles_results,resource_hashes=hashes)
    (args.output/'results.json').write_text(json.dumps(report,indent=2))
    print('Layout:',best,candidates[best],flush=True)
    print('Headings:',head_sizes,flush=True)
    print(json.dumps(styles_results,indent=2))


if __name__=='__main__':
    main()

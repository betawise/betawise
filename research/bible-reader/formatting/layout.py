#!/usr/bin/env python3
"""Compare layout defaults by translation, book and chapter, with sparse escapes."""
import argparse
from collections import Counter
import json
from pathlib import Path
from compact import compact
from measure import read_formatting, sparse_styles, bundle, byte_huffman, singleton_runs, uvarint


def profiles(data, kind):
    if kind=='translation':
        values=[data['default_layout']]*len(data['atoms'])
        table=bytes([data['default_layout']])
    elif kind=='chapter':
        values=[Counter(a['layout']for a in ch if a['first']).most_common(1)[0][0] if ch else 0 for ch in data['atoms']]
        table=bytes(values)
    else:
        counts={book:Counter()for book in data['chapter_books']}
        for book,ch in zip(data['chapter_books'],data['atoms']):
            counts[book].update(a['layout']for a in ch if a['first'])
        defaults={book:count.most_common(1)[0][0]for book,count in counts.items()}
        values=[defaults[book]for book in data['chapter_books']]
        table=bytes(defaults.values())
    events=[]
    for ch,default in zip(data['atoms'],values):
        changes=[(i,a['layout'])for i,a in enumerate(ch)if a['layout']!=(default if a['first']else 0)]
        rebuilt=dict(changes)
        assert all(rebuilt.get(i,default if a['first']else 0)==a['layout']for i,a in enumerate(ch))
        events.append(changes)
    return table,events


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    results={}
    for version in ('kjv','nkjv','esv','niv','nasb','csb'):
        data=read_formatting(version)
        variants={}
        for profile in ('translation','book','chapter'):
            table,events=profiles(data,profile)
            for codec in ('packed_varint','gamma','rice','packed_varint_huffman'):
                header,chunks=sparse_styles(data['atoms'],events,'packed_varint'if codec.endswith('huffman')else codec,'atoms')
                if codec.endswith('huffman'):
                    model,chunks=byte_huffman(chunks)
                    header+=model
                global_header=bytes([('translation','book','chapter').index(profile)])+uvarint(len(table))+table+header
                raw,sizes=bundle(data,global_header,[b'']*len(chunks),layout_override=chunks)
                blob,record=compact(raw)
                name=f'{profile}/{codec}'
                record.update(exceptions=sum(map(len,events)),profile_bytes=len(table),payload_bytes=sum(map(len,chunks)))
                variants[name]=record
                (args.output/f'{version}-{name.replace("/","-")}.bin').write_bytes(blob)
        best=min(variants,key=lambda name:variants[name]['bytes'])
        record=variants[best]
        results[version]=dict(best=best,variants=variants)
        print(version,best,record,flush=True)
        (args.output/'results.json').write_text(json.dumps(dict(status='partial',versions=results),indent=2))
    (args.output/'results.json').write_text(json.dumps(dict(status='passed',versions=results),indent=2))


if __name__=='__main__':
    main()

#!/usr/bin/env python3
"""Test cost-limited per-word defaults for italics, bold and small caps together."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import struct
from measure import read_formatting, singleton_runs, sparse_styles, style_events, bundle, uvarint, read_varint
from compact import compact
from small_huffman import compress
from nkjv import make_file

WORD=re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)*")


def predictions(data, scope, minimum_gain):
    vocabulary=sorted({w.lower()for ch in data['atoms']for a in ch for w in WORD.findall(a['text'])})
    ids={w:i for i,w in enumerate(vocabulary)}
    books={book:i for i,book in enumerate(dict.fromkeys(data['chapter_books']))}
    groups=1 if scope=='global'else 66
    bitmap_size=(groups+7)//8
    counts=defaultdict(lambda:defaultdict(lambda:[0,0,0,0]))
    keys=[]
    for book,ch in zip(data['chapter_books'],data['atoms']):
        group=0 if scope=='global'else books[book]
        row=[]
        for a in ch:
            words=WORD.findall(a['text'].lower())
            key=words[0]if len(words)==1 else None
            row.append(key)
            if key:
                count=counts[key][group]
                count[0]+=1
                for bit in range(3):
                    count[bit+1]+=bool(a['style']&(1<<bit))
        keys.append(row)
    selected={}
    for word,by_group in counts.items():
        attributes={}
        for bit in range(3):
            gain=sum(max(0,2*c[bit+1]-c[0])for c in by_group.values())
            if gain<minimum_gain:
                continue
            bitmap=bytearray(bitmap_size)
            for group,c in by_group.items():
                if 2*c[bit+1]>c[0]:
                    bitmap[group//8]|=1<<(group%8)
            if any(bitmap):
                attributes[bit]=bytes(bitmap)
        if attributes:
            selected[word]=attributes
    header=bytearray(b'WDP2'+bytes([scope=='book'])+struct.pack('>H',groups)+uvarint(len(selected)))
    previous=0
    for word,attributes in sorted(selected.items()):
        header.extend(uvarint(ids[word]-previous));previous=ids[word]
        header.append(sum(1<<bit for bit in attributes))
        for bit in range(3):
            if bit in attributes:
                header.extend(attributes[bit])
    # Apply only the model recovered from the serialized table.
    decoded={}
    count,pos=read_varint(header,7)
    previous=0
    for _ in range(count):
        delta,pos=read_varint(header,pos);previous+=delta
        mask=header[pos];pos+=1
        attributes={}
        for bit in range(3):
            if mask&(1<<bit):
                attributes[bit]=bytes(header[pos:pos+bitmap_size]);pos+=bitmap_size
        decoded[vocabulary[previous]]=attributes
    assert pos==len(header) and decoded==selected
    residual=[]
    for book,ch,row in zip(data['chapter_books'],data['atoms'],keys):
        group=0 if scope=='global'else books[book]
        chapter=[]
        for a,key in zip(ch,row):
            default=sum(((bitmap[group//8]>>(group%8))&1)<<bit for bit,bitmap in decoded.get(key,{}).items())
            value=a['style']^default
            assert value^default==a['style']
            chapter.append(dict(a,style=value))
        residual.append(chapter)
    return bytes(header),residual,dict(words=len(selected),profile_bytes=len(header),predicted_attributes={str(bit):sum(bit in attrs for attrs in selected.values())for bit in range(3)})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    data=read_formatting('nkjv')
    results={}
    for scope,threshold in [('global',4),('book',4),('book',12),('book',32)]:
        table,atoms,stats=predictions(data,scope,threshold)
        for codec in ['runs','runs_huffman','gamma','rice']:
            if codec.startswith('runs'):
                header,chunks=singleton_runs(atoms,7)
                if codec=='runs_huffman':
                    model,chunks=compress(chunks);header+=model
            else:
                header,chunks=sparse_styles(atoms,style_events(atoms,7),codec,'atoms')
            blob,record=make_file(data,table+header,styles=chunks)
            name=f'{scope}-{threshold}/{codec}'
            results[name]=dict(**record,**stats)
            (args.output/(name.replace('/','-')+'.bin')).write_bytes(blob)
        print(scope,threshold,stats,flush=True)
    report=dict(status='passed',version='nkjv',variants=results,best=min(results,key=lambda n:results[n]['bytes']))
    (args.output/'results.json').write_text(json.dumps(report,indent=2))
    print('Best',report['best'],results[report['best']],flush=True)


if __name__=='__main__':
    main()

#!/usr/bin/env python3
"""Predict small caps from vocabulary/book/chapter defaults; escape exceptions."""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import re
from measure import read_formatting, singleton_runs, style_events, sparse_styles, bundle, heading_chunks, uvarint, read_varint
from compact import compact

WORD=re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)*")


def book_predictions(data):
    """The same four-word/book predictor, decoded before applying its residuals."""
    vocabulary = sorted({m.group().lower() for raw in data['blocks'] for m in WORD.finditer(raw.decode())})
    word_ids = {word: i for i, word in enumerate(vocabulary)}
    books = {book: i for i, book in enumerate(dict.fromkeys(data['chapter_books']))}
    keys = []
    marked = Counter()
    for chapter in data['atoms']:
        row = []
        for atom in chapter:
            words = WORD.findall(atom['text'].lower())
            key = words[0] if len(words) == 1 else None
            row.append(key)
            if key and atom['style'] & 4:
                marked[key] += 1
        keys.append(row)
    candidates = sorted(word for word, count in marked.items() if count >= 4)
    frequencies = {word: [Counter() for _ in books] for word in candidates}
    for book, chapter, row in zip(data['chapter_books'], data['atoms'], keys):
        for atom, key in zip(chapter, row):
            if key in frequencies:
                frequencies[key][books[book]][bool(atom['style'] & 4)] += 1
    header = bytearray([1, len(candidates)])
    previous = 0
    for word in candidates:
        header.extend(uvarint(word_ids[word] - previous))
        previous = word_ids[word]
        bitmap = bytearray((len(books) + 7) // 8)
        for book, frequency in enumerate(frequencies[word]):
            bitmap[book // 8] |= int(frequency[True] > frequency[False]) << (book % 8)
        header.extend(bitmap)
    decoded = {}
    pos = 2
    previous = 0
    for _ in range(header[1]):
        delta, pos = read_varint(header, pos)
        previous += delta
        bitmap = header[pos:pos + (len(books) + 7) // 8]
        pos += len(bitmap)
        decoded[vocabulary[previous]] = bitmap
    assert pos == len(header)
    transformed = []
    for book, chapter, row in zip(data['chapter_books'], data['atoms'], keys):
        group = books[book]
        result = []
        for atom, key in zip(chapter, row):
            bitmap = decoded.get(key, b'')
            prediction = (((bitmap[group // 8] >> (group % 8)) & 1) * 4) if bitmap else 0
            residual = atom['style'] ^ prediction
            assert residual ^ prediction == atom['style']
            result.append(dict(atom, style=residual))
        transformed.append(result)
    return bytes(header), transformed


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    data=read_formatting('kjv')
    vocabulary=sorted({m.group().lower()for raw in data['blocks']for m in WORD.finditer(raw.decode())})
    word_ids={word:i for i,word in enumerate(vocabulary)}
    keys=[]
    counts=Counter()
    for ch in data['atoms']:
        row=[]
        for atom in ch:
            matches=WORD.findall(atom['text'].lower())
            key=matches[0]if len(matches)==1 else None
            row.append(key)
            if key and atom['style']&4:
                counts[key]+=1
        keys.append(row)
    candidate_words=sorted(word for word,count in counts.items()if count>=4)
    book_ids={book:i for i,book in enumerate(dict.fromkeys(data['chapter_books']))}
    heads_header,heads=heading_chunks(data['headings'],'front_pool')
    results={}
    for scope in ['global','book','chapter']:
        groups=1 if scope=='global'else len(book_ids)if scope=='book'else len(keys)
        group_ids=[0 if scope=='global'else book_ids[book]if scope=='book'else ci for ci,book in enumerate(data['chapter_books'])]
        word_groups={word:[Counter()for _ in range(groups)]for word in candidate_words}
        for ci,(ch,row)in enumerate(zip(data['atoms'],keys)):
            for atom,key in zip(ch,row):
                if key in word_groups:
                    word_groups[key][group_ids[ci]][bool(atom['style']&4)]+=1
        defaults={word:[int(c[True]>c[False])for c in cs]for word,cs in word_groups.items()}
        header=bytearray([['global','book','chapter'].index(scope),len(candidate_words)])
        previous=0
        for word in candidate_words:
            header.extend(uvarint(word_ids[word]-previous));previous=word_ids[word]
            bits=bytearray((groups+7)//8)
            for group,value in enumerate(defaults[word]):
                bits[group//8]|=value<<(group%8)
            header.extend(bits)
        pos=2
        previous=0
        decoded_defaults={}
        for _ in range(header[1]):
            delta,pos=read_varint(header,pos)
            previous+=delta
            bits=header[pos:pos+(groups+7)//8]
            pos+=len(bits)
            decoded_defaults[vocabulary[previous]]=[(bits[group//8]>>(group%8))&1 for group in range(groups)]
        assert pos==len(header) and decoded_defaults==defaults
        defaults=decoded_defaults
        for projection_name,projection in [('typography',7),('all_styles',15)]:
            transformed=[]
            exceptions=0
            for ci,(ch,row)in enumerate(zip(data['atoms'],keys)):
                chapter=[]
                for atom,key in zip(ch,row):
                    predict=defaults[key][group_ids[ci]]*4 if key in defaults else 0
                    residual=(atom['style']&projection)^predict
                    exceptions+=bool(residual&4)
                    chapter.append(dict(atom,style=residual))
                    assert (residual^predict)==(atom['style']&projection)
                transformed.append(chapter)
            for codec in ['singleton_runs','gamma','rice']:
                if codec=='singleton_runs':
                    style_header,styles=singleton_runs(transformed,projection)
                else:
                    style_header,styles=sparse_styles(transformed,style_events(transformed,projection),codec,'atoms')
                full_header=bytes(header)+style_header
                raw,_=bundle(data,full_header,styles)
                styled,style_sizes=compact(raw)
                raw,_=bundle(data,full_header,styles,heads_header,heads)
                combined,sizes=compact(raw)
                name=f'{scope}/{projection_name}/{codec}'
                results[name]=dict(style_bytes=len(styled),combined_bytes=len(combined),prediction_table_bytes=len(header),smallcaps_exceptions=exceptions,**sizes)
                (args.output/f'{name.replace("/","-")}.bin').write_bytes(combined)
        print(scope,'word defaults',defaults.keys(),'table',len(header),'bytes',flush=True)
    report=dict(status='passed',words=candidate_words,variants=results)
    (args.output/'results.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(sorted((v['combined_bytes'],k)for k,v in results.items())[:6],indent=2))


if __name__=='__main__':
    main()

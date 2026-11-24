#!/usr/bin/env python3
"""Build ASCII-first word/phrase Huffman and arithmetic comparison resources."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import subprocess
from compare_translations import front_dictionary, compress_blocks, TOKEN, packed_json
from context_models import dictionary_letters, parse_grammar
from device_ascii import convert
from measure import canonical, codes_for, pack, unpack

HERE=Path(__file__).resolve().parent


def huffman(blocks,metadata,dictionary,sequences,rules,out,label):
    out.mkdir(parents=True,exist_ok=True)
    lex=front_dictionary(dictionary)
    dictionary_letters(lex,len(dictionary),out/'dictionary.bin')
    letter_blob=(out/'dictionary.bin').read_bytes()
    alphabet=len(dictionary)+len(rules)
    freq=Counter(s for seq in sequences for s in seq)
    lengths=codes_for({s:max(1,freq[s])for s in range(alphabet)})
    codes=canonical([lengths[s]for s in range(alphabet)]);maximum=max(lengths.values())
    ordered=sorted(codes,key=lambda s:(codes[s][1],s));table=bytearray(struct.pack('>HH',maximum,alphabet))
    for n in range(1,maximum+1):
        group=[s for s in ordered if codes[s][1]==n]
        first=ordered.index(group[0])if group else 0
        table.extend(struct.pack('>IHH',codes[group[0]][0]if group else 0,first,len(group)))
    table.extend(b''.join(struct.pack('>H',s)for s in ordered))
    # 8-bit direct table: zero means take the bitwise long-code path.
    fast=[0]*256
    for s,(code,n)in codes.items():
        if n<=8:
            for prefix in range(code<<(8-n),(code+1)<<(8-n)):fast[prefix]=(s<<5)|n
    table.extend(struct.pack('>256I',*fast))
    payload,index=bytearray(),bytearray()
    for raw,seq in zip(blocks,sequences):
        encoded=pack(seq,codes)
        index.extend(struct.pack('>IIII',len(payload),len(encoded),len(seq),len(raw)))
        payload.extend(encoded)
    meta=packed_json(metadata);grammar=b''.join(struct.pack('>HH',a,b)for a,b in rules)
    header=struct.pack('>8s8I',b'KJVHUF01',len(meta),len(dictionary),len(letter_blob),len(table),len(blocks),sum(map(len,blocks)),len(rules),maximum).ljust(64,b'\0')
    image=header+meta+letter_blob+table+grammar+index+payload
    (out/'container.bin').write_bytes(image)
    for raw,seq,i in zip(blocks,sequences,range(len(blocks))):
        offset,n,count,_=struct.unpack_from('>IIII',index,16*i)
        decoded=unpack(payload[offset:offset+n],codes,count);assert decoded==seq
        expanded=[];stack=[]
        for s in decoded:
            stack.append(s)
            while stack:
                s=stack.pop()
                if s<len(dictionary):expanded.append(dictionary[s])
                else:
                    a,b=rules[s-len(dictionary)];stack.extend([b,a])
        assert ''.join(expanded).encode()==raw
    result=dict(label=label,bytes=len(image),payload_bytes=len(payload),dictionary_bytes=len(letter_blob),huffman_table_bytes=len(table),grammar_bytes=len(grammar),dictionary_entries=len(dictionary),max_word_bytes=max(len(w)for w in dictionary),max_code_bits=maximum,verified_chapters=len(blocks),sha256=hashlib.sha256(image).hexdigest())
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source',type=Path);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    books=json.loads(args.source.read_text(encoding='utf-8-sig'))
    for b in books:
        b['chapters']=[[convert(v)for v in c]for c in b['chapters']]
    ascii_source=out/'kjv-ascii.json';ascii_source.write_bytes(packed_json(books))
    blocks=[('\n'.join(c)+'\n').encode('ascii')for b in books for c in b['chapters']]
    metadata=[];start=0
    for b in books:metadata.append([b['name'],start,len(b['chapters'])]);start+=len(b['chapters'])
    dictionary=sorted({t for b in blocks for t in TOKEN.findall(b.decode())});ids={w:i for i,w in enumerate(dictionary)}
    sequences=[[ids[t]for t in TOKEN.findall(b.decode())]for b in blocks]
    results=[huffman(blocks,metadata,dictionary,sequences,[],out/'word','ASCII word Huffman')]
    seqs=sequences;rules=[]
    for _ in range(16):
        pairs=Counter(p for seq in seqs for p in zip(seq,seq[1:]))
        selected=[p for p,n in pairs.most_common(128)if n>=16]
        mapping={p:len(dictionary)+len(rules)+i for i,p in enumerate(selected)};rules.extend(selected)
        updated=[]
        for seq in seqs:
            new=[];i=0
            while i<len(seq):
                symbol=mapping.get(tuple(seq[i:i+2]))
                if symbol is not None:new.append(symbol);i+=2
                else:new.append(seq[i]);i+=1
            updated.append(new)
        seqs=updated
    results.append(huffman(blocks,metadata,dictionary,seqs,rules,out/'phrase','ASCII phrase Huffman'))
    binary=out/'context-codec'
    subprocess.run(['g++','-std=c++17','-O2',str(HERE/'context_codec.cpp'),'-o',str(binary)],check=True)
    arithmetic=compress_blocks(blocks,metadata,binary,out/'arithmetic','ASCII contextual arithmetic')
    report=dict(ascii_source=str(ascii_source),source_sha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),ascii_sha256=hashlib.sha256(ascii_source.read_bytes()).hexdigest(),max_chapter_bytes=max(map(len,blocks)),huffman=results,arithmetic=arithmetic)
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()

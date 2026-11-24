#!/usr/bin/env python3
"""Trial: heading text in the main Huffman stream; canonical search skips it."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from measure import APP,ROOT,read_formatting
from compress_text import build_container
from build_index import build_index,grammar_summaries


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    data=read_formatting('nkjv')
    base=APP/'build/data/nkjv'
    baseline=(base/'container.bin').read_bytes()
    metadata=json.loads(baseline[64:64+int.from_bytes(baseline[8:12],'big')])
    blocks=[]
    for atoms,raw,headings in zip(data['atoms'],data['blocks'],data['headings']):
        output=bytearray();previous=0
        for atom,level,title in headings:
            position=atoms[atom]['byte']if atom<len(atoms)else len(raw)
            output.extend(raw[previous:position]);output.extend(bytes([3,16|level])+title.encode('ascii')+b'\x04');previous=position
        output.extend(raw[previous:])
        pos=0;plain=bytearray();decoded=[]
        while pos<len(output):
            byte=output[pos];pos+=1
            if byte==3:
                level=output[pos]&15;pos+=1;end=output.index(4,pos)
                decoded.append((len(plain),level,output[pos:end].decode()));pos=end+1
            else:plain.append(byte)
        assert bytes(plain)==raw
        assert decoded==[(atoms[a]['byte']if a<len(atoms)else len(raw),l,t)for a,l,t in headings]
        blocks.append(bytes(output))
    image,words=build_container(blocks,metadata)
    index,vocabulary=build_index(data['blocks'],words)
    pruning=grammar_summaries(words,image)
    start=words.index('\x03');end=words.index('\x04')
    n=len(words);offset=64+int.from_bytes(image[8:12],'big')+int.from_bytes(image[16:20],'big')+int.from_bytes(image[20:24],'big')
    count=int.from_bytes(image[32:36],'big');flags=bytearray((count+7)//8)
    for rule in range(count):
        first=int.from_bytes(image[offset+4*rule:offset+4*rule+2],'big');second=int.from_bytes(image[offset+4*rule+2:offset+4*rule+4],'big')
        special=lambda child:child in (start,end)if child<n else bool(flags[(child-n)//8]>>(child-n)%8&1)
        if special(first)or special(second):flags[rule//8]|=1<<(rule%8)
    for name,blob in [('container.bin',image),('search.bin',index),('pruning.bin',pruning),('heading-rules.bin',flags)]:
        (out/name).write_bytes(blob)
    # Only the trial search decoder knows about heading regions. Production is unchanged.
    header=(APP/'Search.h').read_text().replace('    uint16_t selection_origin;','    uint16_t selection_origin;\n    uint16_t heading_active;')
    source=(APP/'Search.c').read_text().replace('extern const uint8_t BibleGrammarSummary[];',f'''extern const uint8_t BibleGrammarSummary[];
static const unsigned heading_begin={start},heading_end={end};
static const uint8_t heading_rules[]={{{','.join(map(str,flags))}}};''')
    source=source.replace('            search->verse = 1;','            search->verse = 1;\n            search->heading_active = 0;')
    target='            unsigned rule = terminal - search->decoder.dictionary_word_count;'
    source=source.replace(target,target+'''
            if(ReadBit(heading_rules,rule)) {
                if(!BibleDecoderExpandRule(&search->decoder,terminal)) return BIBLE_SEARCH_ERROR;
                continue;
            }
            if(search->heading_active) continue;''')
    source=source.replace('        word = ReadNormalizedWord(search, terminal);','''        if((unsigned)terminal==heading_begin) { search->heading_active=1;continue; }
        if((unsigned)terminal==heading_end) { search->heading_active=0;continue; }
        if(search->heading_active) continue;
        word = ReadNormalizedWord(search, terminal);''')
    (out/'Search.h').write_text(header);(out/'Search.c').write_text(source)
    for name in ['BibleFormat.h','Decoder.h','Decoder.c']:(out/name).write_bytes((APP/name).read_bytes())
    sys.path.insert(0,str(ROOT/'betawise/tests/biblewise'))
    import check
    check.APP=out
    corpus=json.loads((base/'source.json').read_text());chapters=[ch for b in corpus for ch in b['chapters']]
    cases=check.check_search(out,out,chapters)
    delta=len(image)+len(index)+len(pruning)+len(flags)-sum((base/name).stat().st_size for name in ['container.bin','search.bin','pruning.bin'])
    result=dict(status='passed',version='NKJV',source_sha256=data['source_sha256'],headings=sum(map(len,data['headings'])),container_bytes=len(image),container_delta=len(image)-len(baseline),search_delta=len(index)-(base/'search.bin').stat().st_size,heading_rule_flags_bytes=len(flags),total_delta=delta,search_cases=cases,words=len(words),vocabulary=vocabulary,production_search_unchanged=False,production_files_untouched=True)
    (out/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))


if __name__=='__main__':main()

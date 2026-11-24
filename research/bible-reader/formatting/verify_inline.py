#!/usr/bin/env python3
"""Verify actual C-decoded inline style streams against every original atom."""
import argparse
import json
from pathlib import Path
import struct
import subprocess
from measure import APP, ROOT, read_formatting
from word_defaults import book_predictions


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trials',type=Path,nargs='+')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    executable=args.output/'decoder'
    subprocess.run(['cc','-O2','-I'+str(APP),str(ROOT/'betawise/tests/biblewise/decoder_check.c'),str(APP/'Decoder.c'),'-o',str(executable)],check=True)
    version=json.loads((args.trials[0]/'results.json').read_text()).get('version','kjv')
    data=read_formatting(version)
    books={book:i for i,book in enumerate(dict.fromkeys(data['chapter_books']))}
    book_header,predicted=book_predictions(data)
    from learned import predictions
    learned_header,learned_atoms,_=predictions(data,'book',32)
    results={}
    for trial in args.trials:
        report=json.loads((trial/'results.json').read_text())
        assert report['status']=='passed'
        assert report.get('version','kjv')==version
        layout_header=(trial/'layout-defaults.bin').read_bytes() if (trial/'layout-defaults.bin').exists() else b''
        projection=7 if report['projection']=='typography'else 15
        mode=report.get('word_defaults','none')
        atoms=predicted if mode=='book'else learned_atoms if mode=='learned'else data['atoms']
        prediction_header=book_header if mode=='book'else learned_header if mode=='learned'else b''
        assert (trial/'prediction-header.bin').read_bytes()==prediction_header
        raw=subprocess.check_output([str(executable),str(trial/'container.bin')])
        count=struct.unpack_from('>I',raw)[0]
        pos=4
        checked=0
        for expected_chapter in reversed(range(count)):
            chapter,size=struct.unpack_from('>II',raw,pos)
            assert chapter==expected_chapter
            pos+=8
            block=raw[pos:pos+size]
            pos+=size
            starts={atom['byte']:atom['style']&projection for atom in atoms[chapter]}
            offset=state=0
            plain=bytearray()
            actual_layout={}
            index=0
            while index<len(block):
                byte=block[index]
                index+=1
                if byte==2:
                    assert index+1<len(block) and all(0x10<=c<0x20 for c in block[index:index+2])
                    assert offset not in actual_layout
                    actual_layout[offset]=((block[index]&15)<<4)|(block[index+1]&15)
                    index+=2
                elif 0x10<=byte<0x20:
                    state=byte&15
                else:
                    if offset in starts:
                        assert state==starts[offset],(trial,chapter,offset,state,starts[offset])
                        checked+=1
                    plain.append(byte)
                    offset+=1
            if report.get('layout_mode')=='inline':
                scope=report['layout_defaults']
                group=0 if scope=='translation'else books[data['chapter_books'][chapter]]if scope=='book'else chapter
                default=layout_header[group]
                for atom in data['atoms'][chapter]:
                    actual=actual_layout.get(atom['byte'],default if atom['first']else 0)
                    assert actual==atom['layout'],(trial,chapter,atom['byte'],actual,atom['layout'])
                expected={a['byte']:a['layout']for a in data['atoms'][chapter]if a['layout']!=(default if a['first']else 0)}
                assert actual_layout==expected
            else:
                assert not actual_layout
            assert bytes(plain)==data['blocks'][chapter]
        assert pos==len(raw) and checked==sum(map(len,atoms))
        results[trial.name]=dict(status='passed',atoms_checked=checked,chapters=count)
    (args.output/'results.json').write_text(json.dumps(dict(status='passed',trials=results),indent=2))
    print(json.dumps(results,indent=2))


if __name__=='__main__':
    main()

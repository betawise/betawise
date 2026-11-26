#!/usr/bin/env python3
"""Summarize no-table and native-file-index MAME experiments."""
import json
from pathlib import Path
import struct

HERE=Path(__file__).resolve().parent
BUILD=HERE/'build'
SUITES=('baseline-file-bench','none-bench-nkjv','file-bench-nkjv',
        'none-interactions-nkjv','file-interactions-nkjv','none-retention-kjv','file-retention-kjv')


def read_suite(name):
    path=BUILD/name
    report=json.loads((path/'results.json').read_text())
    assert report['status']=='passed'
    assert 'PASS BibleWise suite' in (path/'mame.log').read_text()
    checks=json.loads((path/'checks.json').read_text())
    trace=json.loads((path/'timings.json').read_text())
    rows=[]
    for index,check in enumerate(checks,1):
        observing=False
        begin=None
        actual=[]
        observer=[]
        write_begin=None
        writes=[]
        decode_begin=None
        decodes=[]
        for event in (event for event in trace if event['check']==index):
            phase=event['phase']
            if phase==712:
                observing=True
            elif phase==713:
                observing=False
            elif phase==710:
                assert begin is None
                begin=event['time']
            elif phase==711:
                assert begin is not None
                (observer if observing else actual).append(1000*(event['time']-begin))
                begin=None
            elif phase==714:
                write_begin=event['time']
            elif phase==715:
                assert write_begin is not None
                writes.append(1000*(event['time']-write_begin))
                write_begin=None
            elif phase==3:
                decode_begin=event['time']
            elif phase==2 and decode_begin is not None:
                decodes.append(1000*(event['time']-decode_begin))
                decode_begin=None
        editor=(path/f'editor-{index:02}.bin').read_bytes()
        gap_start,gap_end=struct.unpack_from('>II',editor,40)
        file_bytes=(path/f'chapter-{index:02}.bin').stat().st_size
        rows.append(dict(name=check['name'],actual_lookup_ms=actual,observer_lookup_ms=observer,
                         index_write_ms=writes,decode_ms=decodes,
                         chapter_logical_bytes=file_bytes-(gap_end-gap_start),
                         chapter_captured_bytes=file_bytes,editor_gap_bytes=gap_end-gap_start))
    if name.startswith('file-'):
        validations=json.loads((path/'file-index-validation.json').read_text())
        assert len(validations)==len(checks)
    return dict(name=name,path=str(path),checkpoints=report['checkpoints'],status=report['status'],measurements=rows)


def main():
    sizes=json.loads((BUILD/'file-experiment-sizes.json').read_text())
    baseline=sizes['variants'][0]
    for variant in sizes['variants']:
        variant['a5_saved']=baseline['a5']-variant['a5']
        variant['rom_added']=variant['rom']-baseline['rom']
    suites=[read_suite(name)for name in SUITES]
    result=dict(scope='Research only; production remains three A5 tables. Neo 3.21, Century Schoolbook Tiny. Lookup figures are reconstruction/index-read CPU time, not whole key-to-screen latency.',
        sdk_hash=sizes['sdk_hash'],release_sizes=sizes['variants'],suites=suites,
        total_passed_checkpoints=sum(s['checkpoints']for s in suites),
        file_index=dict(location='Opaque B8 records at tail of the same chapter file',entry_bytes=6,
            entries_per_record=32,record_overhead=4,max_index_bytes=1080,
            current_verse_cache_bytes=10,extra_decode_stack_frame_bytes=1288,
            notes='No extra workspace file. All indexed verse bodies and offset ordering are checked against source at every checkpoint.'),
        no_table=dict(index_bytes=0,current_verse_cache_bytes=10,
            strategy='Every cold miss scans from chapter beginning; same-verse cache hits do not scan.'),
        focus_lifecycle='Production saves TextEditorSavePosition and closes the chapter file on MSG_KILLFOCUS. It does not delete it; focus regain reopens it.',
        retained_ram_delta=dict(scope='A5 plus captured chapter-file data, excluding unchanged file bookkeeping and transient stack',
            none=-1044,file_genesis_1=-850,file_psalm_119=40))
    (BUILD/'file-experiment-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Passed checkpoints:',result['total_passed_checkpoints'])
    print(json.dumps(sizes['variants'],indent=2))


if __name__=='__main__':main()

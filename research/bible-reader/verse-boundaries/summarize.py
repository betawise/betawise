#!/usr/bin/env python3
"""Summarize the captured, exact-validated boundary-table experiment."""
import hashlib
import json
from pathlib import Path
import struct

HERE=Path(__file__).resolve().parent
BUILD=HERE/'build'
SUITES={
    'baseline':'final-bench-baseline',
    'one':'final-bench-one',
    'sparse':'final-bench-sparse-retry',
    'kjv-one':'kjv-one',
    'kjv-sparse':'kjv-sparse',
    'interactions-one':'interactions-one',
    'interactions-sparse':'interactions-sparse'}


def scan_timings(directory):
    checks=json.loads((directory/'checks.json').read_text())
    trace=json.loads((directory/'timings.json').read_text())
    rows=[]
    for index,check in enumerate(checks,1):
        observing=False
        begin=None
        actual=[]
        observer=[]
        for event in (event for event in trace if event['check']==index):
            phase=event['phase']
            if phase==712:
                observing=True
            elif phase==710:
                assert begin is None
                begin=event['time']
            elif phase==711:
                assert begin is not None
                (observer if observing else actual).append(1000*(event['time']-begin))
                begin=None
            elif phase==713:
                observing=False
        assert begin is None
        rows.append(dict(name=check['name'],boundary_scans=len(actual),
            boundary_scan_ms=sum(actual),individual_scans_ms=actual,
            observer_scan_ms=sum(observer)))
    return rows


def main():
    sizes=[]
    for variant in ('baseline','one','sparse'):
        image=BUILD/variant/'app/build/NKJV/BibleWise-NKJV.OS3KApp'
        raw=image.read_bytes()
        rom,ram=struct.unpack_from('>II',raw,4)
        assert rom==len(raw)
        # The standard CRT loads the relocation-loop bound into D2 here.
        # Reading the measured image avoids relinking against a newer live SDK.
        entry=struct.unpack_from('>I',raw,0x84)[0]
        startup=raw[entry:entry+0x100]
        marker=startup.index(b'\x24\x3c')
        assert startup[marker+6:marker+8]==b'\x4a\x82'
        got=struct.unpack_from('>I',startup,marker+2)[0]
        row=dict(variant=variant,a5_bytes=ram,got_bytes=got,rom_bytes=rom,
            image_sha256=hashlib.sha256(raw).hexdigest(),
            evidence='Measured release image header and standard CRT relocation-loop bound')
        if sizes:
            row['a5_saved']=sizes[0]['a5_bytes']-ram
            row['rom_added']=rom-sizes[0]['rom_bytes']
        sizes.append(row)
    suites=[]
    for name,directory_name in SUITES.items():
        directory=BUILD/directory_name
        report=json.loads((directory/'results.json').read_text())
        assert report['status']=='passed'
        assert 'PASS BibleWise suite' in (directory/'mame.log').read_text()
        suites.append(dict(name=name,path=str(directory),checkpoints=report['checkpoints'],
            status=report['status'],timings=scan_timings(directory)))
    result=dict(scope='Research only; production applet unchanged. The measured shared-SDK snapshot has a 2624-byte baseline.',
        release_sizes=sizes,suites=suites,total_passed_checkpoints=sum(s['checkpoints']for s in suites),
        payloads=dict(baseline=1062,one_index=352,one_cache=8,sparse_index=22,sparse_cache=10),
        measurement='710/711 delimit actual boundary scans. 712/713 identify test-only observer lookups; observer saves/restores the cache, and its scan time is excluded.',
        interpretation='Cold reconstruction latency, not total key-to-screen latency. A cached lookup performs no boundary scan; normal native scrolling has no production boundary-table lookup.')
    output=BUILD/'results.json'
    output.write_text(json.dumps(result,indent=2)+'\n')
    print('Passed checkpoints:',result['total_passed_checkpoints'])
    print(json.dumps(sizes,indent=2))


if __name__=='__main__':main()

#!/usr/bin/env python3
"""Collect release sizes, CPU timings, stack frames and exact-validated results."""
import hashlib
import json
from pathlib import Path
import re
import struct
from prepare import APP, BUILD

SUITES = ['bench-baseline-kjv','bench-fresh-kjv','bench-direct-kjv','bench-copy-kjv',
          'bench-baseline-nkjv','bench-combined-nkjv','baseline-copy-validation',
          'combined-copy-validation','combined-usage','combined-vendor-small']


def main():
    sizes=[]
    for variant in ('baseline','fresh-file','direct-decode','native-copy','combined'):
        app=BUILD/variant/'app'
        for version in ('KJV','NKJV'):
            stem='BibleWise'+(''if version=='KJV'else'-'+version)
            image=(app/'build'/version/(stem+'.OS3KApp')).read_bytes()
            rom,a5=struct.unpack_from('>II',image,4)
            frames={}
            for line in (app/'build'/version/'BibleWise.su').read_text().splitlines():
                for name in ('DecodeChapterToFile','CopySelectedVerses'):
                    if re.search(r':'+name+r'\t',line):frames[name]=int(line.split('\t')[1])
            sizes.append(dict(variant=variant,version=version,rom=rom,a5=a5,frames=frames,sha256=hashlib.sha256(image).hexdigest()))
    suites=[]
    for name in SUITES:
        path=BUILD/name;r=json.loads((path/'results.json').read_text());assert r['status']=='passed'
        checks=json.loads((path/'checks.json').read_text());trace=json.loads((path/'timings.json').read_text());rows=[]
        for i,check in enumerate(checks,1):
            events=[e for e in trace if e['check']==i]
            def span(first,last):
                start=next((e['time']for e in events if e['phase']==first),None)
                end=next((e['time']for e in events if e['phase']==last and start is not None and e['time']>start),None)
                return 1000*(end-start)if end is not None else None
            row=dict(name=check['name'],load_ms=span(1,4),decode_write_ms=span(3,2),copy_ms=span(900,901),erase_ms=span(910,911))
            if check.get('clipboard'):row['clipboard_bytes']=len((path/f'clipboard-{i:02}.bin').read_bytes())
            rows.append(row)
        suites.append(dict(name=name,status='passed',checkpoints=r['checkpoints'],timings=rows))
    allocation={}
    for name in ('baseline-copy-validation','combined-copy-validation'):
        events=json.loads((BUILD/name/'allocations.json').read_text())
        allocation[name]=[dict(check=i,chapter_minimum=max(max(e['length'],e['reservation'])for e in events if e['check']==i),
            clipboard_peak_capacity=max(e['clip_capacity']for e in events if e['check']==i),
            clipboard_peak_length=max(e['clip_length']for e in events if e['check']==i))for i in(2,4,11)]
    bound_results=[json.loads((BUILD/('bound-check-'+v+'.json')).read_text())for v in('KJV','NKJV')]
    identical=[]
    for left,right in [('bench-baseline-kjv','bench-direct-kjv'),('bench-baseline-kjv','bench-copy-kjv'),('bench-baseline-nkjv','bench-combined-nkjv')]:
        for i in range(1,15):
            def content(name):
                p=BUILD/name;raw=(p/f'chapter-{i:02}.bin').read_bytes();a,b=struct.unpack_from('>II',(p/f'editor-{i:02}.bin').read_bytes(),40);return raw[:a]+raw[b:]
            assert content(left)==content(right),(left,right,i)
        identical.append(dict(left=left,right=right,identical_chapters=14))
    archive=json.loads((APP/'archive.json').read_text())
    for row in sizes:
        if row['variant']=='baseline':
            assert row['sha256'] in (archive['release'][row['version']]['sha256'],
                archive['release'][row['version']].get('research_rebuild_sha256'))
    report=dict(status='passed',baseline_commit='2c579923c406b98655f0c863cd0a33db4b74771c',release=sizes,
        suites=suites,checkpoints=sum(s['checkpoints']for s in suites),bounds=bound_results,
        allocation=allocation,identical_chapters=identical,
        notes=['Timings are emulated Neo time, not host wall time. Copy timing excludes notice painting.',
               'Compiler stack frames exclude callees and firmware; they are not complete peak-stack measurements.',
               'Last-file capacity includes reclaimable tail RAM. Chapter minimum is max(logical length,reservation).',
               'Native copy retains reclaimable clipboard slack after shortening the logical length.',
               'HUF03 reuses high16 of chapter word4 for a capacity bound; low16 retains source length. No resource-size growth.',
               'Initial Genesis total-load phase starts before the harness attaches; use Reload Genesis for totals.'])
    (BUILD/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS',report['checkpoints'],'MAME checkpoints;',sum(r['chapter_profiles']for r in bound_results),'host chapter profiles')


if __name__=='__main__':main()

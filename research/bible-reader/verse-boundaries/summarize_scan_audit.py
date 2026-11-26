#!/usr/bin/env python3
"""Preserve the faster-scanner and cache-free-index measurements."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BUILD=HERE/'build'


def suite(name):
    path=BUILD/name
    result=json.loads((path/'results.json').read_text())
    assert result['status']=='passed'
    assert 'PASS BibleWise suite' in (path/'mame.log').read_text()
    checks=json.loads((path/'checks.json').read_text())
    trace=json.loads((path/'timings.json').read_text())
    rows=[]
    for index,check in enumerate(checks,1):
        observing=False
        start=None
        times=[]
        for event in (event for event in trace if event['check']==index):
            if event['phase']==712:
                observing=True
            elif event['phase']==713:
                observing=False
            elif event['phase']==710:
                assert start is None
                start=event['time']
            elif event['phase']==711:
                assert start is not None
                if not observing:
                    times.append(1000*(event['time']-start))
                start=None
        rows.append(dict(name=check['name'],lookup_calls=len(times),lookup_ms=sum(times),individual_ms=times))
    return dict(name=name,checkpoints=result['checkpoints'],status='passed',measurements=rows)


def main():
    names=('fast-bench-nkjv','file-nocache-bench-nkjv','fast-interactions','file-nocache-interactions')
    suites=[suite(name)for name in names]
    result=dict(scope='Research only. Current NKJV, Neo 3.21, Century Schoolbook Tiny. Lookup CPU times exclude the isolated non-mutating test observer; not full action latency.',
        releases=json.loads((BUILD/'scan-audit-sizes.json').read_text()),suites=suites,
        total_checkpoints=sum(s['checkpoints']for s in suites),
        scanner_change='Refill 256-byte blocks with at most a 14-byte seam copy; parse consecutive ordinary bytes together. Removes per-byte memmove and repeated lookahead refill. No format changes or new markers.',
        cache_free_change='Remove all static current-verse boundary/cache/limit objects. Read six-byte index entries into local stack storage and return fields by value. Caret-to-verse still binary-searches the file index.',
        timing_definitions='Cold in earlier reports meant a cache miss for the last requested verse, not a hardware/disk cache miss or decompression. Cache-free mode has no cold/warm distinction.',
        future_unmeasured='Byte-position binary search over existing self-identifying verse-number records; optional three-byte per-verse opaque ordinal records at heading-inclusive starts. No binary stream prototype was implemented.')
    (BUILD/'scan-audit-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Passed',result['total_checkpoints'],'checkpoints')


if __name__=='__main__':main()

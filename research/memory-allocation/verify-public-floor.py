#!/usr/bin/env python3
"""Independently verify public-compaction captures and their integrity."""
from pathlib import Path
import gzip
import hashlib
import json
import sys

HERE = Path(__file__).resolve().parent
OUT = Path(sys.argv[1]).resolve()
manifest = json.loads((OUT / 'manifest.json').read_text())
layouts = {
    'as3000': (0x1042, 0x4558, 0x354e, 0x36000, 0x1c000),
    'neo_3_01': (0x109a, 0x69c0, 0x35a6, 0x76000, 0x5c000),
    'neo_3_21': (0x10d2, 0x1509c, 0x35de, 0x76000, 0x5c000),
}
assert {r['rom'] for r in manifest['runs']} == set(layouts)
for name, digest in manifest['scripts'].items():
    assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == digest
for run in manifest['runs']:
    name = run['rom']
    log = (OUT / name / 'mame.log').read_bytes()
    assert hashlib.sha256(log).hexdigest() == run['log_sha256']
    assert b'PASS public floor qualification complete ' + name.encode() in log
    assert b'FAIL ' not in log
    assert hashlib.sha256((OUT / name / 'probe.lua').read_bytes()).hexdigest() == run['probe_sha256']
    first, payload, floor_addr, data, oldfloor = layouts[name]
    assert len(run['artifacts']) == 5
    for artifact in run['artifacts']:
        blob = (OUT / artifact['file']).read_bytes()
        assert hashlib.sha256(blob).hexdigest() == artifact['gzip_sha256']
        raw = gzip.decompress(blob)
        assert hashlib.sha256(raw).hexdigest() == artifact['raw_sha256']
        num = lambda a: int.from_bytes(raw[a:a+4], 'big')
        seeded = 'floor-seeded' in artifact['file']
        before = 'floor-before' in artifact['file'] or seeded
        reserved = 'floor-reserved' in artifact['file']
        limit = oldfloor - (4096 if reserved else 0)
        assert num(floor_addr) == limit
        nextptr = payload
        for i, (live, minimum) in enumerate(zip((200, 1000, 1600), (0, 800, 2000))):
            saved = ((256, 1300, 1400 if seeded else 1600)[i] if before else live)
            e = first + i * 72
            ptr, cap = num(e), num(e+12)
            assert ptr == nextptr and ptr + cap <= limit
            assert num(e+4) == live and num(e+8) == saved
            assert num(e+16) == minimum and num(e+20) == 123
            retained = max(live, saved, minimum)
            assert cap >= retained
            assert raw[ptr:ptr+retained] == bytes(((i+1)*53+j*17)&255 for j in range(retained))
            for j, off in enumerate((0, 4, 12, 20)):
                assert num(data+i*32+j*4) == num(e+off)
            nextptr = ptr + cap
        if 'floor-compacted' in artifact['file']:
            assert nextptr == payload + 3584
        if reserved:
            assert limit-nextptr < 512
            assert raw[limit:oldfloor] == bytes((j*29+7)&255 for j in range(4096))
print('PASS three ROMs, 15 RAM captures, public compaction, saved-length changes, payloads, mirrors and heap guards')

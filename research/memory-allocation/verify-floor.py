#!/usr/bin/env python3
"""Verify saved experiment hashes, file state, payloads and reserved guard."""
from pathlib import Path
import gzip
import hashlib
import json
import sys

HERE = Path(sys.argv[1]).resolve()
ROOT = Path(__file__).resolve().parents[3]
manifest = json.loads((HERE / 'manifest.json').read_text())
layouts = {
    'as3000': (0x1042, 0x4558, 0x354e, 0x36000, 0x1c000),
    'neo_3_01': (0x109a, 0x69c0, 0x35a6, 0x76000, 0x5c000),
    'neo_3_21': (0x10d2, 0x1509c, 0x35de, 0x76000, 0x5c000),
}
assert {r['rom'] for r in manifest['runs']} == set(layouts)
for run in manifest['runs']:
    log = (HERE / run['rom'] / 'mame.log').read_bytes()
    assert hashlib.sha256(log).hexdigest() == run['log_sha256']
    assert b'PASS floor qualification complete ' + run['rom'].encode() in log
    assert b'FAIL ' not in log
    first, payload, floor_addr, data, oldfloor = layouts[run['rom']]
    assert len(run['artifacts']) == 3
    for artifact in run['artifacts']:
        blob = (HERE / artifact['file']).read_bytes()
        assert hashlib.sha256(blob).hexdigest() == artifact['gzip_sha256']
        raw = gzip.decompress(blob)
        assert hashlib.sha256(raw).hexdigest() == artifact['raw_sha256']
        num = lambda addr: int.from_bytes(raw[addr:addr+4], 'big')
        reserved = 'floor-reserved' in artifact['file']
        limit = oldfloor - (4096 if reserved else 0)
        assert num(floor_addr) == limit
        nextptr = payload
        for i, (live, saved, minimum) in enumerate(zip(
                (200, 1000, 1600), (256, 1300, 1700), (0, 800, 2000))):
            entry = first + i * 72
            ptr, cap = num(entry), num(entry+12)
            assert ptr == nextptr and ptr+cap <= limit
            assert num(entry+4) == live and num(entry+8) == saved
            assert num(entry+16) == minimum and num(entry+20) == 123
            assert cap >= max(saved, minimum)
            assert raw[ptr:ptr+max(saved, minimum)] == bytes(
                ((i+1)*53+j*17) & 255 for j in range(max(saved, minimum)))
            for j, off in enumerate((0, 4, 12, 20)):
                assert num(data+i*32+j*4) == num(entry+off)
            nextptr = ptr+cap
        if reserved:
            assert raw[limit:oldfloor] == bytes((j*29+7) & 255 for j in range(4096))
scan = json.loads((HERE / 'pool-candidates.json').read_text())
assert len(scan) == 8
for row in scan:
    if ':' not in row['source']:
        assert hashlib.sha256((ROOT / row['source']).read_bytes()).hexdigest() == row['sha256']
assert sum(len(row['candidates']) for row in scan) == 42
assert scan[-1]['bytes_with_low_bit_set'] == 0 and 'excluded' in scan[-1]
print('PASS three-ROM floor logs, nine RAM captures, file bindings/payloads/guard, pool input hashes')

#!/usr/bin/env python3
"""Verify preserved allocation evidence hashes and allocator state assertions."""
from pathlib import Path
import gzip
import hashlib
import json
import sys

HERE = Path(sys.argv[1]).resolve()
manifest = json.loads((HERE / 'manifest.json').read_text())
assert {r['rom'] for r in manifest['runs']} == {'as3000', 'neo_3_01', 'neo_3_21'}
for run in manifest['runs']:
    log = (HERE / run['rom'] / 'mame.log').read_bytes()
    assert hashlib.sha256(log).hexdigest() == run['log_sha256']
    assert b'PASS allocation qualification complete ' + run['rom'].encode() in log
    assert b'FAIL ' not in log
    for artifact in run['artifacts']:
        data = (HERE / artifact['file']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == artifact['gzip_sha256']
        raw = gzip.decompress(data)
        assert hashlib.sha256(raw).hexdigest() == artifact['raw_sha256']
        a5 = 0x30000 if run['rom'] == 'as3000' else 0x70000
        number = lambda address, size: int.from_bytes(raw[address:address + size], 'big')
        if run['rom'] == 'neo_3_21':
            assert number(a5 + 0x494, 4) == 0x5DBE
            assert number(a5 + 0x48E, 4) == 8192
            assert number(a5 + 0x492, 2) == 4
            assert number(a5 + 0x800 + 0x494, 4) == 0x5DBE
            assert number(a5 + 0x800 + 0x492, 2) == 16
        else:
            assert number(a5 + 0x494, 4) == 0
            assert number(a5 + 0x48E, 4) == 0
census = json.loads((Path(__file__).resolve().parent / 'vendor-census.json').read_text())
assert census['image_count'] == len(census['images']) == 56
assert sum(bool(row['scratch_calls']) for row in census['images']) == 5
print('PASS three ROM capture/log hashes, vendor allocator state, and 56-image census')

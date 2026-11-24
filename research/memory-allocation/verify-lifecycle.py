#!/usr/bin/env python3
"""Verify captured bounded startup experiments, not full Manager transactions."""
from pathlib import Path
import gzip
import hashlib
import json
import sys

HERE = Path(sys.argv[1]).resolve()
manifest = json.loads((HERE / 'manifest.json').read_text())
layouts = {
    'as3000': (0x3d800,0x354e,0x34ce,0xd82,0x3568),
    'neo_3_01': (0x7d800,0x35a6,0x3526,0xdda,0x35c0),
    'neo_3_21': (0x7d800,0x35de,0x355e,0xe0a,0x35f8),
}
assert {row['rom'] for row in manifest['runs']} == set(layouts)
for row in manifest['runs']:
    log = (HERE / row['rom'] / 'mame.log').read_bytes()
    assert hashlib.sha256(log).hexdigest() == row['log_sha256']
    assert b'FAIL ' not in log
    assert b'PASS lifecycle qualification complete ' + row['rom'].encode() in log
    top, floor_addr, bases, descriptors, marker = layouts[row['rom']]
    assert len(row['artifacts']) == 4
    for artifact in row['artifacts']:
        compressed = (HERE / artifact['file']).read_bytes()
        assert hashlib.sha256(compressed).hexdigest() == artifact['gzip_sha256']
        raw = gzip.decompress(compressed)
        assert hashlib.sha256(raw).hexdigest() == artifact['raw_sha256']
        num = lambda a: int.from_bytes(raw[a:a+4], 'big')
        label = Path(artifact['file']).name
        if label == 'warm-valid.ram.gz':
            assert num(floor_addr) == top-8192
            assert num(top-4096) == top-8192 and num(top-4092) == 4096
            assert num(top-8192) == 0x5a5a5a5a
            assert num(bases+4) == top-2048 and num(bases+8) == top-4096
        elif label == 'warm-invalid.ram.gz':
            assert num(floor_addr) == top-8192
            assert raw[top-8192:top] == bytes(8192)
            assert num(bases+4) == top-2048 and num(bases+8) == top-4096
        elif label == 'install-accounting.ram.gz':
            assert num(floor_addr) == top-9216 and num(bases+8) == top-5120
            assert raw[top-9216:top] == bytes(9216)
        elif label == 'remove-accounting.ram.gz':
            assert num(floor_addr) == top-6144 and num(bases+4) == top-2048
            assert num(descriptors+4) == 0x12100 and num(descriptors+8) == 0
            assert raw[top-6144:top] == bytes(6144)
            assert num(top-8192) == 0x5a5a5a5a
        else:
            raise AssertionError(label)
print('PASS three-ROM lifecycle logs and twelve RAM captures')

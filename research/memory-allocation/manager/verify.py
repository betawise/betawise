#!/usr/bin/env python3
"""Check saved native Manager observations independently of guest assertions."""
from pathlib import Path
import gzip
import hashlib
import json
import sys

out = Path(sys.argv[1]).resolve()
sha = lambda data: hashlib.sha256(data).hexdigest()
manifest = json.loads((out / 'manifest.json').read_text())
repair = manifest.get('repair_on_init', False)
assert manifest['normalize_command_lanes'] is True
assert json.loads((out / 'results.json').read_text())['result'] == 'PASS'
captures = {}
for row in manifest['ram_captures']:
    compressed = (out / row['file']).read_bytes()
    raw = gzip.decompress(compressed)
    assert sha(compressed) == row['sha256'] and sha(raw) == row['raw_sha256']
    assert len(raw) == 0x80000
    captures[row['file'].removesuffix('.ram.gz')] = raw
assert len(captures) == 11
assert captures['before-control'][0x7b800:0x7d800] == captures['after-control'][0x7b800:0x7d800]
for label, floor, bases in [
        ('after-control', 0x7b800, [0x7d000, 0x7c800]),
        ('after-install', 0x7bc00 if repair else 0x7ac00, [0x7d000, 0x7c800, 0x7bc00]),
        ('after-remove', 0x7c800 if repair else 0x7b800, [0x7d000, 0x7c800])]:
    raw = captures[label]
    num = lambda addr: int.from_bytes(raw[addr:addr+4], 'big')
    assert num(0x35de) == floor
    assert min(bases)-floor == (0 if repair and label != 'after-control' else 4096)
    assert [num(0x355e+i*4) for i in range(1,len(bases)+1)] == bases
    if label != 'after-control':
        for i, base in enumerate(bases, 1):
            assert num(base) == 0x70000000+i
            size = 2048 if i < 3 else 3072
            assert raw[base+4:base+size] == bytes(size-4)
    if repair and label != 'after-control':
        assert num(0x26300) == (0x7ac00 if label == 'after-install' else 0x7b800)
        assert num(0x26304) == floor and num(0x2630c) == floor
        assert num(0x26310) == (0x7bc00 if label == 'after-install' else 0)
        assert num(0x26314) == (2 if label == 'after-install' else 3)
for label, floor in [('install-cleared',0x7ac00), ('remove-cleared',0x7b800)]:
    assert captures[label][floor:0x7d800] == bytes(0x7d800-floor)
finalized = captures['install-finalized']
assert int.from_bytes(finalized[0x35f8:0x35fa], 'big') == 0
assert int.from_bytes(finalized[0x35de:0x35e2], 'big') == 0x7ac00
guest = json.loads((out / 'guest-result.json').read_text())
assert guest['clear_observations'] == 2 and guest['normalized_commands'] > 0
readback = json.loads((out / 'readback.json').read_text())
assert readback['size'] == 1024 and readback['sha256'] == manifest['applet_sha256'][2]
rows = [json.loads(line) for line in (out / 'protocol.jsonl').read_text().splitlines()]
for command, response in [(6,0x46),(2,0x42),(0xb,0x47),(7,0x48),(8,0x52),(5,0x45)]:
    assert any(row['op']=='W' and bytes.fromhex(row['outgoing'])[0]==command
               and bytes.fromhex(row['incoming_header'] or '00')[0]==response for row in rows)
for row in manifest.get('evidence_files', []):
    assert sha((out / row['file']).read_bytes()) == row['sha256']
print('PASS original Manager protocol, applet readback, eleven RAM captures, full clears, reinitialization and '
      + ('executed INIT floor repair' if repair else 'retained gaps'))

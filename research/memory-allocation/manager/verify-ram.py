#!/usr/bin/env python3
"""Verify executed private RAM-loader observations without a screen oracle."""
from pathlib import Path
import gzip
import hashlib
import json
import sys

out = Path(sys.argv[1]).resolve()
sha = lambda b: hashlib.sha256(b).hexdigest()
manifest = json.loads((out / 'manifest.json').read_text())
assert manifest['ram_loader_only'] and not manifest['normalize_command_lanes']
assert json.loads((out / 'results.json').read_text())['result'] == 'PASS'
assert len(manifest['ram_captures']) == 2
for row in manifest['ram_captures']:
    compressed = (out / row['file']).read_bytes()
    raw = gzip.decompress(compressed)
    assert sha(compressed) == row['sha256'] and sha(raw) == row['raw_sha256']
    num = lambda addr: int.from_bytes(raw[addr:addr+4], 'big')
    assert num(0x35de) == 0x5c000
    assert num(0xe0a+3*4) == 0x5c000 and num(0x355e+3*4) == 0x5c400
    assert num(0x5c000) == 0xc0ffeead
    assert int.from_bytes(raw[0x5c014:0x5c016], 'big') == manifest.get('ram_applet_id', 0x7010)
    assert num(0x5c400) == 0x52414d49 and num(0x26320) == 0x5c000
    assert int.from_bytes(raw[0x26324:0x26326], 'big') == 0x2675
    assert raw[0x7c800:0x7d800] == bytes([0xc3])*4096
guest = json.loads((out / 'guest-result.json').read_text())
assert guest == {'clear_observations':0, 'normalized_commands':0}
for row in manifest.get('evidence_files', []):
    assert sha((out / row['file']).read_bytes()) == row['sha256']
print('PASS private RAM-loader registration, executed INIT outside global initialization, and preserved existing A5')

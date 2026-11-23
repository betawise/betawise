#!/usr/bin/env python3
"""Reproduce scoped Neo 3.21 message evidence without executing guest code."""
from pathlib import Path
import hashlib
import json
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
entry = next(x for x in json.loads((HERE.parents[1] / 'abi-audit/rom-inventory.json').read_text())
             if x['name'] == 'neo_3_21')
rom = ROOT / entry['path']
data = rom.read_bytes()
assert hashlib.sha256(data).hexdigest() == entry['sha256']
# Independently selected instructions anchoring the producer/consumer traces.
checks = {
    0x417aee: '7e1b0c2f00fc0005',
    0x417af8: '2c3c000000fc',
    0x417b08: '2c3c000000fe',
    0x417b1e: '2f062f0720524e90',
    0x4185bc: '16bc00fe',
    0x418742: '16bc00fc',
    0x428886: '701bb680',
    0x42888e: '0c87000000fc',
    0x428902: '0c87000000fe',
    0x42f224: '701bbc80',
    0x42f22a: '0c87000000fc',
    0x439ca0: '701cbc806710701dbc80670a028600ffffff08c60018',
}
for address, expected in checks.items():
    offset = address - entry['base']
    assert data[offset:offset + len(bytes.fromhex(expected))].hex() == expected, hex(address)
ranges = [(0x417ace, 0x417b2a), (0x417c1e, 0x417d0e),
          (0x418588, 0x4185c4), (0x418724, 0x418754),
          (0x42882c, 0x42893e), (0x4290d0, 0x4290fa),
          (0x42f200, 0x42f246), (0x439c60, 0x439d0a),
          (0x4119e8, 0x411a14), (0x411bea, 0x411c52),
          (0x41c2e4, 0x41c40e), (0x422be4, 0x422c64)]
output = ['Neo 3.21 static message evidence; no runtime acceptance claim.',
          f"{entry['path']} SHA-256 {entry['sha256']}"]
for start, end in ranges:
    output.append(subprocess.check_output([
        'm68k-linux-gnu-objdump', '-D', '-b', 'binary', '-m', 'm68k:68000',
        f"--adjust-vma={entry['base']}", f'--start-address={start}',
        f'--stop-address={end}', str(rom)], text=True).replace(str(rom), entry['path']))
(HERE / 'messages-disassembly.txt').write_text('\n'.join(line.rstrip() for line in '\n'.join(output).splitlines()) + '\n')
print(f'PASS: ROM SHA-256, {len(checks)} instruction anchors, {len(ranges)} disassembly excerpts')

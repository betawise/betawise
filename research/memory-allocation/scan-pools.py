#!/usr/bin/env python3
"""Bounded binary-only pool-pattern search; candidates require manual review."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
out = Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=False)
sources = [
    ('Ghidra/Alphasmart 3000/SmartApplets/OS3KROM.OS3KOS', 0x4c0000),
    ('Ghidra/Alphasmart 3000/SmartApplets/OS3KNeoROM.OS3KOS', 0x5c0000),
    ('Ghidra/Alphasmart Neo/SmartApplets/os3kneorom.os3kos', 0x410000),
    ('Ghidra/Alphasmart 3000/SmartApplets/SMALLOS3KROM.OS3KOS', 0x400000),
    ('Ghidra/Alphasmart 3000/SmartApplets/SMALLOS3KNeoROM.OS3KOS', 0x400000),
    ('Ghidra/Alphasmart Neo/SmartApplets/smallos3kneorom.os3kos', 0x400000),
    ('Ghidra/Alphasmart 3000/SmartApplets/UpdaterReverterROM.OS3KOS', 0x4c0000),
]
inputs = [(path, base, (ROOT / path).read_bytes()) for path, base in sources]
with zipfile.ZipFile(ROOT / 'mame/roms/asma3k.zip') as archive:
    inputs.append(('mame/roms/asma3k.zip:28f008b3.u1', 0x400000,
                   archive.read('28f008b3.u1')))
results = []
for index, (source, base, blob) in enumerate(inputs):
    row = dict(source=source, base=base, size=len(blob),
               sha256=hashlib.sha256(blob).hexdigest(), candidates=[])
    row['bytes_with_low_bit_set'] = sum(bool(x & 1) for x in blob)
    if not row['bytes_with_low_bit_set']:
        row['excluded'] = 'Every byte has bit 0 clear; unreliable instruction image.'
        results.append(row)
        continue
    binary = out / f'{index}.bin'
    binary.write_bytes(blob)
    listing = subprocess.check_output([
        'm68k-linux-gnu-objdump', '-D', '-z', '-b', 'binary', '-m', 'm68k:68000',
        '--adjust-vma', hex(base), str(binary)], text=True)
    (out / f'{index}.dis').write_text(listing)
    lines = listing.splitlines()
    for i, line in enumerate(lines):
        reasons = []
        if re.search(r'(?:mulu[wl]?|muls[wl]?).*#(?:20|5),|'
                     r'lea\s+%a[0-6]@\(20\)|(?:adda|addl).*#20,%a[0-6]', line):
            reasons.append('descriptor stride / multiply')
        if re.search(r'subql\s+#1,%a[0-6]@(?:\((?:4|8|12|16)\))?$', line):
            reasons.append('possible free-count decrement')
        for reg in re.findall(r',(%a[0-6])@\(16\)', line):
            offsets = set()
            for near in lines[max(0, i-25):i+26]:
                match = re.search(r'(?:move[lw]|clr[lw])\s+.*,' + reg +
                                  r'@(?:\((\d+)\))?\s*$', near)
                if match:
                    offsets.add(int(match[1] or 0))
            if {0, 4, 8, 12, 16} <= offsets:
                reasons.append('five-field write neighborhood')
        if reasons:
            row['candidates'].append(dict(reasons=reasons, instruction=line,
                context=lines[max(0, i-25):i+26]))
    results.append(row)
(out / 'pool-candidates.json').write_text(json.dumps(results, indent=2) + '\n')
for row in results:
    print(row['source'], row.get('excluded', str(len(row['candidates'])) + ' candidates'))

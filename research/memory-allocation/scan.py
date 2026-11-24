#!/usr/bin/env python3
"""Conservative direct/indexed call census; raw literals alone are not calls."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WS = ROOT.parent
out = Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=False)
items = json.loads((ROOT / 'research/abi-audit/vendor-image-inventory.json').read_text())
rows = []
interesting = {10: 'SaveScreen', 113: 'FileBindState', 122: 'FileCreate', 138: 'ClipboardResize', 174: 'CallSysInt', 263: 'FontDialogCreate'}
for index, item in enumerate(items):
    path = WS / item['path']
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == item['sha256']
    # Require an ordered export neighborhood; do not count isolated data words.
    stubs = {}
    for slot in interesting:
        opcode = 0xA000 + slot * 4
        for off in range(0, len(data)-1, 2):
            if data[off:off+2] != opcode.to_bytes(2, 'big'):
                continue
            neighbors = [int.from_bytes(data[j:j+2], 'big') for j in range(max(0, off-16), min(len(data)-1, off+18), 2)]
            if sum(0xA000 <= n <= 0xA470 and n % 4 == 0 for n in neighbors) >= 8:
                stubs[off] = slot
    listing = subprocess.check_output(['m68k-linux-gnu-objdump', '-D', '-b', 'binary', '-m', 'm68k:68000', str(path)], text=True)
    (out / f'{index:02}.dis').write_text(listing)
    lines = listing.splitlines()
    hits = []
    for i, line in enumerate(lines):
        target = None
        match = re.search(r'(?:jsr|bsr[swl]?)\s+0x([0-9a-f]+)', line)
        if match:
            target = int(match[1], 16)
        match = re.search(r'jsr %pc@\(0x([0-9a-f]+),%([a-z0-9]+):[wl]\)', line)
        if match:
            for earlier in reversed(lines[max(0, i-8):i]):
                load = re.search(r'movea[wl] #(-?\d+),%' + match[2] + r'\b', earlier)
                if load:
                    target = (int(match[1], 16) + int(load[1])) & 0xFFFFFFFF
                    break
        if target in stubs:
            slot = stubs[target]
            context = '\n'.join(lines[max(0, i-20):i+3])
            selectors = [int(value, 16) for value in re.findall(r'pea 0x([0-9a-f]+)', context)] if slot == 174 else []
            hits.append({'slot': slot, 'service': interesting[slot], 'instruction': line.strip(), 'nearby_pea_literals': selectors, 'context': context})
    row = {key: item[key] for key in ('name', 'path', 'sha256')}
    row.update(header_ram_bytes=int.from_bytes(data[8:12], 'big'), export_candidates={str(k): v for k, v in stubs.items()}, calls=hits)
    rows.append(row)
    scratch = [h for h in hits if h['slot'] == 174 and set(h['nearby_pea_literals']) & {0x3000, 0x5000}]
    if scratch:
        print(item['name'], [(h['instruction'].split(':')[0], sorted(set(h['nearby_pea_literals']) & {0x3000, 0x5000})) for h in scratch])
summary = {'scope': 'All inventoried images; direct/nearby-register PC-indexed candidates only, not exhaustive indirect call resolution.', 'image_count': len(rows), 'images': rows}
(out / 'calls.json').write_text(json.dumps(summary, indent=2) + '\n')
print('PASS hashes and census for', len(rows), 'images')

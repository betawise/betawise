#!/usr/bin/env python3
"""Read-only package map and both zero/FF padding inventory (not a free-space proof)."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
WS = ROOT.parent
inventory = json.loads((ROOT / 'research/abi-audit/rom-inventory.json').read_text())
result = []
for name in ('as3000', 'neo_3_01', 'neo_3_21'):
    entry = next(e for e in inventory if e['name'] == name)
    image = (WS / entry['path']).read_bytes()
    assert hashlib.sha256(image).hexdigest() == entry['sha256']
    segments = []
    cursor = 0
    for pos in range(0x50, 0x70, 8):
        address = int.from_bytes(image[pos:pos+4], 'big')
        logical = int.from_bytes(image[pos+4:pos+8], 'big')
        if address == logical == 0:
            break
        # Only 2013's rounded transfer contract is qualified here. Older
        # packages include four extra bytes after their logical descriptors.
        extent = (logical + 1023) & ~1023 if name == 'neo_3_21' else logical
        assert cursor + extent <= len(image)
        data = image[cursor:cursor+extent]
        padding = []
        for match in re.finditer(b'\x00{256,}|\xff{256,}', data):
            begin, end = address + match.start(), address + match.end()
            # Raw aligned absolute values are evidence only: absence does not
            # exclude computed addresses, PC-relative references or range CRCs.
            refs = []
            main_size = 0x60000 if name == 'neo_3_21' else 0x40000
            for off in range(0, main_size - 3, 2):
                target = int.from_bytes(image[off:off+4], 'big')
                if begin <= target < end:
                    refs.append({'package_offset': hex(off), 'value': hex(target)})
            padding.append({'begin': hex(begin), 'end_exclusive': hex(end),
                            'bytes': end-begin, 'fill': hex(match[0][0]),
                            'aligned_absolute_values_into_range': refs,
                            'status': 'candidate padding; semantic non-use not proven'})
        segments.append({'begin': hex(address), 'logical_bytes': logical,
                         'mapped_bytes': extent, 'end_exclusive': hex(address+extent),
                         'source_offset': hex(cursor), 'padding': padding})
        cursor += extent
    result.append({'name': name, 'sha256': entry['sha256'], 'package_bytes': len(image),
                   'segments': segments, 'remaining_package_bytes': len(image)-cursor,
                   'note': 'SmallROM excluded; omitted physical bytes are unknown, not free'})
print(json.dumps(result, indent=2))

#!/usr/bin/env python3
"""Hash-gated, deterministic USB research anchors; no execution or USB access."""
import hashlib
import json
from pathlib import Path

workspace = Path(__file__).resolve().parents[3]
paths = {
    'rom': ('Ghidra/Alphasmart Neo/SmartApplets/os3kneorom.os3kos',
            '32fe55bb50c1b58326bd303f14973b8402ddf8bf6662b210e4d5e9f931c7e6c0'),
    'alphaword': ('Ghidra/Alphasmart Neo/SmartApplets/alphawordplus.os3kapp',
                 'a8ae516734a0e0b2e19d51ffb7dff3893074ca733fa40207cbff7ead1433f29e'),
}
images = {}
for name, (path, expected) in paths.items():
    images[name] = (workspace / path).read_bytes()
    assert hashlib.sha256(images[name]).hexdigest() == expected, path
rom = images['rom']


def at(address, size):
    offset = address - 0x410000
    assert 0 <= offset <= len(rom) - size
    return rom[offset:offset + size]


assert at(0x4495f9, 9) == bytes.fromhex('002d2c040f0e0a0127')
slots = {53: 0x424780, 112: 0x43a778, 126: 0x43b660,
         127: 0x43b6f0, 149: 0x438c44, 151: 0x418794,
         175: 0x427e04, 178: 0x429102, 179: 0x4291be,
         185: 0x428598, 186: 0x4285ce, 190: 0x42f6a8, 191: 0x42f744}
for slot, target in slots.items():
    assert int.from_bytes(at(0x44f15e + 4 * slot, 4), 'big') == target

# Neo AlphaWord uses immediate PC deltas; verify the actual instructions,
# destination and syscall word instead of relying on Ghidra's guessed types.
calls = {0x1fc: (0x12ce8, 0x12ee4, 0xa2e4),
         0x258: (0x12c8e, 0x12ee6, 0xa2e8),
         0x1e2: (0x12d0c, 0x12eee, 0xa2f8),
         0x232: (0x12cbe, 0x12ef0, 0xa2fc)}
aw = images['alphaword']
for site, (delta, destination, opcode) in calls.items():
    assert aw[site-6:site] == b'\x20\x7c' + delta.to_bytes(4, 'big')
    assert aw[site:site+4] == bytes.fromhex('4ebb88fe')
    assert site + delta == destination
    assert aw[destination:destination+2] == opcode.to_bytes(2, 'big')

tables = {}
for table in (0x42861e, 0x42f78a):
    keys = at(table + 26, 13)
    assert keys == bytes.fromhex('0107080b0c0d101112131e1f20')
    tables[f'{table:08x}'] = {
        f'{key:02x}': f'{table + int.from_bytes(at(table + 2*(12-i), 2), "big", signed=True):08x}'
        for i, key in enumerate(keys)
    }
print(json.dumps(dict(images={n: dict(path=p, sha256=h) for n, (p, h) in paths.items()},
                      slots={str(k): f'{v:08x}' for k, v in slots.items()},
                      alphaword_calls={f'{k:08x}': f'{v[2]:04x}' for k, v in calls.items()},
                      transfer_jump_tables=tables,
                      result='PASS static anchors (not runtime validation)'), indent=2))

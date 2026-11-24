#!/usr/bin/env python3
"""Replay read-only floor discovery using real guest RAM captures and ROMs."""
from pathlib import Path
import gzip
import hashlib
import json
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for row in json.loads((ROOT / 'betawise/research/abi-audit/rom-inventory.json').read_text()):
    capture = Path(sys.argv[1]).resolve() / row['name'] / 'floor-reserved.ram.gz'
    assert capture.is_file(), f"Missing freshly generated capture: {capture}"
    ram = gzip.decompress(capture.read_bytes())
    rom = (ROOT / row['path']).read_bytes()
    assert hashlib.sha256(rom).hexdigest() == row['sha256']
    def read32(blob, offset):
        assert 0 <= offset <= len(blob)-4
        return int.from_bytes(blob[offset:offset+4], 'big')
    handler = read32(ram, 0x28)
    h = handler-row['base']
    # Validate this dispatcher shape before interpreting its operands.
    mask = bytes.fromhex('000003fc' if row['name'] != 'neo_3_21' else '000007fc')
    assert rom[h:h+14] == bytes.fromhex('206f000230100280') + mask + bytes.fromhex('41f9')
    assert rom[h+18:h+26] == bytes.fromhex('d1c05c8f20504ed0')
    table = read32(rom, h+14)
    target = read32(rom, table-row['base']+107*4)
    f = target-row['base']
    # Exact common function prefix, with two RAM-address operands masked out.
    assert rom[f:f+6] == bytes.fromhex('48e70f38247c')
    assert rom[f+10:f+44] == bytes.fromhex(
        '283cfffffe002e0420522028000c90a80008ce800c870000020062027e002c07267c')
    assert rom[f+48:f+50] == bytes.fromhex('2039')
    assert rom[f+54:f+68] == bytes.fromhex('20532210d2a8000c9081dc80287c')
    floor_address = read32(rom, f+50)
    last_address = read32(rom, f+44)
    floor = read32(ram, floor_address)
    last_record = read32(ram, last_address)
    assert floor_address % 2 == 0 and floor_address < len(ram)-4
    assert last_record % 2 == 0 and last_record < len(ram)-72
    assert read32(ram, last_record) + read32(ram, last_record+12) <= floor < len(ram)
    print(f"PASS {row['name']}: vector={handler:08x} table={table:08x} "
          f"slot107={target:08x} floor_global={floor_address:08x} floor={floor:08x}")

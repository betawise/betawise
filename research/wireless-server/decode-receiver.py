#!/usr/bin/env python3
"""Decode the inventoried receiver 01.20 FUD into flash bytes; never flashes hardware."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[2]
EXPECTED = '41c645a87467f36ee2a9ff1970d3c0beaf41fce2ee5695f6cdbc8d94ecc5a2a1'


def decode(data):
    def require(condition, message):
        if not condition:
            raise ValueError(message)
    header_end = data.find(b'\r\n\r\n')
    require(0 < header_end < 1024, 'missing bounded header')
    lines = data[:header_end].decode('ascii').splitlines()
    require(lines[0] == 'SATURN FIRMWARE FILE/1.0', 'unsupported format')
    fields = dict(line.split(': ', 1) for line in lines[1:])
    require(fields['Device'] == 'Renaissance Receiver', 'not receiver firmware')
    require(fields['Firmware-Version'] == '01.20', 'unreviewed receiver version')
    require(int(fields['PageSize']) == 256 and int(fields['AddressSize']) == 4,
            'unsupported map geometry')
    start = 1024 + len(b'---- DATA BLOCKS ----')
    require(data[1024:start] == b'---- DATA BLOCKS ----', 'missing data marker')
    map_start = int(fields['MapPosition'])
    marker = b'---- BLOCK MAP ----'
    require(data[map_start-len(marker):map_start] == marker, 'missing map marker')
    require(data[map_start:map_start+2] == bytes.fromhex('e10b'), 'unreviewed map prefix')
    # This prefix is observed, not assigned a guessed count/checksum meaning.
    raw_map = data[map_start+2:]
    require(len(raw_map) > 0 and len(raw_map) % 8 == 0, 'truncated map')
    pages = list(struct.iter_unpack('<II', raw_map))
    data_end = map_start - len(marker)
    require(data_end-start == len(pages)*256, 'unmapped/extra data')
    base = pages[0][0]
    require(base == 0x104000, 'unreviewed load address')
    output = bytearray()
    for index, (address, offset) in enumerate(pages):
        require(address == base+index*256, 'noncontiguous/duplicate flash page')
        require(offset == start+index*256, 'noncontiguous/duplicate data page')
        require(start <= offset and offset+256 <= data_end, 'page outside data region')
        output.extend(data[offset:offset+256])
    checksum = sum(output) & 255
    require(checksum == int(fields['Checksum']), 'payload checksum mismatch')
    return bytes(output), dict(header=fields, map_prefix='e10b',
        page_count=len(pages), page_size=256, base=base, end_exclusive=base+len(output),
        payload_offset=start, payload_size=len(output), checksum=checksum,
        sha256=hashlib.sha256(output).hexdigest(),
        mapping='little-endian uint32 flash address, uint32 absolute FUD offset')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=WORKSPACE/'Ghidra/NEOManager3_9_3USPC-extracted/receiver-analysis')
    args = parser.parse_args()
    inv = json.loads((HERE/'package-inventory.json').read_text())
    row = next(r for r in inv['files'] if r['sha256'] == EXPECTED)
    data = (WORKSPACE/row['path']).read_bytes()
    if hashlib.sha256(data).hexdigest() != EXPECTED:
        raise ValueError('receiver source hash differs from inventory')
    image, report = decode(data)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out/'receiver.bin').write_bytes(image)
    report.update(source=row['path'], source_sha256=EXPECTED)
    (args.out/'receiver-map.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

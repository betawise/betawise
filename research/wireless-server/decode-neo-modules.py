#!/usr/bin/env python3
"""Decode the two reviewed radio firmware resources in Wireless Updater 2.00.

Output is a physical flash image, not a flat executable 8051 CODE mapping.
CC2430/CC253x bank switching must be modeled before following banked calls.
"""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[2]
EXPECTED = '2757f362ce35324217b2f459e120fadc52deb0926859a4b8a7ce0339d8d18f96'


def decode_resource(data, start, label):
    image = bytearray(b'\xff' * 0x20000)
    offset, previous = start, -1
    records, overlaps = [], []
    seen = set()
    while offset+3 <= len(data):
        address = int.from_bytes(data[offset:offset+3], 'big')
        if address == 0xffffff:
            break
        if offset+19 > len(data) or address % 16 or not 0 <= address <= 0x1fff0:
            raise ValueError('invalid/truncated module record')
        if address < previous or (address == previous and address != 0x1fff0):
            raise ValueError('unreviewed record ordering')
        if address in seen:
            overlaps.append(dict(address=address, old=image[address:address+16].hex(),
                                 new=data[offset+3:offset+19].hex()))
        image[address:address+16] = data[offset+3:offset+19]
        records.append(dict(address=address, source_offset=offset+3))
        seen.add(address)
        previous = address
        offset += 19
    else:
        raise ValueError('missing module sentinel')
    size = offset+3-start
    metadata = data[offset+3:offset+14]
    if metadata != b'N'+size.to_bytes(4, 'big')+label.encode('ascii')+b'\0':
        raise ValueError('resource size/name metadata differs')
    return bytes(image), dict(label=label, start=start, sentinel_offset=offset,
        encoded_size=size, record_count=len(records), unique_pages=len(seen),
        record_format='big-endian 24-bit physical address followed by 16 bytes',
        fill=255, overlaps=overlaps, records=records,
        sha256=hashlib.sha256(image).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=WORKSPACE/'Ghidra/NEOManager3_9_3USPC-extracted/receiver-analysis')
    args = parser.parse_args()
    inv = json.loads((HERE/'package-inventory.json').read_text())
    row = next(r for r in inv['files'] if r['sha256'] == EXPECTED)
    data = (WORKSPACE/row['path']).read_bytes()
    if hashlib.sha256(data).hexdigest() != EXPECTED:
        raise ValueError('Wireless Updater source hash differs')
    args.out.mkdir(parents=True, exist_ok=True)
    reports = []
    for start, label in [(0x17f2, '01.30'), (0xccf2, '02.00')]:
        image, report = decode_resource(data, start, label)
        (args.out/f'neo-module-{label}.bin').write_bytes(image)
        (args.out/f'neo-module-{label}-records.json').write_text(json.dumps(report, indent=2)+'\n')
        reports.append({k: v for k, v in report.items() if k != 'records'})
    summary = dict(source=row['path'], source_sha256=EXPECTED, resources=reports)
    (args.out/'neo-modules.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()

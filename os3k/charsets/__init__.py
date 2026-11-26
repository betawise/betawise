"""Read shared native-byte to Unicode glyph mapping tables."""
from pathlib import Path


def load(path):
    mapping = {}
    for line in Path(path).read_text().splitlines():
        fields = line.split('#', 1)[0].split()
        if not fields:
            continue
        slot = int(fields[0], 16)
        if not 0 <= slot <= 255 or slot in mapping:
            raise ValueError(f'duplicate/invalid byte slot: {fields[0]}')
        value = None if fields[1] == 'UNMAPPED' else int(fields[1], 16)
        if value is not None and (not 0 <= value <= 0x10ffff or 0xd800 <= value <= 0xdfff):
            raise ValueError(f'invalid Unicode scalar at byte {slot:02X}')
        mapping[slot] = value
    if set(mapping) != set(range(256)):
        raise ValueError('charset must describe all 256 byte slots')
    return mapping


def glyph_name(slot, mapping):
    value = mapping[slot]
    if value is None:
        return f'neoByte{slot:02X}'
    name = f'uni{value:04X}'
    # Keep STARTCHAR names unique when a native charset has Unicode aliases.
    canonical = value if value in mapping and mapping[value] == value else min(
        byte for byte, char in mapping.items() if char == value)
    return name if slot == canonical else f'{name}.alt{slot:02X}'

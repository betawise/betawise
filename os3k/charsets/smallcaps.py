"""Validate the shared descriptor and encode/decode without runtime lookup tables."""
import json
from pathlib import Path

STYLES = ('regular', 'bold', 'italic')


def load(path=None):
    path = Path(path) if path else Path(__file__).with_name('neo-smallcaps.json')
    descriptor = json.loads(path.read_text())
    if descriptor['name'] != 'neo-smallcaps' or descriptor['version'] != 1:
        raise ValueError('unsupported small-cap charset')
    if tuple(descriptor['styles']) != STYLES:
        raise ValueError('unsupported small-cap styles')
    tables(descriptor)
    return descriptor


def byte(value):
    result = int(value, 16)
    if not 0 <= result <= 255:
        raise ValueError(f'invalid byte {value}')
    return result


def tables(descriptor):
    source_to_index = [255] * 256
    variants = []
    decode = [0] * 256
    used = set()
    reserved = {byte(c) for c in descriptor['reserved']}
    for index, letter in enumerate(descriptor['letters']):
        if index >= 255:
            raise ValueError('too many letter forms')
        canonical = byte(letter['canonical'])
        sources = [byte(c) for c in letter['source']]
        if canonical == 0 or canonical not in sources:
            raise ValueError('canonical source must be a nonzero input alias')
        for source in sources:
            if source_to_index[source] != 255:
                raise ValueError(f'duplicate source {source:02X}')
            source_to_index[source] = index
        row = [byte(letter[style]) for style in STYLES]
        for slot in row:
            if slot in reserved or slot in used:
                raise ValueError(f'occupied/reserved destination {slot:02X}')
            used.add(slot)
            decode[slot] = canonical
        variants.append(row)
    digits = [byte(c) for c in descriptor['superscript_digits']]
    if len(digits) != 10:
        raise ValueError('ten superscript slots required')
    for digit, slot in enumerate(digits):
        if slot in reserved or slot in used:
            raise ValueError(f'occupied/reserved destination {slot:02X}')
        used.add(slot)
        decode[slot] = ord('0') + digit
    return dict(source_to_index=source_to_index, variants=variants, decode=decode, digits=digits)


def canonical_lowercase(source):
    """Accept supported native lowercase letters."""
    if (0x61 <= source <= 0x7A or 0xE0 <= source <= 0xF6 or
            0xF8 <= source <= 0xFF or source in (5, 0x9A, 0x9C, 0x9E, 0xDF)):
        return source
    return None


def regular_from_lowercase(source):
    """66-byte C algorithm; input must be a known supported lowercase letter."""
    if source & 0x20:
        result = source ^ 0x2A
    else:
        result = 0x40 | ((25 + (source >> 6) + ((source >> 1) & 3)) ^ 0x0A)
    if not source & 0x10 and (0xAC >> (source & 7)) & 1:
        result ^= 0x2B
    return result


def encode(source, style):
    """Table-free native lowercase conversion."""
    if style not in STYLES:
        raise ValueError('unsupported small-cap style')
    source = canonical_lowercase(source)
    if source is None:
        return None
    regular = regular_from_lowercase(source)
    if style == 'italic':
        return regular ^ 0x2B
    if style == 'bold':
        return regular ^ 0x40
    return regular


def decode(slot):
    """Decode any private style to native lowercase, rejecting unassigned slots."""
    if not 0 <= slot <= 255:
        return None
    if 0x30 <= slot <= 0x39:
        return slot
    value = slot ^ (0x2B if slot & 0x20 else 0)
    index = ((value & 31) | ((value >> 2) & 32)) ^ 0x0A
    if index >= 32:
        if index == 55:
            return None
        source = index | 0xC0
    elif 1 <= index <= 26:
        source = index | 0x60
    elif index == 27:
        source = 5
    elif index == 31:
        source = 0xDF
    elif index in (28, 29, 30):
        source = (index << 1) + 0x62
    else:
        return None
    regular = regular_from_lowercase(source)
    return source if slot in (regular, regular ^ 0x2B, regular ^ 0x40) else None

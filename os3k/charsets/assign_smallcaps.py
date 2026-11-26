#!/usr/bin/env python3
"""Assign private styles deterministically, excluding native editor control slots."""
import argparse
import copy
import json
from pathlib import Path

if __package__:
    from .smallcaps import regular_from_lowercase, canonical_lowercase
else:
    from smallcaps import regular_from_lowercase, canonical_lowercase


def assign(descriptor):
    result = copy.deepcopy(descriptor)
    occupied = {int(c, 16) for c in result['reserved'] + result['superscript_digits']}
    if result['superscript_digits'] != [f'{c:02X}' for c in range(0x30, 0x3A)]:
        raise ValueError('table-free encoding requires digits at 30–39')
    for letter in result['letters']:
        source = int(letter['canonical'], 16)
        if canonical_lowercase(source) != source or 0x30 <= source <= 0x39:
            raise ValueError(f'unsupported lowercase source {source:02X}')
        regular = regular_from_lowercase(source)
        for style, slot in (('regular', regular), ('italic', regular ^ 0x2B), ('bold', regular ^ 0x40)):
            if slot in occupied:
                raise ValueError(f'{style} {letter["text"]}: occupied/reserved slot {slot:02X}')
            letter[style] = f'{slot:02X}'
            occupied.add(slot)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--charset', type=Path, default=Path(__file__).with_name('neo-smallcaps.json'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    original = json.loads(args.charset.read_text())
    generated = assign(original)
    if args.check:
        if original != generated:
            raise SystemExit('stale small-cap slot assignments')
    else:
        args.charset.write_text(json.dumps(generated, indent=2, ensure_ascii=False) + '\n')
    print(args.charset)


if __name__ == '__main__':
    main()
